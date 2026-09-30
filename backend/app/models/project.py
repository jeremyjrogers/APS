from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProjectStatus, ProjectType


class MachineType(Base):
    __tablename__ = "machine_types"

    machine_type_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    avg_engineering_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    avg_assembly_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    avg_test_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    avg_shared_machining_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    avg_lead_time_weeks: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    projects: Mapped[list["Project"]] = relationship(back_populates="machine_type")


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[ProjectType] = mapped_column(Enum(ProjectType))
    machine_type_id: Mapped[str] = mapped_column(ForeignKey("machine_types.machine_type_id"))
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.QUOTED)

    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="Won contract price; null while QUOTED"
    )
    quoted_value: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="Estimated/quoted price before firming"
    )

    # Populated once status == FIRM and engineering has produced a real BOM.
    project_instance_bom_id: Mapped[int | None] = mapped_column(
        ForeignKey("boms.bom_id"), nullable=True
    )

    machine_type: Mapped["MachineType"] = relationship(back_populates="projects")
    milestones: Mapped[list["ProjectMilestone"]] = relationship(back_populates="project")


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"))
    milestone_name: Mapped[str] = mapped_column(String(100))
    planned_date: Mapped[date] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="milestones")
