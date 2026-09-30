from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PurchaseOrderStatus, WorkOrderSource, WorkOrderStatus


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.PLANNED
    )

    # Pegging — POs are always leaves (BUY items don't explode further), so
    # they peg to the WO that consumes them plus the root demand.
    parent_wo_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    source: Mapped[WorkOrderSource | None] = mapped_column(Enum(WorkOrderSource), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bom_level: Mapped[int] = mapped_column(Integer, default=0)
    expedite_days: Mapped[int] = mapped_column(Integer, default=0)

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.po_id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    qty: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[date] = mapped_column(Date)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    wo_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    qty: Mapped[float] = mapped_column(Numeric(12, 2))
    routing_id: Mapped[int | None] = mapped_column(ForeignKey("routings.routing_id"), nullable=True)
    source: Mapped[WorkOrderSource] = mapped_column(Enum(WorkOrderSource))
    source_ref: Mapped[str | None] = mapped_column(
        String(30), nullable=True, doc="project_id / order_id / job_id that generated this WO"
    )
    start_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[WorkOrderStatus] = mapped_column(Enum(WorkOrderStatus), default=WorkOrderStatus.PLANNED)

    # Pegging: which WO's BOM explosion created this one, and how deep. Together
    # with source_ref (the root independent demand) this is what makes
    # "why is this order late?" answerable by walking the chain.
    parent_wo_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    bom_level: Mapped[int] = mapped_column(Integer, default=0)
    # Days the plan would need to start before today to hit the due date; >0
    # means infeasible as planned and needs expediting.
    expedite_days: Mapped[int] = mapped_column(Integer, default=0)
    # Of expedite_days, how many come from waiting on a busy work center rather
    # than from lead time — the two have different remedies.
    capacity_delay_days: Mapped[int] = mapped_column(Integer, default=0)
    # Finite-capacity projected completion. When this is later than due_date the
    # order genuinely cannot be delivered on time as currently planned.
    projected_end: Mapped[date | None] = mapped_column(Date, nullable=True)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    location: Mapped[str] = mapped_column(String(50), default="MAIN")
    qty_on_hand: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    qty_allocated: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
