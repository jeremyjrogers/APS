from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BomType, RoutingType


class Bom(Base):
    __tablename__ = "boms"

    bom_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    bom_type: Mapped[BomType] = mapped_column(Enum(BomType))
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    lines: Mapped[list["BomLine"]] = relationship(back_populates="bom")


class BomLine(Base):
    __tablename__ = "bom_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(ForeignKey("boms.bom_id"))
    component_item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    qty_per: Mapped[float] = mapped_column(Numeric(12, 4))
    scrap_pct: Mapped[float] = mapped_column(Numeric(5, 4), default=0)

    bom: Mapped["Bom"] = relationship(back_populates="lines")


class Routing(Base):
    __tablename__ = "routings"

    routing_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    routing_type: Mapped[RoutingType] = mapped_column(Enum(RoutingType))

    operations: Mapped[list["RoutingOperation"]] = relationship(back_populates="routing")


class RoutingOperation(Base):
    __tablename__ = "routing_operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    routing_id: Mapped[int] = mapped_column(ForeignKey("routings.routing_id"))
    seq: Mapped[int] = mapped_column(Integer)
    work_center_id: Mapped[str] = mapped_column(ForeignKey("work_centers.work_center_id"))
    setup_time_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    run_time_hours_per_unit: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)

    routing: Mapped["Routing"] = relationship(back_populates="operations")
