"""Entry points for new demand: sales orders, projects, and overhaul jobs.

This is the day-to-day input side of the tool — a customer calls with an
order, a quote gets won, a unit comes in for teardown. Before this, every
demand record came from the one-time seed script; nothing new could enter
the system short of editing the database directly.

Projects follow the domain model's QUOTED -> FIRM distinction: a quote
carries only a rough-cut MachineType profile (no BOM exists yet, because
engineering hasn't designed anything). Firming a project is the moment
engineering hands off a real, unique top-level item with its own BOM and
routing, cloned from the machine type's template — mirroring how the
synthetic seed data was built, but now triggerable one project at a time.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.bom import Bom, BomLine, Routing, RoutingOperation
from app.models.enums import (
    ActionType,
    BomType,
    FindingAction,
    FindingSource,
    ItemType,
    MakeOrBuy,
    OverhaulJobStatus,
    ProjectStatus,
    ProjectType,
    RoutingType,
    SalesOrderType,
)
from app.models.aftermarket import SalesOrder
from app.models.exception import PlanAction
from app.models.item import Item
from app.models.overhaul import OverhaulFinding, OverhaulJob
from app.models.project import MachineType, Project, ProjectMilestone

router = APIRouter(tags=["demand-entry"])


def _log(db: Session, action_type: ActionType, target_type: str, target_id: str,
         after: str, note: str | None = None) -> None:
    db.add(PlanAction(action_type=action_type, target_type=target_type, target_id=target_id,
                       before_value=None, after_value=after, note=note, actor="planner"))


def _next_id(db: Session, model, id_attr: str, prefix: str) -> str:
    """Highest existing numeric suffix + 1 — consistent with how the planning
    engine allocates WO/PO ids, so entry-created and engine-created records
    never collide."""
    highest = 0
    for (existing,) in db.query(getattr(model, id_attr)).filter(
        getattr(model, id_attr).like(f"{prefix}-%")
    ).all():
        try:
            highest = max(highest, int(str(existing).rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{highest + 1:06d}"


# --------------------------------------------------------------------------
# Sales orders
# --------------------------------------------------------------------------


class SalesOrderBody(BaseModel):
    customer: str
    item_id: str
    qty: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    order_type: str = "STANDARD"
    requested_date: date
    priority: int = Field(default=5, ge=1, le=10)


@router.post("/demand/sales-orders", status_code=201)
def create_sales_order(body: SalesOrderBody, db: Session = Depends(get_db)) -> dict:
    item = db.query(Item).filter(Item.item_id == body.item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {body.item_id} not found")
    if not item.is_aftermarket_item:
        raise HTTPException(status_code=422, detail=f"{body.item_id} isn't marked as an aftermarket item")
    try:
        order_type = SalesOrderType(body.order_type.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    order_id = _next_id(db, SalesOrder, "order_id", "SO")
    order = SalesOrder(order_id=order_id, customer=body.customer, item_id=body.item_id,
                        qty=body.qty, unit_price=body.unit_price, order_type=order_type,
                        requested_date=body.requested_date, priority=body.priority)
    db.add(order)
    _log(db, ActionType.RELEASE, "SALES_ORDER", order_id,
         f"{body.qty}x {body.item_id} due {body.requested_date}", "New order entered")
    db.commit()
    return {"order_id": order_id, "item_id": body.item_id, "qty": body.qty,
            "requested_date": body.requested_date.isoformat()}


# --------------------------------------------------------------------------
# Projects: quote -> firm
# --------------------------------------------------------------------------


class ProjectQuoteBody(BaseModel):
    customer: str
    machine_type_id: str
    project_type: str = "ETO"
    quoted_value: float | None = None


@router.get("/master/machine-types")
def list_machine_types(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(MachineType).order_by(MachineType.machine_type_id).all()
    return [
        {"machine_type_id": m.machine_type_id, "name": m.name,
         "avg_lead_time_weeks": float(m.avg_lead_time_weeks),
         "avg_engineering_hours": float(m.avg_engineering_hours),
         "avg_assembly_hours": float(m.avg_assembly_hours),
         "avg_test_hours": float(m.avg_test_hours)}
        for m in rows
    ]


@router.post("/demand/projects", status_code=201)
def create_project_quote(body: ProjectQuoteBody, db: Session = Depends(get_db)) -> dict:
    mt = db.query(MachineType).filter(MachineType.machine_type_id == body.machine_type_id).one_or_none()
    if mt is None:
        raise HTTPException(status_code=404, detail=f"Machine type {body.machine_type_id} not found")
    try:
        project_type = ProjectType(body.project_type.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    project_id = _next_id(db, Project, "project_id", "PRJ")
    project = Project(project_id=project_id, customer=body.customer, project_type=project_type,
                       machine_type_id=body.machine_type_id, status=ProjectStatus.QUOTED,
                       quoted_value=body.quoted_value)
    db.add(project)
    _log(db, ActionType.RELEASE, "PROJECT", project_id,
         f"QUOTED — {body.customer} / {mt.name}", "New quote entered")
    db.commit()
    return {"project_id": project_id, "status": "QUOTED", "customer": body.customer,
            "machine_type_id": body.machine_type_id}


class FirmProjectBody(BaseModel):
    contract_date: date | None = None
    contract_value: float | None = None
    lead_time_variance: float = Field(default=1.0, gt=0, le=3.0)


@router.post("/demand/projects/{project_id}/firm")
def firm_project(project_id: str, body: FirmProjectBody, db: Session = Depends(get_db)) -> dict:
    """Won it. Generates the real top-level item, clones the machine type's
    template BOM and routing into an instance BOM/routing, and lays down
    milestones — the same mechanics the seed script uses for FIRM projects,
    just for one project on demand instead of forty-four at once."""
    project = db.query(Project).filter(Project.project_id == project_id).one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    if project.status != ProjectStatus.QUOTED:
        raise HTTPException(status_code=409, detail=f"Project {project_id} is {project.status.value}, not QUOTED")

    mt = db.query(MachineType).filter(MachineType.machine_type_id == project.machine_type_id).one()
    template_item_id = f"FG-{mt.machine_type_id}"
    template_bom = db.query(Bom).filter(Bom.parent_item_id == template_item_id).one_or_none()
    template_routing = db.query(Routing).filter(Routing.item_id == template_item_id).one_or_none()
    if template_bom is None or template_routing is None:
        raise HTTPException(
            status_code=422,
            detail=f"Machine type {mt.machine_type_id} has no template BOM/routing to clone from",
        )

    contract_date = body.contract_date or date.today()
    lead_days = int(float(mt.avg_lead_time_weeks) * 7 * body.lead_time_variance)
    due_date = contract_date + timedelta(days=lead_days)

    fg_id = f"FG-{project_id}"
    db.add(Item(item_id=fg_id, description=f"{mt.name} - {project_id}",
                item_type=ItemType.FINISHED_PACKAGE, make_or_buy=MakeOrBuy.MAKE, uom="EA",
                standard_cost=0, default_lead_time_days=lead_days,
                is_project_item=True, is_aftermarket_item=False))
    db.flush()

    template_lines = db.query(BomLine).filter(BomLine.bom_id == template_bom.bom_id).all()
    instance_bom = Bom(parent_item_id=fg_id, bom_type=BomType.PROJECT_INSTANCE, version="1.0",
                        effective_from=contract_date)
    db.add(instance_bom)
    db.flush()
    for line in template_lines:
        db.add(BomLine(bom_id=instance_bom.bom_id, component_item_id=line.component_item_id,
                        qty_per=line.qty_per, scrap_pct=line.scrap_pct))

    template_ops = db.query(RoutingOperation).filter(
        RoutingOperation.routing_id == template_routing.routing_id).all()
    instance_routing = Routing(item_id=fg_id, routing_type=RoutingType.NEW_UNIT)
    db.add(instance_routing)
    db.flush()
    for op in template_ops:
        db.add(RoutingOperation(routing_id=instance_routing.routing_id, seq=op.seq,
                                 work_center_id=op.work_center_id, setup_time_hours=op.setup_time_hours,
                                 run_time_hours_per_unit=op.run_time_hours_per_unit,
                                 description=op.description))

    total_days = max(1, (due_date - contract_date).days)
    fractions = [0.15, 0.30, 0.55, 0.85, 1.0]
    names = ["Design freeze", "Procurement release", "Assembly start", "Test", "Ship"]
    if project.project_type == ProjectType.CTO:
        fractions = [0.05, 0.20, 0.50, 0.85, 1.0]
    for frac, name in zip(fractions, names):
        db.add(ProjectMilestone(project_id=project_id, milestone_name=name,
                                 planned_date=contract_date + timedelta(days=int(total_days * frac))))

    project.status = ProjectStatus.FIRM
    project.contract_date = contract_date
    project.contract_due_date = due_date
    project.contract_value = body.contract_value or project.quoted_value
    project.project_instance_bom_id = instance_bom.bom_id

    _log(db, ActionType.RELEASE, "PROJECT", project_id,
         f"FIRM — due {due_date}, value {project.contract_value}", "Quote won, engineering released")
    db.commit()
    return {"project_id": project_id, "status": "FIRM", "contract_date": contract_date.isoformat(),
            "contract_due_date": due_date.isoformat(), "fg_item_id": fg_id,
            "bom_lines": len(template_lines), "routing_operations": len(template_ops)}


# --------------------------------------------------------------------------
# Overhaul jobs
# --------------------------------------------------------------------------


class OverhaulJobBody(BaseModel):
    customer: str
    asset_id: str
    received_date: date = Field(default_factory=date.today)


@router.post("/demand/overhaul-jobs", status_code=201)
def create_overhaul_job(body: OverhaulJobBody, db: Session = Depends(get_db)) -> dict:
    job_id = _next_id(db, OverhaulJob, "job_id", "OHJ")
    job = OverhaulJob(job_id=job_id, customer=body.customer, asset_id=body.asset_id,
                       received_date=body.received_date, status=OverhaulJobStatus.RECEIVED)
    db.add(job)
    _log(db, ActionType.RELEASE, "OVERHAUL_JOB", job_id,
         f"RECEIVED — {body.customer} / {body.asset_id}", "New job received")
    db.commit()
    return {"job_id": job_id, "status": "RECEIVED", "received_date": body.received_date.isoformat()}


class FindingBody(BaseModel):
    item_id: str
    recommended_action: str
    qty: int = Field(default=1, gt=0)
    source: str


class AdvanceOverhaulBody(BaseModel):
    status: str
    estimated_value: float | None = None
    findings: list[FindingBody] = []


# Only forward transitions make sense for a physical teardown/repair process.
_STATUS_ORDER = [s.value for s in OverhaulJobStatus]


@router.post("/demand/overhaul-jobs/{job_id}/advance")
def advance_overhaul_job(job_id: str, body: AdvanceOverhaulBody, db: Session = Depends(get_db)) -> dict:
    job = db.query(OverhaulJob).filter(OverhaulJob.job_id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail=f"Overhaul job {job_id} not found")
    try:
        new_status = OverhaulJobStatus(body.status.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if _STATUS_ORDER.index(new_status.value) < _STATUS_ORDER.index(job.status.value):
        raise HTTPException(
            status_code=409,
            detail=f"Can't move {job_id} backward from {job.status.value} to {new_status.value}",
        )

    if body.findings and new_status.value in (
        OverhaulJobStatus.RECEIVED.value, OverhaulJobStatus.TEARDOWN.value,
    ):
        raise HTTPException(
            status_code=422,
            detail="Findings only make sense once a job has passed INSPECTION",
        )

    for f in body.findings:
        if db.query(Item).filter(Item.item_id == f.item_id).one_or_none() is None:
            raise HTTPException(status_code=404, detail=f"Item {f.item_id} not found")
        try:
            action = FindingAction(f.recommended_action.upper())
            source = FindingSource(f.source.upper())
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        db.add(OverhaulFinding(job_id=job_id, item_id=f.item_id, recommended_action=action,
                                qty=f.qty, source=source))

    before = job.status.value
    job.status = new_status
    if body.estimated_value is not None:
        job.estimated_value = body.estimated_value

    _log(db, ActionType.RESCHEDULE, "OVERHAUL_JOB", job_id,
         f"{before} -> {new_status.value}", f"{len(body.findings)} finding(s) added"
         if body.findings else None)
    db.commit()
    return {"job_id": job_id, "status": new_status.value, "findings_added": len(body.findings)}
