"""Multi-level BOM explosion with inventory netting and backward scheduling.

Classic regenerative MRP logic: process each independent demand, netting
against on-hand inventory (a running balance shared across all demands so the
same unit of stock isn't used twice), and for any shortfall either plan a
purchase order (BUY items) or a work order (MAKE items) — recursing into the
work order's own BOM to generate dependent demand for its components.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.bom import Bom, BomLine, Routing, RoutingOperation
from app.models.enums import (
    MakeOrBuy,
    PurchaseOrderStatus,
    WorkOrderSource,
    WorkOrderStatus,
)
from app.models.item import Item, ItemSupplier
from app.models.supply import Inventory, PurchaseOrder, PurchaseOrderLine, WorkOrder
from app.planning.demand import Demand, bucket_demand
from app.planning.schedule import (
    CapacityLedger,
    OperationConsumption,
    schedule_routing,
    simulate_routing_backward,
)

MAX_BOM_DEPTH = 12


@dataclass
class PlannedOrder:
    order_id: str  # assigned during explosion so children can peg to their parent
    item_id: str
    qty: float
    need_date: date
    start_date: date
    kind: str  # "WO" or "PO"
    source: WorkOrderSource
    source_ref: str
    supplier_id: str | None = None
    parent_wo_id: str | None = None
    bom_level: int = 0
    expedite_days: int = 0
    #: Of expedite_days, how many are attributable to competing for a busy
    #: work center rather than to lead time.
    capacity_delay_days: int = 0
    #: Hours that could not be placed anywhere in the horizon.
    unmet_hours: float = 0.0
    #: Projected completion under the finite schedule; may be after need_date.
    projected_end: date | None = None


@dataclass
class ReferenceData:
    items: dict[str, Item]
    boms: dict[str, Bom]  # keyed by parent_item_id
    routing_ops: dict[str, list[tuple[int, str, float, float]]]  # item_id -> ops
    preferred_supplier: dict[str, tuple[str, int]]  # item_id -> (supplier_id, lead_time_days)
    available: dict[str, float]  # item_id -> qty_on_hand - qty_allocated (mutated as we net)
    #: Already-committed incoming supply (RELEASED / IN_PROGRESS orders) as
    #: [due_date, remaining_qty] pairs sorted by date, consumed as we net.
    #: Without these the planner ignores work already in flight and re-buys
    #: everything from scratch.
    receipts: dict[str, list[list]]


def load_reference_data(db: Session) -> ReferenceData:
    items = {i.item_id: i for i in db.query(Item).all()}

    boms: dict[str, Bom] = {}
    for bom in db.query(Bom).all():
        lines = db.query(BomLine).filter(BomLine.bom_id == bom.bom_id).all()
        bom.loaded_lines = lines  # stash, not a mapped relationship
        boms.setdefault(bom.parent_item_id, bom)

    routing_ops: dict[str, list[tuple[int, str, float, float]]] = {}
    for routing in db.query(Routing).all():
        ops = db.query(RoutingOperation).filter(RoutingOperation.routing_id == routing.routing_id).all()
        routing_ops.setdefault(routing.item_id, [
            (o.seq, o.work_center_id, float(o.setup_time_hours), float(o.run_time_hours_per_unit))
            for o in ops
        ])

    preferred_supplier: dict[str, tuple[str, int]] = {}
    for isup in db.query(ItemSupplier).filter(ItemSupplier.is_preferred.is_(True)).all():
        preferred_supplier[isup.item_id] = (isup.supplier_id, isup.lead_time_days)

    available: dict[str, float] = {}
    for inv in db.query(Inventory).all():
        available[inv.item_id] = available.get(inv.item_id, 0.0) + float(inv.qty_on_hand) - float(inv.qty_allocated)

    # Scheduled receipts: supply already committed and therefore not replanned.
    # These are exactly the orders clear_planned() leaves alone.
    receipts: dict[str, list[list]] = {}
    open_po_ids = [
        po.po_id for po in db.query(PurchaseOrder).filter(
            PurchaseOrder.status.in_([PurchaseOrderStatus.RELEASED, PurchaseOrderStatus.RECEIVED])
        ).all()
    ]
    if open_po_ids:
        for line in db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id.in_(open_po_ids)).all():
            receipts.setdefault(line.item_id, []).append([line.due_date, float(line.qty)])

    for wo in db.query(WorkOrder).filter(
        WorkOrder.status.in_([WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS])
    ).all():
        receipts.setdefault(wo.item_id, []).append([wo.due_date, float(wo.qty)])

    for rows in receipts.values():
        rows.sort(key=lambda r: r[0])

    return ReferenceData(items=items, boms=boms, routing_ops=routing_ops,
                          preferred_supplier=preferred_supplier, available=available,
                          receipts=receipts)


@dataclass
class RawException:
    """Pre-enrichment exception emitted during explosion. engine.py turns these
    into persisted PlanException rows with severity and value-at-risk."""

    category: str
    message: str
    item_id: str | None = None
    source: str | None = None
    source_ref: str | None = None
    order_id: str | None = None
    days_late: int = 0
    need_date: date | None = None


class _Counter:
    """Order-id allocator.

    Must start above any *surviving* order, not at zero: a regen deletes only
    PLANNED supply, so RELEASED orders from prior runs keep their ids and a
    naive restart-at-1 collides with them the moment a planner releases
    anything.
    """

    def __init__(self, wo_start: int = 0, po_start: int = 0) -> None:
        self.wo = wo_start
        self.po = po_start

    def next_wo(self) -> str:
        self.wo += 1
        return f"WO-{self.wo:06d}"

    def next_po(self) -> str:
        self.po += 1
        return f"PO-{self.po:06d}"


def _max_suffix(db: Session, model, id_attr: str) -> int:
    """Highest numeric suffix among existing order ids (e.g. WO-000412 -> 412)."""
    highest = 0
    for (order_id,) in db.query(getattr(model, id_attr)).all():
        try:
            highest = max(highest, int(str(order_id).rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue
    return highest


def dispatch_key(d: Demand) -> tuple[int, date]:
    """Sequencing rule for finite capacity: whoever is scheduled first gets
    first claim on the machine.

    Priority wins over date, because that is the actual business rule here —
    an emergency turnaround order (priority 1-2) must be able to jump ahead of
    standard stock replenishment (4-8) even when the stock order is needed
    sooner. Firm project demand sits between them at 3. Within a priority
    band, earliest need date goes first.
    """
    return (d.priority, d.need_date)


def run_mrp(db: Session, demands: list[Demand], calendar: dict, today: date
            ) -> tuple[list[PlannedOrder], list[OperationConsumption], list[RawException], CapacityLedger]:
    ref = load_reference_data(db)
    planned: list[PlannedOrder] = []
    consumptions: list[OperationConsumption] = []
    exceptions: list[RawException] = []
    ledger = CapacityLedger(calendar)
    counter = _Counter(
        wo_start=_max_suffix(db, WorkOrder, "wo_id"),
        po_start=_max_suffix(db, PurchaseOrder, "po_id"),
    )

    demands = bucket_demand(demands)

    # Order matters now in a way it didn't under infinite capacity: capacity is
    # consumed as we go, so this sequence decides who gets the machine and who
    # gets pushed out. It also still nets limited on-hand stock against the
    # most urgent demand first.
    for d in sorted(demands, key=dispatch_key):
        _net_item(ref, d.item_id, d.qty, d.need_date, d.source, d.source_ref,
                  planned, consumptions, exceptions, ledger, today, counter,
                  depth=0, parent_wo_id=None)

    return planned, consumptions, exceptions, ledger


def _net_item(ref: ReferenceData, item_id: str, qty: float, need_date: date,
              source: WorkOrderSource, source_ref: str, planned: list[PlannedOrder],
              consumptions: list[OperationConsumption], exceptions: list[RawException],
              ledger: CapacityLedger, today: date, counter: _Counter, depth: int,
              parent_wo_id: str | None) -> date:
    """Plan supply for one requirement. Returns the date this item is actually
    available, which the caller uses as a floor for scheduling its parent —
    a subassembly cannot start before its components have arrived."""
    if depth > MAX_BOM_DEPTH:
        exceptions.append(RawException(
            category="BOM_DEPTH_EXCEEDED",
            message=f"BOM depth exceeded for {item_id} (possible cycle) — stopped exploding",
            item_id=item_id, source=source.value, source_ref=source_ref,
        ))
        return need_date

    item = ref.items.get(item_id)
    if item is None:
        exceptions.append(RawException(
            category="UNKNOWN_ITEM",
            message=f"Demand for unknown item {item_id} ({source_ref}) — skipped",
            item_id=item_id, source=source.value, source_ref=source_ref,
        ))
        return need_date

    # Net against on-hand stock first, then against supply already in flight.
    balance = ref.available.get(item_id, 0.0)
    if balance >= qty:
        ref.available[item_id] = balance - qty
        return today  # already on the shelf
    shortfall = qty - balance
    ref.available[item_id] = 0.0

    # Time-phased: a receipt that lands after this requirement is needed can't
    # cover it, so only consume receipts arriving on or before the need date.
    covered_by_receipt: date | None = None
    for receipt in ref.receipts.get(item_id, []):
        if shortfall <= 1e-9:
            break
        receipt_date, receipt_qty = receipt[0], receipt[1]
        if receipt_qty <= 0 or receipt_date > need_date:
            continue
        take = min(receipt_qty, shortfall)
        receipt[1] = receipt_qty - take
        shortfall -= take
        covered_by_receipt = max(covered_by_receipt or receipt_date, receipt_date)

    if shortfall <= 1e-9:
        # Fully covered by existing commitments — nothing new to plan.
        return covered_by_receipt or today

    if item.make_or_buy == MakeOrBuy.BUY:
        supplier_id, lead_time = ref.preferred_supplier.get(item_id, (None, item.default_lead_time_days))
        release_date = need_date - timedelta(days=lead_time)
        po_id = counter.next_po()
        expedite_days = max(0, (today - release_date).days)
        if expedite_days > 0:
            # Can't order in the past: the realistic arrival is today + lead time.
            arrival = today + timedelta(days=lead_time)
            exceptions.append(RawException(
                category="PAST_DUE_PO_RELEASE",
                message=(f"PO for {item_id} needed release {release_date} "
                          f"({expedite_days}d ago); ordering today lands {arrival}, "
                          f"{(arrival - need_date).days}d after it's needed"),
                item_id=item_id, source=source.value, source_ref=source_ref,
                order_id=po_id, days_late=expedite_days, need_date=need_date,
            ))
            release_date = today
        else:
            arrival = need_date
        planned.append(PlannedOrder(order_id=po_id, item_id=item_id, qty=shortfall,
                                     need_date=need_date, start_date=release_date, kind="PO",
                                     source=source, source_ref=source_ref, supplier_id=supplier_id,
                                     parent_wo_id=parent_wo_id, bom_level=depth,
                                     expedite_days=expedite_days))
        return arrival

    # MAKE item. Components must be planned *before* the parent is placed: the
    # parent cannot start until its material has arrived, so we need each
    # component's real availability date to use as a scheduling floor. The
    # components' own need-date is the parent's backward-derived target start.
    wo_id = counter.next_wo()
    capacity_delay = 0
    unmet_hours = 0.0
    late_days = 0
    ops = ref.routing_ops.get(item_id)

    target_start = (
        simulate_routing_backward(ledger, ops, need_date, shortfall)
        if ops
        else need_date - timedelta(days=item.default_lead_time_days or 7)
    )

    material_ready = today
    bom = ref.boms.get(item_id)
    if bom:
        for line in getattr(bom, "loaded_lines", []):
            comp_qty = shortfall * float(line.qty_per) * (1 + float(line.scrap_pct))
            comp_ready = _net_item(ref, line.component_item_id, comp_qty, target_start,
                                    source, source_ref, planned, consumptions, exceptions,
                                    ledger, today, counter, depth=depth + 1, parent_wo_id=wo_id)
            material_ready = max(material_ready, comp_ready)

    if ops:
        result = schedule_routing(ledger, ops, need_date, shortfall, today,
                                   earliest_start=material_ready,
                                   source=source.value, source_ref=source_ref)
        start_date = result.start_date
        end_date = result.end_date
        capacity_delay = result.capacity_delay_days
        unmet_hours = result.unmet_hours
        late_days = result.late_days
        consumptions.extend(result.consumptions)
        if unmet_hours > 0:
            exceptions.append(RawException(
                category="CAPACITY_INFEASIBLE",
                message=(f"{unmet_hours:.0f}h for {item_id} could not be placed anywhere in the "
                          f"planning horizon — capacity is structurally short, not just late"),
                item_id=item_id, source=source.value, source_ref=source_ref, order_id=wo_id,
                days_late=late_days, need_date=need_date,
            ))
        elif late_days > 0:
            # The order physically cannot finish by its due date. Attribute how
            # much of that is machine contention vs. sheer work content, since
            # the two have different remedies (resequence/overtime vs. subcontract).
            attribution = (f"{capacity_delay}d of it waiting on busy work centers"
                            if capacity_delay > 0 else "driven by work content, not contention")
            exceptions.append(RawException(
                category="CAPACITY_CONSTRAINED_LATE",
                message=(f"WO for {item_id} cannot finish before {end_date} — "
                          f"{late_days}d after its {need_date} due date ({attribution})"),
                item_id=item_id, source=source.value, source_ref=source_ref,
                order_id=wo_id, days_late=late_days, need_date=need_date,
            ))
    else:
        start_date = need_date - timedelta(days=item.default_lead_time_days or 7)
        end_date = need_date
        exceptions.append(RawException(
            category="NO_ROUTING",
            message=f"No routing for MAKE item {item_id} — used flat lead time fallback",
            item_id=item_id, source=source.value, source_ref=source_ref, order_id=wo_id,
        ))
        if start_date < today:
            late_days = (today - start_date).days
            exceptions.append(RawException(
                category="PAST_DUE_WO_START",
                message=(f"WO for {item_id} needs to start {start_date} "
                          f"({late_days}d past today) to hit {need_date}"),
                item_id=item_id, source=source.value, source_ref=source_ref,
                order_id=wo_id, days_late=late_days, need_date=need_date,
            ))

    planned.append(PlannedOrder(order_id=wo_id, item_id=item_id, qty=shortfall,
                                 need_date=need_date, start_date=start_date, kind="WO",
                                 source=source, source_ref=source_ref, parent_wo_id=parent_wo_id,
                                 bom_level=depth, expedite_days=late_days,
                                 capacity_delay_days=capacity_delay, unmet_hours=unmet_hours,
                                 projected_end=end_date))

    return end_date
