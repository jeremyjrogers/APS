from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ItemType, MakeOrBuy


class Item(Base):
    __tablename__ = "items"

    item_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(String(300))
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType))
    make_or_buy: Mapped[MakeOrBuy] = mapped_column(Enum(MakeOrBuy))
    uom: Mapped[str] = mapped_column(String(10), default="EA")
    standard_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    default_lead_time_days: Mapped[int] = mapped_column(Integer, default=0)

    is_project_item: Mapped[bool] = mapped_column(Boolean, default=False)
    is_aftermarket_item: Mapped[bool] = mapped_column(Boolean, default=False)

    reorder_point: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reorder_qty: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    safety_stock: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    suppliers: Mapped[list["ItemSupplier"]] = relationship(back_populates="item")


class ItemSupplier(Base):
    __tablename__ = "item_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    lead_time_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)

    item: Mapped["Item"] = relationship(back_populates="suppliers")
