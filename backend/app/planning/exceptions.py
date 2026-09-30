"""Turn raw planning warnings into a ranked, persistent exception workbench.

Two things make this a workbench rather than a log:

1. **Business weighting.** Each exception carries the customer and the dollar
   value at risk (contract value / order revenue / overhaul estimate), so a
   planner triages by impact rather than by whatever the explosion happened to
   emit first.
2. **Stable identity across regens.** The planning engine wipes and rebuilds
   planned supply on every run, but exception_id is derived from what the
   problem *is* (category + item + demand ref), not from the order id. A
   re-run therefore recognizes the same problem and preserves an
   acknowledgement or snooze instead of resurrecting it as new.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.aftermarket import SalesOrder
from app.models.enums import (
    ExceptionCategory,
    ExceptionSeverity,
    ExceptionStatus,
    WorkOrderSource,
)
from app.models.exception import PlanException
from app.models.overhaul import OverhaulJob
from app.models.project import Project
from app.planning.capacity import WeeklyLoad
from app.planning.explode import RawException

# Past-due thresholds (days) that separate "tight" from "genuinely broken".
CRITICAL_DAYS = 14
HIGH_DAYS = 3
# A late order this valuable is critical regardless of how few days late.
CRITICAL_VALUE = 250_000.0


@dataclass
class DemandContext:
    """customer + total value for each root demand ref, so exceptions can be
    ranked by what they actually put at risk."""

    customer: dict[str, str]
    value: dict[str, float]


def load_demand_context(db: Session) -> DemandContext:
    customer: dict[str, str] = {}
    value: dict[str, float] = {}

    for p in db.query(Project).all():
        customer[p.project_id] = p.customer
        value[p.project_id] = float(p.contract_value or p.quoted_value or 0)

    for o in db.query(SalesOrder).all():
        customer[o.order_id] = o.customer
        value[o.order_id] = float(o.qty) * float(o.unit_price)

    for j in db.query(OverhaulJob).all():
        customer[j.job_id] = j.customer
        value[j.job_id] = float(j.estimated_value or 0)

    return DemandContext(customer=customer, value=value)


def _primary_ref(source_ref: str | None) -> str | None:
    """Bucketed demand carries refs like 'SO-000123 +4 more' — the first token
    is the representative order we can look customer/value up by."""
    if not source_ref:
        return None
    return source_ref.split(" ")[0]


def _severity(category: str, days_late: int, value_at_risk: float) -> ExceptionSeverity:
    if category in ("NO_ROUTING", "BOM_DEPTH_EXCEEDED", "UNKNOWN_ITEM"):
        return ExceptionSeverity.LOW  # data quality, not a schedule threat
    if category == "CAPACITY_INFEASIBLE":
        # Work that fits nowhere in the horizon is a structural shortfall —
        # no amount of resequencing fixes it, so it always escalates.
        return ExceptionSeverity.CRITICAL
    if category == "CAPACITY_OVERLOAD":
        return ExceptionSeverity.HIGH if days_late >= 4 else ExceptionSeverity.MEDIUM
    if days_late >= CRITICAL_DAYS or value_at_risk >= CRITICAL_VALUE:
        return ExceptionSeverity.CRITICAL
    if days_late >= HIGH_DAYS:
        return ExceptionSeverity.HIGH
    return ExceptionSeverity.MEDIUM


def build_exceptions(raw: list[RawException], capacity_report: list[WeeklyLoad],
                      ctx: DemandContext) -> list[dict]:
    """Collapse raw warnings + capacity overloads into deduplicated, enriched
    exception dicts keyed by a stable exception_id."""
    by_id: dict[str, dict] = {}

    for r in raw:
        ref = _primary_ref(r.source_ref)
        value = ctx.value.get(ref, 0.0) if ref else 0.0
        customer = ctx.customer.get(ref) if ref else None
        exception_id = f"{r.category}|{r.item_id or '-'}|{r.source_ref or '-'}"

        existing = by_id.get(exception_id)
        if existing and existing["days_late"] >= r.days_late:
            continue

        by_id[exception_id] = {
            "exception_id": exception_id,
            "category": ExceptionCategory(r.category),
            "severity": _severity(r.category, r.days_late, value),
            "message": r.message,
            "item_id": r.item_id,
            "source": r.source,
            "source_ref": r.source_ref,
            "customer": customer,
            "work_center_id": None,
            "days_late": r.days_late,
            "value_at_risk": value,
            "need_date": r.need_date,
        }

    # Capacity overload: aggregate to one exception per work center rather than
    # one per overloaded week — a planner acts on "this cell is oversubscribed",
    # not on 40 individual week rows.
    overloaded_by_wc: dict[str, list[WeeklyLoad]] = {}
    for w in capacity_report:
        if w.overloaded:
            overloaded_by_wc.setdefault(w.work_center_id, []).append(w)

    for wc_id, weeks in overloaded_by_wc.items():
        worst = max(weeks, key=lambda w: w.required_pct)
        total_excess = sum(w.excess_hours for w in weeks)
        exception_id = f"CAPACITY_OVERLOAD|{wc_id}"
        by_id[exception_id] = {
            "exception_id": exception_id,
            "category": ExceptionCategory.CAPACITY_OVERLOAD,
            "severity": _severity("CAPACITY_OVERLOAD", len(weeks), 0.0),
            "message": (
                f"{worst.work_center_name} oversubscribed in {len(weeks)} week(s), "
                f"{total_excess:.0f}h total excess pushed to earlier weeks; worst "
                f"{worst.week_start} wanted {worst.required_hours:.0f}h vs "
                f"{worst.available_hours:.0f}h available ({worst.required_pct:.0f}%)"
            ),
            "item_id": None,
            "source": None,
            "source_ref": None,
            "customer": None,
            "work_center_id": wc_id,
            "days_late": len(weeks),
            "value_at_risk": 0.0,
            "need_date": worst.week_start,
        }

    return list(by_id.values())


def upsert_exceptions(db: Session, exceptions: list[dict], today: date) -> dict[str, int]:
    """Merge this run's exceptions into the table, preserving triage state.

    - New problem -> inserted as OPEN.
    - Recurring problem -> refresh the facts (message/severity/days late) but
      keep ACKNOWLEDGED/SNOOZED so the planner isn't re-shown what they've
      already dealt with. An expired snooze reverts to OPEN.
    - Problem no longer produced by the plan -> auto-RESOLVED, since the
      underlying condition is gone.
    """
    incoming = {e["exception_id"]: e for e in exceptions}
    existing = {e.exception_id: e for e in db.query(PlanException).all()}
    now = datetime.now()

    created = 0
    updated = 0
    auto_resolved = 0

    for exc_id, data in incoming.items():
        row = existing.get(exc_id)
        if row is None:
            db.add(PlanException(**data, status=ExceptionStatus.OPEN,
                                  first_seen=now, last_seen=now))
            created += 1
            continue

        row.category = data["category"]
        row.severity = data["severity"]
        row.message = data["message"]
        row.customer = data["customer"]
        row.days_late = data["days_late"]
        row.value_at_risk = data["value_at_risk"]
        row.need_date = data["need_date"]
        row.work_center_id = data["work_center_id"]
        row.last_seen = now

        if row.status == ExceptionStatus.SNOOZED and row.snooze_until and row.snooze_until <= today:
            row.status = ExceptionStatus.OPEN
            row.snooze_until = None
        elif row.status == ExceptionStatus.RESOLVED:
            # It came back — a previously resolved condition reappearing is new news.
            row.status = ExceptionStatus.OPEN
        updated += 1

    for exc_id, row in existing.items():
        if exc_id not in incoming and row.status != ExceptionStatus.RESOLVED:
            row.status = ExceptionStatus.RESOLVED
            row.last_seen = now
            auto_resolved += 1

    db.flush()
    return {"created": created, "updated": updated, "auto_resolved": auto_resolved}
