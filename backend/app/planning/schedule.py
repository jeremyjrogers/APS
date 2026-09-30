"""Finite-capacity backward scheduling.

The scheduler maintains a *ledger* of remaining hours per work center per day
and decrements it as orders are placed. Once a day is full, later orders are
pushed to earlier days — so two orders can never claim the same machine hour,
and a work center can never be scheduled above 100%.

This is the difference between "here is a plan that assumes infinite
machines" and "here is a plan the shop could actually run". The cost of
honesty is that some orders no longer fit before their due date; those surface
as capacity-constrained exceptions rather than as impossible utilization
percentages.

Both numbers are still computed for every operation:

- **required** — what the order would need with unlimited capacity
- **scheduled** — where it actually landed once contention was resolved

The gap between them is the capacity-driven delay, which is what tells a
planner whether an order is late because of a long lead time or because
another job was already using the machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.reference import CapacityCalendar


@dataclass
class OperationConsumption:
    work_center_id: str
    day: date
    hours: float
    source: str = ""
    source_ref: str = ""


@dataclass
class ScheduleResult:
    start_date: date
    #: When the work actually finishes. Under forward scheduling this can be
    #: after the due date — that is the honest answer, and the number a
    #: planner needs to quote a realistic date to the customer.
    end_date: date
    #: "BACKWARD" when the order fits before its due date, "FORWARD" when it
    #: had to be pushed out from today because it did not.
    direction: str = "BACKWARD"
    consumptions: list[OperationConsumption] = field(default_factory=list)
    #: Hours that could not be placed inside the planning horizon at all.
    unmet_hours: float = 0.0
    #: Days earlier than an unconstrained plan would have started, caused
    #: purely by other orders already holding the capacity.
    capacity_delay_days: int = 0
    #: Days the projected finish falls after the due date. 0 = on time.
    late_days: int = 0


class CapacityLedger:
    """Mutable remaining-capacity map. Consuming hours removes them."""

    def __init__(self, calendar: dict[tuple[str, date], float]) -> None:
        self.baseline = dict(calendar)
        self.remaining = dict(calendar)
        days = [d for _, d in calendar]
        self.horizon_start = min(days) if days else date.today()
        self.horizon_end = max(days) if days else date.today()
        #: Unconstrained demand per (work_center, day), for required-vs-scheduled
        #: reporting. Tracked even when the hours don't fit.
        self.required: dict[tuple[str, date], float] = {}

    def available(self, work_center_id: str, day: date) -> float:
        if day < self.horizon_start or day > self.horizon_end:
            return 0.0
        return self.remaining.get((work_center_id, day), 0.0)

    def baseline_hours(self, work_center_id: str, day: date) -> float:
        if day < self.horizon_start or day > self.horizon_end:
            return 0.0
        return self.baseline.get((work_center_id, day), 0.0)

    def note_required(self, work_center_id: str, day: date, hours: float) -> None:
        # Badly-overdue orders can compute an unconstrained "wants to happen"
        # date before the calendar's earliest row (elapsed capacity is real, but
        # the calendar only covers today-forward), or scheduling can otherwise
        # land outside the seeded horizon. Clamp into range rather than
        # recording demand into a week with zero available hours — that
        # produces a divide-by-zero (Infinity) in the capacity report, which
        # serializes as JSON null and crashes any consumer that formats it as
        # a number.
        clamped = min(max(day, self.horizon_start), self.horizon_end)
        key = (work_center_id, clamped)
        self.required[key] = self.required.get(key, 0.0) + hours

    def consume_backward(self, work_center_id: str, end_date: date, hours_needed: float,
                          source: str = "", source_ref: str = ""
                          ) -> tuple[date, list[OperationConsumption], float]:
        """Take `hours_needed` from this work center walking back from end_date,
        decrementing remaining capacity. Returns (start_date, consumptions,
        unmet_hours)."""
        consumptions: list[OperationConsumption] = []
        day = end_date
        remaining = hours_needed

        while remaining > 1e-9:
            day -= timedelta(days=1)
            if day < self.horizon_start:
                # Ran out of horizon before finding room — report what's unplaceable.
                return day, consumptions, remaining
            avail = self.available(work_center_id, day)
            if avail <= 0:
                continue
            used = min(avail, remaining)
            self.remaining[(work_center_id, day)] = avail - used
            consumptions.append(OperationConsumption(
                work_center_id=work_center_id, day=day, hours=used,
                source=source, source_ref=source_ref,
            ))
            remaining -= used

        return day, consumptions, 0.0

    def simulate_backward(self, work_center_id: str, end_date: date, hours_needed: float,
                           finite: bool = False) -> date:
        """Where this operation would start, without mutating the ledger.

        finite=False uses baseline capacity (ignoring other orders) to answer
        "how long does this take on its own", which is the reference point for
        attributing capacity-driven delay. finite=True respects what's already
        booked, and is used to test whether an order fits before its due date
        before committing to a direction.
        """
        day = end_date
        remaining = hours_needed
        while remaining > 1e-9:
            day -= timedelta(days=1)
            if day < self.horizon_start:
                return day
            avail = self.available(work_center_id, day) if finite else self.baseline_hours(work_center_id, day)
            if avail <= 0:
                continue
            remaining -= min(avail, remaining)
        return day

    def consume_forward(self, work_center_id: str, start_date: date, hours_needed: float,
                         source: str = "", source_ref: str = ""
                         ) -> tuple[date, list[OperationConsumption], float]:
        """Take `hours_needed` walking forward from start_date. Used when an
        order cannot fit before its due date: rather than inventing capacity in
        the past, push it out and report when it will genuinely finish."""
        consumptions: list[OperationConsumption] = []
        day = start_date - timedelta(days=1)
        remaining = hours_needed

        while remaining > 1e-9:
            day += timedelta(days=1)
            if day > self.horizon_end:
                return day, consumptions, remaining
            avail = self.available(work_center_id, day)
            if avail <= 0:
                continue
            used = min(avail, remaining)
            self.remaining[(work_center_id, day)] = avail - used
            consumptions.append(OperationConsumption(
                work_center_id=work_center_id, day=day, hours=used,
                source=source, source_ref=source_ref,
            ))
            remaining -= used

        return day, consumptions, 0.0


def load_calendar(db: Session) -> dict[tuple[str, date], float]:
    """(work_center_id, date) -> available_hours, for every seeded calendar day."""
    rows = db.query(CapacityCalendar).all()
    return {(r.work_center_id, r.calendar_date): float(r.available_hours) for r in rows}


def simulate_routing_backward(ledger: CapacityLedger, operations: list[tuple[int, str, float, float]],
                               due_date: date, qty: float, finite: bool = True) -> date:
    """Target start date for a routing, without committing capacity. Used to
    give components a need-date before the parent is actually placed."""
    cursor = due_date
    for _seq, wc_id, setup_hours, run_hours_per_unit in sorted(operations, key=lambda o: o[0], reverse=True):
        cursor = ledger.simulate_backward(wc_id, cursor, setup_hours + run_hours_per_unit * qty,
                                           finite=finite)
    return cursor


def schedule_routing(
    ledger: CapacityLedger,
    operations: list[tuple[int, str, float, float]],  # (seq, work_center_id, setup_hours, run_hours_per_unit)
    due_date: date,
    qty: float,
    today: date,
    earliest_start: date | None = None,
    source: str = "",
    source_ref: str = "",
) -> ScheduleResult:
    """Schedule a routing against finite capacity.

    Tries backward from the due date first, which is what you want when the
    order fits. If backward scheduling would require starting before
    `earliest_start` — either because the capacity has already elapsed, or
    because the components won't have arrived yet — it forward-schedules from
    that floor instead. A plan that starts work last month, or before its
    material exists, is not a plan; the useful output in that case is the real
    projected finish date and how late it makes the order.
    """
    ops_desc = sorted(operations, key=lambda o: o[0], reverse=True)
    ops_asc = sorted(operations, key=lambda o: o[0])
    floor = max(today, earliest_start) if earliest_start else today

    # Reference point: how early this would start with no contention at all,
    # and — per operation — where each hour of it "wants" to land. This backward
    # walk (from due_date, ignoring other orders) is what note_required uses
    # for BOTH branches below.
    #
    # It must not use the forward-execution floor for that instead: when an
    # order can't fit before its due date, dozens of unrelated orders often
    # share the same floor (today, or the same material-ready date), which
    # would collapse all of their hours onto one day — one order's four hours
    # of work reported as "hundreds of hours required this week." The
    # due-date-anchored walk keeps each order's contribution spread across the
    # weeks it actually belongs to, consistent with the backward-execution case.
    cursor = due_date
    for _seq, wc_id, setup_hours, run_hours_per_unit in ops_desc:
        hours_needed = setup_hours + run_hours_per_unit * qty
        ledger.note_required(wc_id, cursor, hours_needed)
        cursor = ledger.simulate_backward(wc_id, cursor, hours_needed, finite=False)
    unconstrained_end = cursor

    # Dry run against real remaining capacity to pick a direction.
    trial_end = simulate_routing_backward(ledger, operations, due_date, qty, finite=True)

    all_consumptions: list[OperationConsumption] = []
    total_unmet = 0.0

    if trial_end >= floor:
        cursor = due_date
        for _seq, wc_id, setup_hours, run_hours_per_unit in ops_desc:
            hours_needed = setup_hours + run_hours_per_unit * qty
            start, consumptions, unmet = ledger.consume_backward(
                wc_id, cursor, hours_needed, source, source_ref)
            all_consumptions.extend(consumptions)
            total_unmet += unmet
            cursor = start
        start_date, end_date, direction = cursor, due_date, "BACKWARD"
    else:
        cursor = floor
        for _seq, wc_id, setup_hours, run_hours_per_unit in ops_asc:
            hours_needed = setup_hours + run_hours_per_unit * qty
            finish, consumptions, unmet = ledger.consume_forward(
                wc_id, cursor, hours_needed, source, source_ref)
            all_consumptions.extend(consumptions)
            total_unmet += unmet
            cursor = finish
        start_date, end_date, direction = floor, cursor, "FORWARD"

    # Capacity delay = how much longer the job *spans* than the work actually
    # takes. Comparing start dates instead is unbounded and meaningless: when
    # the finite backward trial exhausts the horizon it lands at horizon_start,
    # producing "349 days of contention" on a job with four hours of work.
    # Elapsed-span minus work-span is bounded by the order's own schedule.
    work_span = max(0, (due_date - unconstrained_end).days)
    actual_span = max(0, (end_date - start_date).days)
    capacity_delay = max(0, actual_span - work_span)
    late_days = max(0, (end_date - due_date).days)

    return ScheduleResult(
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        consumptions=all_consumptions,
        unmet_hours=total_unmet,
        capacity_delay_days=capacity_delay,
        late_days=late_days,
    )
