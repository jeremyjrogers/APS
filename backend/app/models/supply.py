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


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    location: Mapped[str] = mapped_column(String(50), default="MAIN")
    qty_on_hand: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    qty_allocated: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
