"""Synthetic data generator for the APS POC.

Builds a plausible single-plant dataset: reference data, shared item master,
BOMs/routings, ~50 won projects/year plus an open quote pipeline, aftermarket
sales orders and overhaul jobs sized to ~$120M/year combined, and starting
inventory. Deterministic (fixed random seed) so re-runs are reproducible.

Deliberately NOT seeded here: PurchaseOrder / WorkOrder. Those represent
planned/released supply, which is the planning engine's output (phase 1
deliverable), not input data.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.aftermarket import SalesOrder
from app.models.bom import Bom, BomLine, Routing, RoutingOperation
from app.models.enums import (
    BomType,
    FindingAction,
    FindingSource,
    ItemType,
    MakeOrBuy,
    OverhaulJobStatus,
    ProjectStatus,
    PurchaseOrderStatus,
    WorkOrderSource,
    WorkOrderStatus,
    ProjectType,
    RoutingType,
    SalesOrderType,
    WorkCenterArea,
)
from app.models.item import Item, ItemSupplier
from app.models.overhaul import OverhaulFinding, OverhaulJob
from app.models.project import MachineType, Project, ProjectMilestone
from app.models.reference import CapacityCalendar, Plant, Supplier, WorkCenter
from app.models.supply import Inventory, PurchaseOrder, PurchaseOrderLine, WorkOrder
from app.seed import catalog

RNG_SEED = 42
TODAY = date.today()

# Machined/manufactured-part family -> primary shared work center
FAMILY_TO_SHARED_WC = {
    "impeller": "SH-CNC1",
    "shaft": "SH-CNC2",
    "casing": "SH-CNC3",
    "smallpart": "SH-CNC4",
    "kit": "AM-KIT",
}

MOTOR_MAP = {
    ("PUMP", "S"): "PC-MOTOR-50",
    ("PUMP", "M"): "PC-MOTOR-100",
    ("PUMP", "L"): "PC-MOTOR-200",
    ("COMPRESSOR", "S"): "PC-MOTOR-100",
    ("COMPRESSOR", "M"): "PC-MOTOR-200",
    ("COMPRESSOR", "L"): "PC-MOTOR-400",
}
GEARBOX_MAP = {"S": "PC-GEARBOX-S", "M": "PC-GEARBOX-S", "L": "PC-GEARBOX-L"}
IMPELLER_MAP = {"S": "MP-IMPELLER-S", "M": "MP-IMPELLER-M", "L": "MP-IMPELLER-L"}
INDUCER_MAP = {"S": "MP-INDUCER-S", "M": "MP-INDUCER-M", "L": "MP-INDUCER-M"}
SHAFT_MAP = {"S": "MP-SHAFT-S", "M": "MP-SHAFT-M", "L": "MP-SHAFT-L"}
CASING_MAP = {"S": "MP-CASING-S", "M": "MP-CASING-M", "L": "MP-CASING-L"}
WEARRING_MAP = {"S": "MP-WEARRING-S", "M": "MP-WEARRING-M", "L": "MP-WEARRING-M"}

PRICE_RANGE_BY_SIZE = {
    "S": (180_000, 320_000),
    "M": (350_000, 650_000),
    "L": (700_000, 1_400_000),
}

SUBASSEMBLY_LINES = {
    "SA-ELECASM": [
        ("PC-ELECPANEL", 1),
        ("PC-VFD", 1),
        ("PC-INSTR-PT", 2),
        ("PC-INSTR-TT", 2),
        ("PC-INSTR-VIB", 1),
        ("PC-NAMEPLATE", 1),
    ],
    "SA-PIPING": [
        ("RM-STEEL-316", 2),
        ("RM-GASKET-SHEET", 1),
        ("PC-GASKET-KIT", 1),
    ],
    "SA-GUARDASM": [
        ("PC-GUARD", 1),
        ("PC-FASTENER-KIT", 1),
    ],
    "SA-LUBESKID": [
        ("PC-LUBEPUMP", 1),
        ("PC-LUBERES", 1),
        ("PC-FILTER-LUBE", 1),
        ("PC-COOLER", 1),
    ],
}

KIT_LINES = {
    "MP-SEALKIT-STD": [("PC-SEAL-MECH", 1), ("PC-SEAL-OSEAL", 1), ("MP-SLEEVE-SHAFT", 1)],
    "MP-SEALKIT-HD": [("PC-SEAL-MECH", 2), ("PC-SEAL-OSEAL", 1), ("MP-LABYRINTHSEAL", 1)],
    "MP-BEARINGKIT": [("PC-BEARING-RAD", 2), ("PC-BEARING-THR", 1)],
    "MP-OHKIT-S": [("MP-SEALKIT-STD", 1), ("MP-BEARINGKIT", 1), ("MP-WEARRING-S", 1), ("MP-KEYSET", 1)],
    "MP-OHKIT-M": [("MP-SEALKIT-STD", 1), ("MP-BEARINGKIT", 1), ("MP-WEARRING-M", 1), ("MP-KEYSET", 1)],
    "MP-OHKIT-L": [("MP-SEALKIT-HD", 1), ("MP-BEARINGKIT", 1), ("MP-WEARRING-M", 2), ("MP-KEYSET", 1)],
}


def _id(prefix: str, n: int) -> str:
    return f"{prefix}-{n:06d}"


def seed_all(db: Session) -> dict[str, int]:
    rng = random.Random(RNG_SEED)
    stats: dict[str, int] = {}

    items = _create_items(db, stats)
    work_centers = _create_work_centers(db, stats)
    _create_capacity_calendar(db, work_centers, stats)
    _create_kit_boms(db, items, stats)
    _create_subassembly_boms(db, items, stats)
    _create_manufactured_part_routings(db, items, stats)
    machine_types = _create_machine_types(db, items, rng, stats)
    _create_projects(db, items, machine_types, rng, stats)
    _create_sales_orders(db, items, rng, stats)
    _create_overhaul_jobs(db, items, rng, stats)
    _create_inventory(db, items, rng, stats)
    _create_inflight_project_supply(db, items, rng, stats)

    db.commit()
    return stats


def _create_items(db: Session, stats: dict) -> dict[str, Item]:
    plant = Plant(plant_id="PLANT-01", name="Main Plant")
    db.add(plant)

    suppliers: dict[str, Supplier] = {}
    for sid, name, reliability in catalog.SUPPLIERS:
        sup = Supplier(supplier_id=sid, name=name, reliability_rating=reliability)
        db.add(sup)
        suppliers[sid] = sup
    db.flush()

    items: dict[str, Item] = {}

    def add_item(item_id, desc, item_type, make_or_buy, cost, lead_time, supplier_ids,
                 is_project=False, is_aftermarket=False):
        it = Item(
            item_id=item_id,
            description=desc,
            item_type=item_type,
            make_or_buy=make_or_buy,
            uom="EA",
            standard_cost=cost,
            default_lead_time_days=lead_time,
            is_project_item=is_project,
            is_aftermarket_item=is_aftermarket,
            reorder_point=20 if is_aftermarket else None,
            reorder_qty=20 if is_aftermarket else None,
            safety_stock=5 if is_aftermarket else None,
        )
        db.add(it)
        items[item_id] = it
        for i, sup_id in enumerate(supplier_ids):
            db.add(ItemSupplier(
                item_id=item_id, supplier_id=sup_id,
                lead_time_days=lead_time, price=cost * 0.9,
                is_preferred=(i == 0),
            ))
        return it

    for item_id, desc, _, cost, lead_time, sup_ids in catalog.RAW_MATERIALS:
        add_item(item_id, desc, ItemType.RAW_MATERIAL, MakeOrBuy.BUY, cost, lead_time, sup_ids,
                 is_project=True)

    for item_id, desc, _, cost, lead_time, sup_ids, is_am in catalog.PURCHASED_COMPONENTS:
        add_item(item_id, desc, ItemType.PURCHASED_COMPONENT, MakeOrBuy.BUY, cost, lead_time,
                 sup_ids, is_project=True, is_aftermarket=is_am)

    for item_id, desc, family, cost, lead_time, is_am, machining_hours in catalog.MANUFACTURED_PARTS:
        it = add_item(item_id, desc, ItemType.MANUFACTURED_PART, MakeOrBuy.MAKE, cost, lead_time,
                      [], is_project=True, is_aftermarket=is_am)
        it._family = family  # stash for routing generation (not a mapped column)
        it._machining_hours = machining_hours

    for item_id, desc in catalog.SUBASSEMBLIES:
        add_item(item_id, desc, ItemType.SUBASSEMBLY, MakeOrBuy.MAKE, 0, 14, [], is_project=True)

    db.flush()
    stats["items"] = len(items)
    stats["suppliers"] = len(suppliers)
    return items


def _create_work_centers(db: Session, stats: dict) -> dict[str, WorkCenter]:
    wcs: dict[str, WorkCenter] = {}
    for wc_id, name, area in catalog.WORK_CENTERS:
        wc = WorkCenter(
            work_center_id=wc_id,
            plant_id="PLANT-01",
            name=name,
            area=WorkCenterArea(area),
            capacity_uom="hours",
            hourly_rate=95.0 if area == "SHARED" else 85.0,
        )
        db.add(wc)
        wcs[wc_id] = wc
    db.flush()
    stats["work_centers"] = len(wcs)
    return wcs


# Effective daily hours per work center. A "work center" here is a capacity
# pool, not necessarily one machine: CNC cells are banks of machines, and
# labor-constrained stations (kitting, QC, assembly) add shifts rather than
# capital. These numbers were not guessed — each was set by running the finite
# scheduler and reading the required-vs-available figure it reported, then
# sizing the pool to sit meaningfully below 100%. A pool at or above 100% has
# an unbounded queue: lateness compounds indefinitely rather than settling.
DAILY_HOURS = {
    # Shared machining
    "SH-CNC1": 24.0,   # ~3 machines (impellers/inducers)
    "SH-CNC2": 24.0,   # ~3 machines (shafts)
    "SH-CNC3": 24.0,   # ~3 machines (casings/housings)
    # Small precision hardware is the highest-volume machining demand by far:
    # sold as spares *and* consumed inside every kit and package.
    "SH-CNC4": 72.0,   # ~9 small lathes across shifts
    "SH-GRIND": 24.0,  # feeds both shaft and small-part flows
    "SH-WELD": 16.0,
    "SH-NDT": 16.0,
    "SH-HEATTREAT": 16.0,
    "SH-KEYWAY": 16.0,
    "SH-LAP": 16.0,
    "SH-TOOLROOM": 16.0,
    # New unit: 44 packages/yr at 340-560 assembly hours each is ~3.5
    # bay-years of work, so three bays run two shifts.
    "NU-ASM1": 16.0,
    "NU-ASM2": 16.0,
    "NU-ASM3": 16.0,
    "NU-QC": 16.0,
    # Aftermarket: kitting touches nearly every spares order and pays a setup
    # per batch, which multiplied once rush work was separated from routine
    # replenishment. Two benches across three shifts.
    "AM-KIT": 48.0,
    "AM-QC": 24.0,
}
DEFAULT_DAILY_HOURS = 8.0  # single bay / stand / test cell


def _daily_hours_for(wc_id: str) -> float:
    return DAILY_HOURS.get(wc_id, DEFAULT_DAILY_HOURS)


def _create_capacity_calendar(db: Session, work_centers: dict[str, WorkCenter], stats: dict) -> None:
    # Starts today, not in the past. Elapsed capacity cannot be used, and
    # including it silently understates utilization — a work center saturated
    # every usable month looked like ~68% when six months of unusable history
    # sat in the denominator. Runs past the demand horizon so forward-scheduled
    # late work has somewhere to land.
    start = TODAY
    # Demand runs to ~+365. The calendar needs meaningful headroom past that so
    # forward-scheduled late work has somewhere to land; otherwise orders get
    # flagged CAPACITY_INFEASIBLE merely for running off the end of the
    # calendar, which is a reporting artifact rather than a real shortfall.
    end = TODAY + timedelta(days=900)
    count = 0
    d = start
    entries = []
    while d <= end:
        if d.weekday() < 5:  # weekdays only
            for wc_id in work_centers:
                entries.append(CapacityCalendar(work_center_id=wc_id, calendar_date=d,
                                                 available_hours=_daily_hours_for(wc_id)))
                count += 1
        d += timedelta(days=1)
    db.bulk_save_objects(entries)
    stats["capacity_calendar_rows"] = count


def _make_bom(db: Session, parent_item_id: str, bom_type: BomType, lines: list[tuple[str, float]],
              effective_from: date | None = None) -> Bom:
    bom = Bom(parent_item_id=parent_item_id, bom_type=bom_type, version="1.0",
              effective_from=effective_from)
    db.add(bom)
    db.flush()
    for comp_id, qty in lines:
        db.add(BomLine(bom_id=bom.bom_id, component_item_id=comp_id, qty_per=qty, scrap_pct=0.02))
    return bom


def _make_routing(db: Session, item_id: str, routing_type: RoutingType,
                   ops: list[tuple[int, str, float, float, str]]) -> Routing:
    routing = Routing(item_id=item_id, routing_type=routing_type)
    db.add(routing)
    db.flush()
    for seq, wc_id, setup, run, desc in ops:
        db.add(RoutingOperation(
            routing_id=routing.routing_id, seq=seq, work_center_id=wc_id,
            setup_time_hours=setup, run_time_hours_per_unit=run, description=desc,
        ))
    return routing


def _create_kit_boms(db: Session, items: dict[str, Item], stats: dict) -> None:
    count = 0
    for kit_id, lines in KIT_LINES.items():
        _make_bom(db, kit_id, BomType.STANDARD, lines)
        count += 1
        family = "kit"
        ops = [(10, "AM-KIT", 1.0, 0.5, "Kit and package"), (20, "AM-QC", 0.5, 0.2, "Final QC")]
        _make_routing(db, kit_id, RoutingType.AFTERMARKET_MFG, ops)
    stats["kit_boms"] = count


def _create_subassembly_boms(db: Session, items: dict[str, Item], stats: dict) -> None:
    count = 0
    routing_ops = {
        "SA-ELECASM": [(10, "NU-ELEC", 4.0, 6.0, "Wire and test panel"), (20, "NU-QC", 1.0, 0.5, "QC")],
        "SA-PIPING": [(10, "SH-WELD", 3.0, 5.0, "Fit and weld piping"), (20, "NU-PIPE", 2.0, 3.0, "Install"),
                      (30, "NU-QC", 0.5, 0.3, "QC")],
        "SA-GUARDASM": [(10, "NU-ASM1", 1.0, 1.5, "Fit guard")],
        "SA-LUBESKID": [(10, "NU-ASM2", 3.0, 8.0, "Assemble lube skid"), (20, "NU-PIPE", 2.0, 3.0, "Piping"),
                        (30, "NU-QC", 1.0, 0.5, "QC")],
    }
    for sa_id, lines in SUBASSEMBLY_LINES.items():
        _make_bom(db, sa_id, BomType.STANDARD, lines)
        _make_routing(db, sa_id, RoutingType.NEW_UNIT, routing_ops[sa_id])
        count += 1
    stats["subassembly_boms"] = count


def _manufactured_part_routing_ops(family: str, machining_hours: float
                                    ) -> list[tuple[int, str, float, float, str]]:
    """Secondary ops scale off the part's own machining time rather than a
    flat rate — a shim set and a large shaft are both 'shaft family' but
    shouldn't consume anywhere near the same heat-treat/grind/NDT time."""
    wc = FAMILY_TO_SHARED_WC.get(family, "SH-CNC2")
    setup = round(max(0.25, min(2.0, machining_hours * 0.4)), 2)
    ops: list[tuple[int, str, float, float, str]] = [(10, wc, setup, machining_hours, "Machine")]
    if family == "shaft":
        ops.append((20, "SH-HEATTREAT", setup * 0.5, machining_hours * 0.5, "Heat treat"))
        ops.append((30, "SH-GRIND", setup * 0.5, machining_hours * 0.4, "Precision grind"))
        ops.append((40, "SH-NDT", setup * 0.25, machining_hours * 0.15, "NDT inspection"))
    elif family in ("impeller", "casing"):
        ops.append((20, "SH-NDT", setup * 0.25, machining_hours * 0.15, "NDT inspection"))
        ops.append((30, "SH-LAP", setup * 0.25, machining_hours * 0.3, "Lap/finish"))
    elif family == "smallpart":
        # Turned hardware: a finish grind where it matters, but no heat treat
        # or NDT — those are for rotating/pressure-containing parts.
        ops.append((20, "SH-GRIND", setup * 0.5, machining_hours * 0.4, "Finish grind"))
    return ops


