"""Capacity report: what the plan *wanted* vs what it could actually schedule.

Under finite scheduling, scheduled load can never exceed available capacity —
so utilization alone would always look healthy and hide the real problem.
The signal instead lives in the gap between two numbers:

- **required** — hours demanded in a week if capacity were unlimited
- **scheduled** — hours actually placed there once contention was resolved

`required > available` is an oversubscribed week. The excess didn't vanish; it
was pushed to earlier weeks (or off the horizon entirely), which is what
makes orders late. This is the classic rough-cut capacity view, and it's the
number to act on when deciding where to add a shift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.reference import WorkCenter
from app.planning.schedule import CapacityLedger, OperationConsumption


# Sentinel for "demand exists but available_hours is 0" — never emit float
# ('inf'). Python's json module happily encodes it, but FastAPI's
# jsonable_encoder silently rewrites it to null (a documented but easy-to-miss
# behavior), and a consumer calling e.g. .toFixed() on that null crashes.
UNBOUNDED_PCT = 9999.0


@dataclass
class WeeklyLoad:
    work_center_id: str
    work_center_name: str
    area: str
    week_start: date
    load_hours: float  # finite/scheduled
    available_hours: float
    required_hours: float  # unconstrained demand

    @property
    def utilization_pct(self) -> float:
        """How full the machine actually is — capped by construction at 100%."""
        if self.available_hours <= 0:
            return 0.0 if self.load_hours == 0 else UNBOUNDED_PCT
        return round(100.0 * self.load_hours / self.available_hours, 1)

    @property
    def required_pct(self) -> float:
        """How much was wanted. Above 100% means oversubscribed."""
        if self.available_hours <= 0:
            return 0.0 if self.required_hours == 0 else UNBOUNDED_PCT
        return round(100.0 * self.required_hours / self.available_hours, 1)

    @property
    def overloaded(self) -> bool:
        return self.required_hours > self.available_hours

    @property
    def excess_hours(self) -> float:
        return round(max(0.0, self.required_hours - self.available_hours), 1)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_capacity_report(db: Session, consumptions: list[OperationConsumption],
                           calendar: dict[tuple[str, date], float],
                           ledger: CapacityLedger | None = None,
                           report_end: date | None = None) -> list[WeeklyLoad]:
    """`report_end` bounds the report to the window that actually has demand.

    The calendar deliberately runs well past the demand horizon so
    forward-scheduled late work has room to land, but counting those empty
    trailing weeks as available capacity deflates every utilization figure —
    the same denominator mistake that once made a saturated cell look
    two-thirds idle.
    """
    work_centers = {wc.work_center_id: wc for wc in db.query(WorkCenter).all()}

    load: dict[tuple[str, date], float] = {}
    for c in consumptions:
        key = (c.work_center_id, _week_start(c.day))
        load[key] = load.get(key, 0.0) + c.hours

    required: dict[tuple[str, date], float] = {}
    if ledger is not None:
        for (wc_id, day), hours in ledger.required.items():
            key = (wc_id, _week_start(day))
            required[key] = required.get(key, 0.0) + hours

    available: dict[tuple[str, date], float] = {}
    for (wc_id, day), hours in calendar.items():
        key = (wc_id, _week_start(day))
        available[key] = available.get(key, 0.0) + hours

    cutoff = _week_start(report_end) if report_end else None

    all_keys = set(load) | set(available) | set(required)
    report = []
    for wc_id, week_start in all_keys:
        wc = work_centers.get(wc_id)
        if wc is None:
            continue
        if cutoff and week_start > cutoff:
            continue
        report.append(WeeklyLoad(
            work_center_id=wc_id, work_center_name=wc.name, area=wc.area.value,
            week_start=week_start,
            load_hours=round(load.get((wc_id, week_start), 0.0), 1),
            available_hours=round(available.get((wc_id, week_start), 0.0), 1),
            required_hours=round(required.get((wc_id, week_start), 0.0), 1),
        ))

    report.sort(key=lambda r: (r.week_start, r.work_center_id))
    return report
