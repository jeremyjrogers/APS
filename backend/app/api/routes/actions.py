"""The write path: exception triage and planner actions.

Every mutation records a PlanAction audit row (what changed, from what, to
what) so decisions are traceable and their cumulative impact is measurable.

Actions that change the supply picture (release, cancel) survive the next
regenerative planning run, because run_planning only clears PLANNED orders —
a RELEASED order is a commitment, not a suggestion.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.aftermarket import SalesOrder
from app.models.enums import (
    ActionType,
    ExceptionSeverity,
    ExceptionStatus,
    PurchaseOrderStatus,
    WorkOrderStatus,
)
from app.models.exception import PlanAction, PlanException
from app.models.reference import CapacityCalendar
from app.models.supply import PurchaseOrder, PurchaseOrderLine, WorkOrder

router = APIRouter(tags=["actions"])


def _log(db: Session, action_type: ActionType, target_type: str, target_id: str,
         before: str | None, after: str | None, note: str | None = None) -> PlanAction:
    action = PlanAction(
        action_type=action_type, target_type=target_type, target_id=target_id,
        before_value=before, after_value=after, note=note,
    )
    db.add(action)
    return action


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


@router.get("/exceptions")
def list_exceptions(
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    q = db.query(PlanException)
    if status:
        q = q.filter(PlanException.status == ExceptionStatus(status.upper()))
    else:
        # Default view is the planner's actual queue, not the archive.
        q = q.filter(PlanException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ACKNOWLEDGED]))
    if severity:
        q = q.filter(PlanException.severity == ExceptionSeverity(severity.upper()))
    if category:
        q = q.filter(PlanException.category == category.upper())
    if source:
        q = q.filter(PlanException.source == source.upper())

    total = q.count()
    total_value = q.with_entities(func.coalesce(func.sum(PlanException.value_at_risk), 0)).scalar()

    severity_rank = {
        ExceptionSeverity.CRITICAL: 0, ExceptionSeverity.HIGH: 1,
        ExceptionSeverity.MEDIUM: 2, ExceptionSeverity.LOW: 3,
    }
    rows = q.all()
    rows.sort(key=lambda e: (severity_rank[e.severity], -float(e.value_at_risk), -e.days_late))
    page = rows[offset: offset + limit]

    return {
        "total": total,
        "total_value_at_risk": float(total_value),
        "rows": [
            {
                "exception_id": e.exception_id,
                "category": e.category.value,
                "severity": e.severity.value,
                "status": e.status.value,
                "message": e.message,
                "item_id": e.item_id,
                "source": e.source,
                "source_ref": e.source_ref,
                "customer": e.customer,
                "work_center_id": e.work_center_id,
                "days_late": e.days_late,
                "value_at_risk": float(e.value_at_risk),
                "need_date": e.need_date.isoformat() if e.need_date else None,
                "snooze_until": e.snooze_until.isoformat() if e.snooze_until else None,
                "note": e.note,
            }
            for e in page
        ],
    }


@router.get("/exceptions/summary")
def exceptions_summary(db: Session = Depends(get_db)) -> dict:
    q = db.query(PlanException).filter(
        PlanException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ACKNOWLEDGED])
    )
    by_severity: dict[str, dict] = {}
    for e in q.all():
        entry = by_severity.setdefault(e.severity.value, {"count": 0, "value_at_risk": 0.0})
        entry["count"] += 1
        entry["value_at_risk"] += float(e.value_at_risk)
    return {"by_severity": by_severity}


class ExceptionUpdate(BaseModel):
    note: str | None = None
    snooze_days: int = Field(default=7, ge=1, le=90)


@router.post("/exceptions/{exception_id}/acknowledge")
def acknowledge_exception(exception_id: str, body: ExceptionUpdate | None = None,
                           db: Session = Depends(get_db)) -> dict:
    e = _get_exception(db, exception_id)
    before = e.status.value
    e.status = ExceptionStatus.ACKNOWLEDGED
    if body and body.note:
        e.note = body.note
    _log(db, ActionType.ACKNOWLEDGE_EXCEPTION, "EXCEPTION", exception_id, before,
         e.status.value, body.note if body else None)
    db.commit()
    return {"exception_id": exception_id, "status": e.status.value}


@router.post("/exceptions/{exception_id}/snooze")
def snooze_exception(exception_id: str, body: ExceptionUpdate | None = None,
                      db: Session = Depends(get_db)) -> dict:
    e = _get_exception(db, exception_id)
    before = e.status.value
    days = body.snooze_days if body else 7
    e.status = ExceptionStatus.SNOOZED
    e.snooze_until = date.today() + timedelta(days=days)
    if body and body.note:
        e.note = body.note
    _log(db, ActionType.SNOOZE_EXCEPTION, "EXCEPTION", exception_id, before,
         f"SNOOZED until {e.snooze_until}", body.note if body else None)
    db.commit()
    return {"exception_id": exception_id, "status": e.status.value,
            "snooze_until": e.snooze_until.isoformat()}


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(exception_id: str, body: ExceptionUpdate | None = None,
                       db: Session = Depends(get_db)) -> dict:
    e = _get_exception(db, exception_id)
    before = e.status.value
    e.status = ExceptionStatus.RESOLVED
    if body and body.note:
        e.note = body.note
    _log(db, ActionType.RESOLVE_EXCEPTION, "EXCEPTION", exception_id, before,
         e.status.value, body.note if body else None)
    db.commit()
    return {"exception_id": exception_id, "status": e.status.value}


def _get_exception(db: Session, exception_id: str) -> PlanException:
    e = db.query(PlanException).filter(PlanException.exception_id == exception_id).one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")
    return e


# --------------------------------------------------------------------------
# Order actions
# --------------------------------------------------------------------------


class RescheduleBody(BaseModel):
    due_date: date
    note: str | None = None


class ExpediteBody(BaseModel):
    pull_in_days: int = Field(ge=1, le=180)
    note: str | None = None


@router.post("/supply/work-orders/{wo_id}/reschedule")
def reschedule_work_order(wo_id: str, body: RescheduleBody, db: Session = Depends(get_db)) -> dict:
    wo = _get_wo(db, wo_id)
    before = f"start={wo.start_date} due={wo.due_date}"
    span = (wo.due_date - wo.start_date).days
    wo.due_date = body.due_date
    wo.start_date = body.due_date - timedelta(days=span)
    wo.expedite_days = max(0, (date.today() - wo.start_date).days)
    _log(db, ActionType.RESCHEDULE, "WORK_ORDER", wo_id, before,
         f"start={wo.start_date} due={wo.due_date}", body.note)
    db.commit()
    return _wo_dict(wo)


@router.post("/supply/work-orders/{wo_id}/expedite")
def expedite_work_order(wo_id: str, body: ExpediteBody, db: Session = Depends(get_db)) -> dict:
    """Compress the build window without moving the due date — models paying
    for overtime/priority rather than shipping late."""
    wo = _get_wo(db, wo_id)
    before = f"start={wo.start_date} expedite_days={wo.expedite_days}"
    wo.start_date = wo.start_date + timedelta(days=body.pull_in_days)
    if wo.start_date > wo.due_date:
        wo.start_date = wo.due_date
    wo.expedite_days = max(0, (date.today() - wo.start_date).days)
    _log(db, ActionType.EXPEDITE, "WORK_ORDER", wo_id, before,
         f"start={wo.start_date} expedite_days={wo.expedite_days}", body.note)
    db.commit()
    return _wo_dict(wo)


@router.post("/supply/work-orders/{wo_id}/release")
def release_work_order(wo_id: str, db: Session = Depends(get_db)) -> dict:
    wo = _get_wo(db, wo_id)
    before = wo.status.value
    wo.status = WorkOrderStatus.RELEASED
    _log(db, ActionType.RELEASE, "WORK_ORDER", wo_id, before, wo.status.value,
         "Released to the floor — survives future planning regens")
    db.commit()
    return _wo_dict(wo)


@router.post("/supply/purchase-orders/{po_id}/release")
def release_purchase_order(po_id: str, db: Session = Depends(get_db)) -> dict:
    po = _get_po(db, po_id)
    before = po.status.value
    po.status = PurchaseOrderStatus.RELEASED
    _log(db, ActionType.RELEASE, "PURCHASE_ORDER", po_id, before, po.status.value,
         "Released to supplier — survives future planning regens")
    db.commit()
    return {"po_id": po.po_id, "status": po.status.value}


@router.post("/supply/purchase-orders/{po_id}/reschedule")
def reschedule_purchase_order(po_id: str, body: RescheduleBody, db: Session = Depends(get_db)) -> dict:
    po = _get_po(db, po_id)
    lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id == po_id).all()
    before = ", ".join(f"{line.item_id}:{line.due_date}" for line in lines)
    for line in lines:
        line.due_date = body.due_date
    _log(db, ActionType.RESCHEDULE, "PURCHASE_ORDER", po_id, before,
         f"all lines due {body.due_date}", body.note)
    db.commit()
    return {"po_id": po.po_id, "due_date": body.due_date.isoformat()}


class PriorityBody(BaseModel):
    priority: int = Field(ge=1, le=10)
    note: str | None = None


@router.post("/demand/sales-orders/{order_id}/priority")
def change_priority(order_id: str, body: PriorityBody, db: Session = Depends(get_db)) -> dict:
    so = db.query(SalesOrder).filter(SalesOrder.order_id == order_id).one_or_none()
    if so is None:
        raise HTTPException(status_code=404, detail=f"Sales order {order_id} not found")
    before = str(so.priority)
    so.priority = body.priority
    _log(db, ActionType.CHANGE_PRIORITY, "SALES_ORDER", order_id, before,
         str(body.priority), body.note)
    db.commit()
    return {"order_id": order_id, "priority": so.priority}


class CapacityBody(BaseModel):
    work_center_id: str
    week_start: date
    daily_hours: float = Field(gt=0, le=24)
    note: str | None = None


@router.post("/reference/capacity")
def adjust_capacity(body: CapacityBody, db: Session = Depends(get_db)) -> dict:
    """Add a shift / overtime for one work center for one week, then rerun
    planning to see whether the overload actually clears."""
    days = [body.week_start + timedelta(days=i) for i in range(5)]
    rows = db.query(CapacityCalendar).filter(
        CapacityCalendar.work_center_id == body.work_center_id,
        CapacityCalendar.calendar_date.in_(days),
    ).all()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No calendar rows for {body.work_center_id} week of {body.week_start}",
        )
    before = f"{sum(float(r.available_hours) for r in rows):.1f}h/week"
    for r in rows:
        r.available_hours = body.daily_hours
    after = f"{body.daily_hours * len(rows):.1f}h/week"
    _log(db, ActionType.ADJUST_CAPACITY, "WORK_CENTER",
         f"{body.work_center_id}@{body.week_start}", before, after, body.note)
    db.commit()
    return {"work_center_id": body.work_center_id, "week_start": body.week_start.isoformat(),
            "before": before, "after": after}


@router.get("/actions")
def list_actions(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    q = db.query(PlanAction).order_by(PlanAction.created_at.desc(), PlanAction.action_id.desc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "rows": [
            {
                "action_id": a.action_id, "action_type": a.action_type.value,
                "target_type": a.target_type, "target_id": a.target_id,
                "before_value": a.before_value, "after_value": a.after_value,
                "note": a.note, "actor": a.actor,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
    }


def _get_wo(db: Session, wo_id: str) -> WorkOrder:
    wo = db.query(WorkOrder).filter(WorkOrder.wo_id == wo_id).one_or_none()
    if wo is None:
        raise HTTPException(status_code=404, detail=f"Work order {wo_id} not found")
    return wo


def _get_po(db: Session, po_id: str) -> PurchaseOrder:
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail=f"Purchase order {po_id} not found")
    return po


def _wo_dict(wo: WorkOrder) -> dict:
    return {
        "wo_id": wo.wo_id, "item_id": wo.item_id, "qty": float(wo.qty),
        "start_date": wo.start_date.isoformat(), "due_date": wo.due_date.isoformat(),
        "status": wo.status.value, "expedite_days": wo.expedite_days,
    }