def _create_machine_types(db: Session, items: dict[str, Item], rng: random.Random,
                           stats: dict) -> dict[str, MachineType]:
    machine_types: dict[str, MachineType] = {}

    for mt_id, name, family, size, has_lube in catalog.MACHINE_TYPES:
        eng, asm, test, mach, lead_wk = catalog.SIZE_PROFILE[size]
        mt = MachineType(
            machine_type_id=mt_id, name=name,
            avg_engineering_hours=eng, avg_assembly_hours=asm, avg_test_hours=test,
            avg_shared_machining_hours=mach, avg_lead_time_weeks=lead_wk,
        )
        db.add(mt)
        machine_types[mt_id] = mt

        # Template top-level finished item + its BOM/routing
        fg_id = f"FG-{mt_id}"
        fg_item = Item(
            item_id=fg_id, description=f"{name} (template)", item_type=ItemType.FINISHED_PACKAGE,
            make_or_buy=MakeOrBuy.MAKE, uom="EA", standard_cost=0, default_lead_time_days=int(lead_wk * 7),
            is_project_item=True, is_aftermarket_item=False,
        )
        db.add(fg_item)
        items[fg_id] = fg_item
        db.flush()  # Item/Bom have no ORM relationship, so order isn't inferred automatically

        lines = _template_bom_lines(family, size, has_lube)
        _make_bom(db, fg_id, BomType.PROJECT_TEMPLATE, lines)
        _make_routing(db, fg_id, RoutingType.NEW_UNIT, [
            (10, rng.choice(["NU-ASM1", "NU-ASM2", "NU-ASM3"]), 4.0, asm, "Final assembly"),
            (20, "NU-PAINT", 2.0, 6.0, "Paint/coat"),
            (30, rng.choice(["NU-TEST1", "NU-TEST2"]), 3.0, test, "Performance test"),
            (40, "NU-QC", 2.0, 4.0, "Final QC/inspection"),
            (50, "NU-PACK", 1.0, 3.0, "Crate and prep for ship"),
        ])

    db.flush()
    stats["machine_types"] = len(machine_types)
    return machine_types


