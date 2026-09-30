from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FindingAction, FindingSource, OverhaulJobStatus


class OverhaulJob(Base):
    __tablename__ = "overhaul_jobs"

    job_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer: Mapped[str] = mapped_column(String(200))
    asset_id: Mapped[str] = mapped_column(String(100))
    received_date: Mapped[date] = mapped_column(Date)
    status: Mapped[OverhaulJobStatus] = mapped_column(
        Enum(OverhaulJobStatus), default=OverhaulJobStatus.RECEIVED
    )
    estimated_value: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="Approximate parts + labor value once scoped"
    )

    findings: Mapped[list["OverhaulFinding"]] = relationship(back_populates="job")


class OverhaulFinding(Base):
    __tablename__ = "overhaul_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("overhaul_jobs.job_id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("items.item_id"))
    recommended_action: Mapped[FindingAction] = mapped_column(Enum(FindingAction))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[FindingSource] = mapped_column(Enum(FindingSource))

    job: Mapped["OverhaulJob"] = relationship(back_populates="findings")
