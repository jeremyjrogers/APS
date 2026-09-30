"""Pegging / traceability — answering "why is this late?".

Given a root demand (project, sales order, overhaul job) this assembles the
full supply tree that the planning engine generated for it, so a planner can
walk from a late package down through subassemblies and machined parts to the
specific purchase order that is actually driving the delay.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.aftermarket import SalesOrder
from app.models.item import Item
from app.models.overhaul import OverhaulJob
from app.models.project import Project
from app.models.supply import PurchaseOrder, PurchaseOrderLine, WorkOrder

router = APIRouter(prefix="/pegging", tags=["pegging"])


def _wo_node(wo: WorkOrder, descriptions: dict[str, str]) -> dict:
    return {
        "node_type": "WORK_ORDER",
        "order_id": wo.wo_id,
        "item_id": wo.item_id,
        "description": descriptions.get(wo.item_id, ""),
        "qty": float(wo.qty),
        "start_date": wo.start_date.isoformat(),
        "due_date": wo.due_date.isoformat(),
        "status": wo.status.value,
        "bom_level": wo.bom_level,
        "expedite_days": wo.expedite_days,
        "supplier_id": None,
        "children": [],
    }


def _po_node(po: PurchaseOrder, line: PurchaseOrderLine | None, descriptions: dict[str, str]) -> dict:
    item_id = line.item_id if line else ""
    return {
        "node_type": "PURCHASE_ORDER",
        "order_id": po.po_id,
        "item_id": item_id,
        "description": descriptions.get(item_id, ""),
        "qty": float(line.qty) if line else 0.0,
        "start_date": None,
        "due_date": line.due_date.isoformat() if line else None,
        "status": po.status.value,
        "bom_level": po.bom_level,
        "expedite_days": po.expedite_days,
        "supplier_id": po.supplier_id,
        "children": [],
    }


@router.get("/demand/{source_ref}")
def peg_demand(source_ref: str, db: Session = Depends(get_db)) -> dict:
    """Full supply tree for one root demand reference."""
    # Bucketed demand stores refs like "SO-000123 +4 more"; match on prefix so
    # either the bare id or the full bucketed label resolves.
    wos = db.query(WorkOrder).filter(WorkOrder.source_ref.like(f"{source_ref}%")).all()
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.source_ref.like(f"{source_ref}%")).all()

    if not wos and not pos:
        raise HTTPException(status_code=404, detail=f"No planned supply pegged to {source_ref}")

    item_ids = {w.item_id for w in wos}
    po_lines = db.query(PurchaseOrderLine).filter(
        PurchaseOrderLine.po_id.in_([p.po_id for p in pos])
    ).all() if pos else []
    line_by_po = {line.po_id: line for line in po_lines}
    item_ids |= {line.item_id for line in po_lines}

    descriptions = {
        i.item_id: i.description
        for i in db.query(Item).filter(Item.item_id.in_(item_ids)).all()
    } if item_ids else {}

    nodes: dict[str, dict] = {w.wo_id: _wo_node(w, descriptions) for w in wos}
    roots: list[dict] = []

    for w in wos:
        node = nodes[w.wo_id]
        parent = nodes.get(w.parent_wo_id) if w.parent_wo_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)

    for p in pos:
        node = _po_node(p, line_by_po.get(p.po_id), descriptions)
        parent = nodes.get(p.parent_wo_id) if p.parent_wo_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)

    _sort_tree(roots)

    worst = _worst_offender(roots)
    return {
        "source_ref": source_ref,
        "demand": _describe_demand(db, source_ref),
        "total_orders": len(wos) + len(pos),
        "max_expedite_days": worst["expedite_days"] if worst else 0,
        "root_cause": worst,
        "tree": roots,
    }


def _sort_tree(nodes: list[dict]) -> None:
    """Most-delayed branches first, so the problem is at the top of the view."""
    nodes.sort(key=lambda n: (-n["expedite_days"], n["item_id"]))
    for n in nodes:
        _sort_tree(n["children"])


def _worst_offender(nodes: list[dict]) -> dict | None:
    """Deepest, most-delayed node — the actual constraint rather than the
    top-level order that merely reports being late."""
    worst = None
    stack = list(nodes)
    while stack:
        n = stack.pop()
        stack.extend(n["children"])
        if n["expedite_days"] <= 0:
            continue
        if worst is None or (n["expedite_days"], n["bom_level"]) > (worst["expedite_days"], worst["bom_level"]):
            worst = n
    if worst is None:
        return None
    return {k: v for k, v in worst.items() if k != "children"}


def _describe_demand(db: Session, source_ref: str) -> dict | None:
    project = db.query(Project).filter(Project.project_id == source_ref).one_or_none()
    if project:
        return {
            "type": "PROJECT", "ref": project.project_id, "customer": project.customer,
            "due_date": project.contract_due_date.isoformat() if project.contract_due_date else None,
            "value": float(project.contract_value or project.quoted_value or 0),
        }
    so = db.query(SalesOrder).filter(SalesOrder.order_id == source_ref).one_or_none()
    if so:
        return {
            "type": "SALES_ORDER", "ref": so.order_id, "customer": so.customer,
            "due_date": so.requested_date.isoformat(),
            "value": float(so.qty) * float(so.unit_price),
            "order_type": so.order_type.value, "priority": so.priority,
        }
    job = db.query(OverhaulJob).filter(OverhaulJob.job_id == source_ref).one_or_none()
    if job:
        return {
            "type": "OVERHAUL_JOB", "ref": job.job_id, "customer": job.customer,
            "due_date": None, "value": float(job.estimated_value or 0),
            "status": job.status.value,
        }
    return None


@router.get("/order/{order_id}")
def peg_order(order_id: str, db: Session = Depends(get_db)) -> dict:
    """Walk upward from one order to the root demand it exists to satisfy."""
    chain: list[dict] = []
    descriptions: dict[str, str] = {}

    current_id: str | None = order_id
    source_ref = None
    guard = 0

    while current_id and guard < 20:
        guard += 1
        wo = db.query(WorkOrder).filter(WorkOrder.wo_id == current_id).one_or_none()
        if wo:
            item = db.query(Item).filter(Item.item_id == wo.item_id).one_or_none()
            descriptions[wo.item_id] = item.description if item else ""
            chain.append(_wo_node(wo, descriptions))
            source_ref = wo.source_ref
            current_id = wo.parent_wo_id
            continue

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_id == current_id).one_or_none()
        if po:
            line = db.query(PurchaseOrderLine).filter(
                PurchaseOrderLine.po_id == po.po_id).first()
            if line:
                item = db.query(Item).filter(Item.item_id == line.item_id).one_or_none()
                descriptions[line.item_id] = item.description if item else ""
            chain.append(_po_node(po, line, descriptions))
            source_ref = po.source_ref
            current_id = po.parent_wo_id
            continue

        break

    if not chain:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return {
        "order_id": order_id,
        "source_ref": source_ref,
        "demand": _describe_demand(db, source_ref.split(" ")[0]) if source_ref else None,
        "chain_to_root": chain,
    }