def _create_manufactured_part_routings(db: Session, items: dict[str, Item], stats: dict) -> None:
    """Every MAKE manufactured part needs a routing, whether or not it's used
    in a project template BOM — many are spares-only (bushings, shim sets,
    etc.) or overhaul-finding replacement parts with no BOM of their own."""
    count = 0
    for item_id, _desc, family, _cost, _lead, _is_am, machining_hours in catalog.MANUFACTURED_PARTS:
        if item_id in KIT_LINES:
            continue  # kit routings created separately in _create_kit_boms
        _make_routing(db, item_id, RoutingType.AFTERMARKET_MFG,
                      _manufactured_part_routing_ops(family, machining_hours))
        count += 1
    stats["manufactured_part_routings"] = count


def _template_bom_lines(family: str, size: str, has_lube: bool) -> list[tuple[str, float]]:
    lines = [
        (IMPELLER_MAP[size], 1),
        (SHAFT_MAP[size], 1),
        (CASING_MAP[size], 1),
        (WEARRING_MAP[size], 2),
        ("MP-SLEEVE-SHAFT", 1),
        ("PC-BEARING-RAD", 2),
        ("PC-BEARING-THR", 1),
        ("PC-SEAL-MECH", 1),
        ("PC-COUPLING", 1),
        (MOTOR_MAP[(family, size)], 1),
        ("PC-SKID-STEEL", 1),
        ("PC-BASEPLATE", 1),
        ("PC-FASTENER-KIT", 2),
        ("PC-NAMEPLATE", 1),
        ("SA-ELECASM", 1),
        ("SA-PIPING", 1),
        ("SA-GUARDASM", 1),
    ]
    if family == "COMPRESSOR":
        lines.append((INDUCER_MAP[size], 1))
        lines.append((GEARBOX_MAP[size], 1))
    if has_lube:
        lines.append(("SA-LUBESKID", 1))
    return lines


