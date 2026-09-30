from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    ActionType,
    ExceptionCategory,
    ExceptionSeverity,
    ExceptionStatus,
)


class PlanException(Base):
    """A planner-actionable problem surfaced by a planning run.

    The planning engine is regenerative — it wipes and rebuilds planned supply
    on every run — but exception *triage state* must survive that. So
    exception_id is a deterministic key derived from what the problem is
    (category + item + demand ref) rather than a surrogate id, letting a
    re-run recognize the same problem and preserve an
    acknowledgement/snooze instead of resurrecting it as new.
    """

    __tablename__ = "plan_exceptions"

    exception_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    category: Mapped[ExceptionCategory] = mapped_column(Enum(ExceptionCategory), index=True)
    severity: Mapped[ExceptionSeverity] = mapped_column(Enum(ExceptionSeverity), index=True)
    status: Mapped[ExceptionStatus] = mapped_column(
        Enum(ExceptionStatus), default=ExceptionStatus.OPEN, index=True
    )

    message: Mapped[str] = mapped_column(Text)
    item_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    work_center_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    days_late: Mapped[int] = mapped_column(Integer, default=0)
    value_at_risk: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    need_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    snooze_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlanAction(Base):
    """Audit trail of planner decisions — what was changed, from what, to what.

    Without this there's no way to answer "who pulled this order in and why",
    and no way to show the cost impact of decisions over time.
    """

    __tablename__ = "plan_actions"

    action_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType))
    target_type: Mapped[str] = mapped_column(String(30), doc="WORK_ORDER / PURCHASE_ORDER / SALES_ORDER / EXCEPTION / WORK_CENTER")
    target_id: Mapped[str] = mapped_column(String(200))

    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), default="planner")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
