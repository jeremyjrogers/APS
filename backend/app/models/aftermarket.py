from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SalesOrderType
from app.models.item import Item


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    order_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer: Mapped[str] = mapped_column(String(200))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    order_type: Mapped[SalesOrderType] = mapped_column(Enum(SalesOrderType))
    requested_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[int] = mapped_column(Integer, default=5)

    item: Mapped["Item"] = relationship()