def _create_projects(db: Session, items: dict[str, Item], machine_types: dict[str, MachineType],
                      rng: random.Random, stats: dict) -> None:
    RESOLVED_COUNT = 50  # won/lost decisions made this year
    FIRM_COUNT = 44
    QUOTED_COUNT = 15  # currently open pipeline, unresolved

    mt_ids = list(machine_types.keys())
    n = 0
    firm_created = 0
    total_contract_value = 0.0

    for i in range(1, RESOLVED_COUNT + 1):
        n += 1
        project_id = _id("PRJ", n)
        mt_id = rng.choice(mt_ids)
        mt = machine_types[mt_id]
        _, _, family, size, has_lube = next(t for t in catalog.MACHINE_TYPES if t[0] == mt_id)
        project_type = ProjectType.ETO if rng.random() < 0.7 else ProjectType.CTO
        is_firm = firm_created < FIRM_COUNT
        status = ProjectStatus.FIRM if is_firm else ProjectStatus.LOST

        contract_date = TODAY - timedelta(days=rng.randint(0, 365))
        lo, hi = PRICE_RANGE_BY_SIZE[size]
        value = round(rng.uniform(lo, hi), 2)

        proj = Project(
            project_id=project_id, customer=rng.choice(catalog.CUSTOMERS),
            project_type=project_type, machine_type_id=mt_id, status=status,
        )

        if status == ProjectStatus.FIRM:
            firm_created += 1
            variance = rng.uniform(0.9, 1.3) if project_type == ProjectType.ETO else rng.uniform(0.95, 1.1)
            lead_days = int(mt.avg_lead_time_weeks * 7 * variance)
            due_date = contract_date + timedelta(days=lead_days)
            proj.contract_date = contract_date
            proj.contract_due_date = due_date
            proj.contract_value = value
            total_contract_value += value

            fg_id = f"FG-{project_id}"
            fg_item = Item(
                item_id=fg_id, description=f"{mt.name} - {project_id}", item_type=ItemType.FINISHED_PACKAGE,
                make_or_buy=MakeOrBuy.MAKE, uom="EA", standard_cost=0,
                default_lead_time_days=lead_days, is_project_item=True, is_aftermarket_item=False,
            )
            db.add(fg_item)
            items[fg_id] = fg_item
            db.flush()

            template_lines = _template_bom_lines(family, size, has_lube)
            instance_lines = list(template_lines)
            if project_type == ProjectType.ETO and rng.random() < 0.3:
                extra = rng.choice(["PC-INSTR-VIB", "PC-INSTR-PT", "RM-STEEL-316"])
                instance_lines.append((extra, 1))
            instance_bom = _make_bom(db, fg_id, BomType.PROJECT_INSTANCE, instance_lines,
                                      effective_from=contract_date)
            proj.project_instance_bom_id = instance_bom.bom_id

            asm_hours = mt.avg_assembly_hours * rng.uniform(0.9, 1.1)
            test_hours = mt.avg_test_hours * rng.uniform(0.9, 1.1)
            _make_routing(db, fg_id, RoutingType.NEW_UNIT, [
                (10, rng.choice(["NU-ASM1", "NU-ASM2", "NU-ASM3"]), 4.0, asm_hours, "Final assembly"),
                (20, "NU-PAINT", 2.0, 6.0, "Paint/coat"),
                (30, rng.choice(["NU-TEST1", "NU-TEST2"]), 3.0, test_hours, "Performance test"),
                (40, "NU-QC", 2.0, 4.0, "Final QC/inspection"),
                (50, "NU-PACK", 1.0, 3.0, "Crate and prep for ship"),
            ])

            _add_milestones(db, project_id, contract_date, due_date, project_type)
        else:
            proj.quoted_value = value

        db.add(proj)

    # Open quote pipeline
    for i in range(1, QUOTED_COUNT + 1):
        n += 1
        project_id = _id("PRJ", n)
        mt_id = rng.choice(mt_ids)
        size = next(s for (m, _, _, s, _) in catalog.MACHINE_TYPES if m == mt_id)
        lo, hi = PRICE_RANGE_BY_SIZE[size]
        proj = Project(
            project_id=project_id, customer=rng.choice(catalog.CUSTOMERS),
            project_type=ProjectType.ETO if rng.random() < 0.7 else ProjectType.CTO,
            machine_type_id=mt_id, status=ProjectStatus.QUOTED,
            quoted_value=round(rng.uniform(lo, hi), 2),
        )
        db.add(proj)

    db.flush()
    stats["projects_total"] = n
    stats["projects_firm"] = firm_created
    stats["projects_quoted"] = QUOTED_COUNT
    stats["projects_lost"] = RESOLVED_COUNT - firm_created
    stats["firm_contract_value"] = round(total_contract_value, 2)


