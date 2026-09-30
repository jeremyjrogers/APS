from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import WorkCenterArea


class Plant(Base):
    __tablename__ = "plants"

    plant_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    work_centers: Mapped[list["WorkCenter"]] = relationship(back_populates="plant")


class WorkCenter(Base):
    __tablename__ = "work_centers"

    work_center_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.plant_id"))
    name: Mapped[str] = mapped_column(String(200))
    area: Mapped[WorkCenterArea] = mapped_column(Enum(WorkCenterArea))
    capacity_uom: Mapped[str] = mapped_column(String(20), default="hours")
    hourly_rate: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    plant: Mapped["Plant"] = relationship(back_populates="work_centers")
    calendar_entries: Mapped[list["CapacityCalendar"]] = relationship(
        back_populates="work_center"
    )


class CapacityCalendar(Base):
    __tablename__ = "capacity_calendar"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    work_center_id: Mapped[str] = mapped_column(ForeignKey("work_centers.work_center_id"))
    calendar_date: Mapped[date] = mapped_column(Date)
    available_hours: Mapped[float] = mapped_column(Numeric(6, 2))

    work_center: Mapped["WorkCenter"] = relationship(back_populates="calendar_entries")


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    reliability_rating: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
