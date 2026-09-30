"""Planning engine orchestrator: gather demand -> explode/net -> backward
schedule -> persist planned supply -> report capacity feasibility.

Regenerative: each run clears previously PLANNED (not yet RELEASED) work
orders and purchase orders and rebuilds them from scratch, same as a classic
MRP regen. RELEASED/IN_PROGRESS/COMPLETE orders are left alone since those
represent committed reality, not a plan.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.bom import Routing
from app.models.enums import ExceptionStatus, PurchaseOrderStatus, WorkOrderStatus
from app.models.exception import PlanException
from app.models.supply import PurchaseOrder, PurchaseOrderLine, WorkOrder
from app.planning.capacity import build_capacity_report
from app.planning.demand import gather_demand
from app.planning.exceptions import build_exceptions, load_demand_context, upsert_exceptions
from app.planning.explode import PlannedOrder, run_mrp
from app.planning.schedule import load_calendar


def clear_planned(db: Session) -> None:
    planned_po_ids = [po.po_id for po in db.query(PurchaseOrder).filter(
        PurchaseOrder.status == PurchaseOrderStatus.PLANNED).all()]
    if planned_po_ids:
        db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id.in_(planned_po_ids)).delete(
            synchronize_session=False)
        db.query(PurchaseOrder).filter(PurchaseOrder.po_id.in_(planned_po_ids)).delete(
            synchronize_session=False)
    db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.PLANNED).delete(synchronize_session=False)
    db.flush()


def persist_planned_orders(db: Session, planned: list[PlannedOrder]) -> dict[str, int]:
    routing_id_by_item = {r.item_id: r.routing_id for r in db.query(Routing).all()}

    wo_count = 0
    po_count = 0
    for p in planned:
        if p.kind == "WO":
            wo_count += 1
            db.add(WorkOrder(
                wo_id=p.order_id, item_id=p.item_id, qty=p.qty,
                routing_id=routing_id_by_item.get(p.item_id), source=p.source,
                source_ref=p.source_ref, start_date=p.start_date, due_date=p.need_date,
                status=WorkOrderStatus.PLANNED, parent_wo_id=p.parent_wo_id,
                bom_level=p.bom_level, expedite_days=p.expedite_days,
                capacity_delay_days=p.capacity_delay_days,
                projected_end=p.projected_end,
            ))
        else:
            po_count += 1
            db.add(PurchaseOrder(
                po_id=p.order_id, supplier_id=p.supplier_id,
                status=PurchaseOrderStatus.PLANNED, parent_wo_id=p.parent_wo_id,
                source=p.source, source_ref=p.source_ref, bom_level=p.bom_level,
                expedite_days=p.expedite_days,
            ))
            db.flush()
            db.add(PurchaseOrderLine(po_id=p.order_id, item_id=p.item_id, qty=p.qty,
                                      due_date=p.need_date))
    db.flush()
    return {"work_orders": wo_count, "purchase_orders": po_count}


def build_capacity_heatmap(capacity_report: list, today: date, weeks_before: int = 2,
                            weeks_after: int = 16) -> list[dict]:
    """Group the flat weekly report by work center for charting: a bounded
    window of weeks around today (readable heatmap) plus annual totals (the
    true feasibility picture, not just what's visible in the window)."""
    window_start = today - timedelta(days=today.weekday() + weeks_before * 7)
    window_end = window_start + timedelta(days=(weeks_before + weeks_after) * 7)

    by_wc: dict[str, dict] = {}
    for r in capacity_report:
        wc = by_wc.setdefault(r.work_center_id, {
            "work_center_id": r.work_center_id, "work_center_name": r.work_center_name,
            "area": r.area, "weeks": [], "annual_load_hours": 0.0,
            "annual_available_hours": 0.0, "annual_required_hours": 0.0,
            "overloaded_weeks": 0, "total_excess_hours": 0.0,
        })
        wc["annual_load_hours"] += r.load_hours
        wc["annual_available_hours"] += r.available_hours
        wc["annual_required_hours"] += r.required_hours
        if r.overloaded:
            wc["overloaded_weeks"] += 1
            wc["total_excess_hours"] += r.excess_hours
        if window_start <= r.week_start < window_end:
            wc["weeks"].append({
                "week_start": r.week_start.isoformat(), "load_hours": r.load_hours,
                "available_hours": r.available_hours, "utilization_pct": r.utilization_pct,
                "required_hours": r.required_hours, "required_pct": r.required_pct,
                "excess_hours": r.excess_hours,
            })

    result = []
    for wc in by_wc.values():
        wc["weeks"].sort(key=lambda w: w["week_start"])
        wc["annual_load_hours"] = round(wc["annual_load_hours"], 1)
        wc["annual_available_hours"] = round(wc["annual_available_hours"], 1)
        wc["annual_required_hours"] = round(wc["annual_required_hours"], 1)
        wc["total_excess_hours"] = round(wc["total_excess_hours"], 1)
        avail = wc["annual_available_hours"]
        wc["annual_utilization_pct"] = round(100 * wc["annual_load_hours"] / avail, 1) if avail > 0 else 0.0
        wc["annual_required_pct"] = round(100 * wc["annual_required_hours"] / avail, 1) if avail > 0 else 0.0
        result.append(wc)
    result.sort(key=lambda wc: -wc["annual_required_pct"])
    return result


def run_planning(db: Session, today: date | None = None) -> dict:
    today = today or date.today()

    clear_planned(db)

    demands = gather_demand(db, today)
    calendar = load_calendar(db)
    planned, consumptions, raw_exceptions, ledger = run_mrp(db, demands, calendar, today)
    persisted = persist_planned_orders(db, planned)
    demand_horizon_end = max((d.need_date for d in demands), default=today)
    capacity_report = build_capacity_report(db, consumptions, calendar, ledger,
                                             report_end=demand_horizon_end)

    overloaded = [r for r in capacity_report if r.overloaded]
    overloaded.sort(key=lambda r: r.load_hours - r.available_hours, reverse=True)
    heatmap = build_capacity_heatmap(capacity_report, today)

    ctx = load_demand_context(db)
    enriched = build_exceptions(raw_exceptions, capacity_report, ctx)
    exception_stats = upsert_exceptions(db, enriched, today)

    open_count = db.query(PlanException).filter(
        PlanException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ACKNOWLEDGED])
    ).count()

    db.commit()

    return {
        "run_date": today.isoformat(),
        "demand_count": len(demands),
        "planned_work_orders": persisted["work_orders"],
        "planned_purchase_orders": persisted["purchase_orders"],
        "exceptions": {**exception_stats, "open": open_count, "total": len(enriched)},
        "capacity_weeks_evaluated": len(capacity_report),
        "overloaded_week_count": len(overloaded),
        "capacity_by_work_center": heatmap,
        "top_overloaded": [
            {
                "work_center_id": r.work_center_id,
                "work_center_name": r.work_center_name,
                "area": r.area,
                "week_start": r.week_start.isoformat(),
                "load_hours": r.load_hours,
                "available_hours": r.available_hours,
                "utilization_pct": r.utilization_pct,
            }
            for r in overloaded[:20]
        ],
    }