def _add_milestones(db: Session, project_id: str, contract_date: date, due_date: date,
                     project_type: ProjectType) -> None:
    total_days = (due_date - contract_date).days
    fractions = [0.15, 0.30, 0.55, 0.85, 1.0]
    names = ["Design freeze", "Procurement release", "Assembly start", "Test", "Ship"]
    if project_type == ProjectType.CTO:
        fractions = [0.05, 0.20, 0.50, 0.85, 1.0]
    for frac, name in zip(fractions, names):
        planned = contract_date + timedelta(days=int(total_days * frac))
        actual = planned if planned <= TODAY else None
        db.add(ProjectMilestone(project_id=project_id, milestone_name=name, planned_date=planned,
                                 actual_date=actual))


LARGE_MACHINED_PART_MARKERS = ("SHAFT", "CASING", "IMPELLER", "INDUCER", "DIFFUSER")


def _order_frequency_weight(it: Item) -> float:
    """Consumables (bearings, seals, kits) turn over far more often than
    large machined components (shafts, casings, impellers) — a real spares
    business sells many of the former for every one of the latter. Uniform
    selection was overloading the shared CNC/heat-treat/grind cells well
    beyond anything achievable with realistic capacity."""
    if it.item_type == ItemType.PURCHASED_COMPONENT or "KIT" in it.item_id:
        return 6.0
    return 1.0


