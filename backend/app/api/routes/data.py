from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.aftermarket import SalesOrder
from app.models.enums import (
    OverhaulJobStatus,
    ProjectStatus,
    PurchaseOrderStatus,
    SalesOrderType,
    WorkOrderSource,
    WorkOrderStatus,
)
from app.models.item import Item
from app.models.overhaul import OverhaulJob
from app.models.project import Project
from app.models.reference import Supplier, WorkCenter
from app.models.supply import PurchaseOrder, PurchaseOrderLine, WorkOrder

router = APIRouter(tags=["data"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    project_counts = {
        status.value: count
        for status, count in db.query(Project.status, func.count()).group_by(Project.status).all()
    }
    firm_value = db.query(func.coalesce(func.sum(Project.contract_value), 0)).filter(
        Project.status == ProjectStatus.FIRM).scalar()
    quoted_value = db.query(func.coalesce(func.sum(Project.quoted_value), 0)).filter(
        Project.status == ProjectStatus.QUOTED).scalar()
    so_revenue = db.query(func.coalesce(func.sum(SalesOrder.qty * SalesOrder.unit_price), 0)).scalar()
    oh_value = db.query(func.coalesce(func.sum(OverhaulJob.estimated_value), 0)).scalar()

    return {
        "items": db.query(func.count(Item.item_id)).scalar(),
        "work_centers": db.query(func.count(WorkCenter.work_center_id)).scalar(),
        "suppliers": db.query(func.count(Supplier.supplier_id)).scalar(),
        "projects": {
            "firm": project_counts.get("FIRM", 0),
            "quoted": project_counts.get("QUOTED", 0),
            "lost": project_counts.get("LOST", 0),
            "cancelled": project_counts.get("CANCELLED", 0),
            "firm_contract_value": float(firm_value),
            "quoted_pipeline_value": float(quoted_value),
        },
        "sales_orders": {
            "count": db.query(func.count(SalesOrder.order_id)).scalar(),
            "revenue": float(so_revenue),
        },
        "overhaul_jobs": {
            "count": db.query(func.count(OverhaulJob.job_id)).scalar(),
            "value": float(oh_value),
        },
        "work_orders": db.query(func.count(WorkOrder.wo_id)).scalar(),
        "purchase_orders": db.query(func.count(PurchaseOrder.po_id)).scalar(),
    }


@router.get("/reference/work-centers")
def list_work_centers(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(WorkCenter).order_by(WorkCenter.work_center_id).all()
    return [
        {"work_center_id": r.work_center_id, "name": r.name, "area": r.area.value,
         "hourly_rate": float(r.hourly_rate)}
        for r in rows
    ]


@router.get("/demand/projects")
def list_projects(status: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
                   db: Session = Depends(get_db)) -> dict:
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == ProjectStatus(status.upper()))
    total = q.count()
    rows = q.order_by(Project.project_id).offset(offset).limit(limit).all()
    return {
        "total": total,
        "rows": [
            {
                "project_id": r.project_id, "customer": r.customer,
                "project_type": r.project_type.value, "machine_type_id": r.machine_type_id,
                "status": r.status.value,
                "contract_date": r.contract_date.isoformat() if r.contract_date else None,
                "contract_due_date": r.contract_due_date.isoformat() if r.contract_due_date else None,
                "contract_value": float(r.contract_value) if r.contract_value is not None else None,
                "quoted_value": float(r.quoted_value) if r.quoted_value is not None else None,
            }
            for r in rows
        ],
    }


@router.get("/demand/sales-orders")
def list_sales_orders(order_type: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
                       db: Session = Depends(get_db)) -> dict:
    q = db.query(SalesOrder)
    if order_type:
        q = q.filter(SalesOrder.order_type == SalesOrderType(order_type.upper()))
    total = q.count()
    rows = q.order_by(SalesOrder.requested_date).offset(offset).limit(limit).all()
    return {
        "total": total,
        "rows": [
            {
                "order_id": r.order_id, "customer": r.customer, "item_id": r.item_id,
                "qty": r.qty, "unit_price": float(r.unit_price), "order_type": r.order_type.value,
                "requested_date": r.requested_date.isoformat(), "priority": r.priority,
            }
            for r in rows
        ],
    }


@router.get("/demand/overhaul-jobs")
def list_overhaul_jobs(status: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
                        db: Session = Depends(get_db)) -> dict:
    q = db.query(OverhaulJob)
    if status:
        q = q.filter(OverhaulJob.status == OverhaulJobStatus(status.upper()))
    total = q.count()
    rows = q.order_by(OverhaulJob.received_date.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "rows": [
            {
                "job_id": r.job_id, "customer": r.customer, "asset_id": r.asset_id,
                "received_date": r.received_date.isoformat(), "status": r.status.value,
                "estimated_value": float(r.estimated_value) if r.estimated_value is not None else None,
            }
            for r in rows
        ],
    }


@router.get("/supply/work-orders")
def list_work_orders(source: str | None = None, status: str | None = None,
                      limit: int = Query(100, le=500), offset: int = 0,
                      db: Session = Depends(get_db)) -> dict:
    q = db.query(WorkOrder)
    if source:
        q = q.filter(WorkOrder.source == WorkOrderSource(source.upper()))
    if status:
        q = q.filter(WorkOrder.status == WorkOrderStatus(status.upper()))
    total = q.count()
    rows = q.order_by(WorkOrder.start_date).offset(offset).limit(limit).all()
    return {
        "total": total,
        "rows": [
            {
                "wo_id": r.wo_id, "item_id": r.item_id, "qty": float(r.qty),
                "source": r.source.value, "source_ref": r.source_ref,
                "start_date": r.start_date.isoformat(), "due_date": r.due_date.isoformat(),
                "status": r.status.value,
                "projected_end": r.projected_end.isoformat() if r.projected_end else None,
                "capacity_delay_days": r.capacity_delay_days,
                "expedite_days": r.expedite_days,
            }
            for r in rows
        ],
    }


@router.get("/supply/purchase-orders")
def list_purchase_orders(status: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
                          db: Session = Depends(get_db)) -> dict:
    q = db.query(PurchaseOrder)
    if status:
        q = q.filter(PurchaseOrder.status == PurchaseOrderStatus(status.upper()))
    total = q.count()
    pos = q.order_by(PurchaseOrder.po_id).offset(offset).limit(limit).all()
    po_ids = [p.po_id for p in pos]
    lines = db.query(PurchaseOrderLine).filter(PurchaseOrderLine.po_id.in_(po_ids)).all() if po_ids else []
    lines_by_po: dict[str, list] = {}
    for line in lines:
        lines_by_po.setdefault(line.po_id, []).append(
            {"item_id": line.item_id, "qty": float(line.qty), "due_date": line.due_date.isoformat()}
        )
    return {
        "total": total,
        "rows": [
            {"po_id": p.po_id, "supplier_id": p.supplier_id, "status": p.status.value,
             "lines": lines_by_po.get(p.po_id, [])}
            for p in pos
        ],
    }