def _order_qty_range(it: Item) -> tuple[int, int]:
    """A customer replacing a shaft or casing orders 1-2, not a dozen — those
    are single large parts per asset. Small hardware/consumables are
    plausibly ordered in bulk (stocking up, multi-unit fleets)."""
    if "KIT" in it.item_id:
        return (1, 6)
    if any(marker in it.item_id for marker in LARGE_MACHINED_PART_MARKERS):
        return (1, 3)
    return (1, 12)


def _create_sales_orders(db: Session, items: dict[str, Item], rng: random.Random, stats: dict) -> None:
    target_revenue = 84_000_000.0
    eligible = [it for it in items.values() if it.is_aftermarket_item]
    weights = [_order_frequency_weight(it) for it in eligible]
    total = 0.0
    n = 0
    while total < target_revenue:
        n += 1
        it = rng.choices(eligible, weights=weights, k=1)[0]
        order_type = SalesOrderType.EMERGENCY if rng.random() < 0.2 else SalesOrderType.STANDARD
        qty = rng.randint(*_order_qty_range(it))
        margin = rng.uniform(1.4, 2.2)
        unit_price = round(float(it.standard_cost) * margin, 2)
        line_total = unit_price * qty
        total += line_total

        if order_type == SalesOrderType.EMERGENCY:
            offset = int(rng.gauss(5, 15))  # urgent, but skewed slightly forward of "now"
            priority = rng.randint(1, 2)
        else:
            # A rolling year of open backlog (mostly future-dated), not clustered
            # around "today" — this is what makes weekly capacity load realistic
            # instead of compressing a year of demand into a few weeks.
            offset = rng.randint(-15, 365)
            priority = rng.randint(4, 8)
        requested_date = TODAY + timedelta(days=offset)

        db.add(SalesOrder(
            order_id=_id("SO", n), customer=rng.choice(catalog.CUSTOMERS), item_id=it.item_id,
            qty=qty, unit_price=unit_price, order_type=order_type,
            requested_date=requested_date, priority=priority,
        ))
    db.flush()
    stats["sales_orders"] = n
    stats["sales_orders_revenue"] = round(total, 2)


def _create_overhaul_jobs(db: Session, items: dict[str, Item], rng: random.Random, stats: dict) -> None:
    target_revenue = 36_000_000.0
    job_count = rng.randint(45, 55)

    raw_values = [rng.uniform(15_000, 220_000) for _ in range(job_count)]
    scale = target_revenue / sum(raw_values)
    values = [round(v * scale, 2) for v in raw_values]

    finding_pool = [it for it in items.values() if it.is_aftermarket_item]

    total = 0.0
    for i in range(1, job_count + 1):
        job_id = _id("OHJ", i)
        received_date = TODAY - timedelta(days=rng.randint(0, 365))
        days_elapsed = (TODAY - received_date).days
        status = _overhaul_status(days_elapsed, rng)

        job = OverhaulJob(
            job_id=job_id, customer=rng.choice(catalog.CUSTOMERS),
            asset_id=f"AST-{rng.randint(10000, 99999)}", received_date=received_date,
            status=status, estimated_value=values[i - 1],
        )
        db.add(job)
        total += values[i - 1]

        if status != OverhaulJobStatus.RECEIVED and status != OverhaulJobStatus.TEARDOWN:
            n_findings = rng.randint(2, 6)
            for _ in range(n_findings):
                it = rng.choice(finding_pool)
                action_roll = rng.random()
                if action_roll < 0.5:
                    action = FindingAction.REPLACE
                    source = FindingSource.BUY if rng.random() < 0.6 else FindingSource.INVENTORY
                elif action_roll < 0.8:
                    action = FindingAction.REPAIR
                    source = FindingSource.MAKE
                else:
                    action = FindingAction.REUSE
                    source = FindingSource.INVENTORY
                db.add(OverhaulFinding(
                    job_id=job_id, item_id=it.item_id, recommended_action=action,
                    qty=rng.randint(1, 2), source=source,
                ))

    db.flush()
    stats["overhaul_jobs"] = job_count
    stats["overhaul_jobs_revenue"] = round(total, 2)


def _overhaul_status(days_elapsed: int, rng: random.Random) -> OverhaulJobStatus:
    if days_elapsed > 90:
        return OverhaulJobStatus.COMPLETE
    if rng.random() < 0.15:
        return OverhaulJobStatus.AWAITING_APPROVAL  # stuck waiting on customer, regardless of age
    if days_elapsed < 3:
        return OverhaulJobStatus.RECEIVED
    if days_elapsed < 7:
        return OverhaulJobStatus.TEARDOWN
    if days_elapsed < 14:
        return OverhaulJobStatus.INSPECTION
    if days_elapsed < 30:
        return OverhaulJobStatus.AWAITING_APPROVAL
    if days_elapsed < 45:
        return OverhaulJobStatus.APPROVED
    if days_elapsed < 75:
        return OverhaulJobStatus.IN_REPAIR
    return OverhaulJobStatus.TEST


def _create_inventory(db: Session, items: dict[str, Item], rng: random.Random, stats: dict) -> None:
    count = 0
    for it in items.values():
        if it.item_type == ItemType.FINISHED_PACKAGE:
            continue
        if it.is_aftermarket_item:
            on_hand = rng.randint(5, 60)
        elif it.make_or_buy == MakeOrBuy.BUY:
            on_hand = rng.randint(2, 20)
        else:
            on_hand = rng.randint(0, 5)
        allocated = round(on_hand * rng.uniform(0, 0.3))
        db.add(Inventory(item_id=it.item_id, location="MAIN", qty_on_hand=on_hand, qty_allocated=allocated))
        count += 1
    db.flush()
    stats["inventory_rows"] = count


def _create_inflight_project_supply(db: Session, items: dict[str, Item], rng: random.Random,
                                     stats: dict) -> None:
    """Released purchase orders for projects already underway.

    A contract won eight months ago does not still have its motors and
    gearboxes un-ordered — procurement releases long-lead items right after
    the design freeze. Without this the planner sees every in-flight project
    as if nothing had been bought yet, correctly concludes a 56-day gearbox
    cannot arrive for a unit shipping next month, and floods the exception
    list with lateness that does not exist in reality.

    These are RELEASED, so a planning regen leaves them alone and nets demand
    against them as scheduled receipts.
    """
    projects = db.query(Project).filter(
        Project.status == ProjectStatus.FIRM,
        Project.contract_date.isnot(None),
        Project.contract_date < TODAY,
    ).all()

    po_seq = 0
    line_count = 0
    wip_count = 0
    for project in projects:
        bom = db.query(Bom).filter(Bom.bom_id == project.project_instance_bom_id).one_or_none()
        if bom is None:
            continue
        days_elapsed = (TODAY - project.contract_date).days
        total_days = max(1, (project.contract_due_date - project.contract_date).days)
        progress = days_elapsed / total_days

        # Past the 60% mark the unit is physically on the floor being built.
        # Represent it as one in-progress work order for the package: the
        # planner then nets the project's demand against real WIP instead of
        # re-planning a months-long build for a unit due in three days.
        if progress >= 0.60:
            wip_count += 1
            db.add(WorkOrder(
                wo_id=f"WO-WIP-{wip_count:05d}",
                item_id=bom.parent_item_id, qty=1,
                source=WorkOrderSource.PROJECT, source_ref=project.project_id,
                start_date=project.contract_date + timedelta(days=int(total_days * 0.55)),
                due_date=project.contract_due_date,
                status=WorkOrderStatus.IN_PROGRESS,
                bom_level=0,
            ))
            continue  # its components were consumed when the build started

        # Procurement releases start around the 30% mark of the schedule.
        if progress < 0.30:
            continue

        for line in db.query(BomLine).filter(BomLine.bom_id == bom.bom_id).all():
            item = items.get(line.component_item_id)
            if item is None or item.make_or_buy != MakeOrBuy.BUY:
                continue
            # Long-lead items go out first; short-lead hardware is bought later.
            lead = item.default_lead_time_days
            if lead < 14:
                continue
            release_day = project.contract_date + timedelta(days=int(total_days * 0.30))
            if release_day > TODAY:
                continue
            due = release_day + timedelta(days=lead)
            po_seq += 1
            po_id = f"PO-INFLIGHT-{po_seq:05d}"
            supplier = next(
                (s for s in catalog.PURCHASED_COMPONENTS if s[0] == item.item_id), None)
            supplier_id = supplier[5][0] if supplier else "SUP-006"
            db.add(PurchaseOrder(
                po_id=po_id, supplier_id=supplier_id,
                status=PurchaseOrderStatus.RELEASED,
                source=WorkOrderSource.PROJECT, source_ref=project.project_id,
                bom_level=1,
            ))
            db.flush()
            db.add(PurchaseOrderLine(
                po_id=po_id, item_id=item.item_id,
                qty=float(line.qty_per), due_date=due,
            ))
            line_count += 1

    db.flush()
    stats["inflight_project_pos"] = po_seq
    stats["inflight_project_po_lines"] = line_count
    stats["inflight_project_wip_wos"] = wip_count
