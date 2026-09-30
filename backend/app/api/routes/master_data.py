"""CRUD for reference/master data: items, suppliers, work centers, inventory,
BOMs, and routings.

This is the layer that was entirely missing before — every item, BOM, and
work center in the system came from the one-time seed script. Real use
requires maintaining this data: adding a part, correcting a lead time,
onboarding a supplier, fixing a routing.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.bom import Bom, BomLine, Routing, RoutingOperation
from app.models.enums import BomType, ItemType, MakeOrBuy, RoutingType, WorkCenterArea
from app.models.aftermarket import SalesOrder
from app.models.item import Item, ItemSupplier
from app.models.overhaul import OverhaulFinding
from app.models.reference import CapacityCalendar, Supplier, WorkCenter
from app.models.supply import Inventory, PurchaseOrderLine, WorkOrder

router = APIRouter(tags=["master-data"])


# --------------------------------------------------------------------------
# Items
# --------------------------------------------------------------------------


class ItemBody(BaseModel):
    item_id: str
    description: str
    item_type: str
    make_or_buy: str
    uom: str = "EA"
    standard_cost: float = 0
    default_lead_time_days: int = 0
    is_project_item: bool = False
    is_aftermarket_item: bool = False
    reorder_point: float | None = None
    reorder_qty: float | None = None
    safety_stock: float | None = None


class ItemUpdateBody(BaseModel):
    description: str | None = None
    item_type: str | None = None
    make_or_buy: str | None = None
    uom: str | None = None
    standard_cost: float | None = None
    default_lead_time_days: int | None = None
    is_project_item: bool | None = None
    is_aftermarket_item: bool | None = None
    reorder_point: float | None = None
    reorder_qty: float | None = None
    safety_stock: float | None = None


def _item_dict(i: Item) -> dict:
    return {
        "item_id": i.item_id, "description": i.description, "item_type": i.item_type.value,
        "make_or_buy": i.make_or_buy.value, "uom": i.uom, "standard_cost": float(i.standard_cost),
        "default_lead_time_days": i.default_lead_time_days,
        "is_project_item": i.is_project_item, "is_aftermarket_item": i.is_aftermarket_item,
        "reorder_point": float(i.reorder_point) if i.reorder_point is not None else None,
        "reorder_qty": float(i.reorder_qty) if i.reorder_qty is not None else None,
        "safety_stock": float(i.safety_stock) if i.safety_stock is not None else None,
    }


@router.get("/master/items")
def list_items(q: str | None = None, item_type: str | None = None,
                limit: int = 100, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    query = db.query(Item)
    if q:
        like = f"%{q}%"
        query = query.filter((Item.item_id.ilike(like)) | (Item.description.ilike(like)))
    if item_type:
        query = query.filter(Item.item_type == ItemType(item_type.upper()))
    total = query.count()
    rows = query.order_by(Item.item_id).offset(offset).limit(limit).all()
    return {"total": total, "rows": [_item_dict(i) for i in rows]}


@router.post("/master/items", status_code=201)
def create_item(body: ItemBody, db: Session = Depends(get_db)) -> dict:
    if db.query(Item).filter(Item.item_id == body.item_id).one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Item {body.item_id} already exists")
    try:
        item = Item(
            item_id=body.item_id, description=body.description,
            item_type=ItemType(body.item_type.upper()), make_or_buy=MakeOrBuy(body.make_or_buy.upper()),
            uom=body.uom, standard_cost=body.standard_cost,
            default_lead_time_days=body.default_lead_time_days,
            is_project_item=body.is_project_item, is_aftermarket_item=body.is_aftermarket_item,
            reorder_point=body.reorder_point, reorder_qty=body.reorder_qty, safety_stock=body.safety_stock,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    db.add(item)
    db.commit()
    return _item_dict(item)


@router.put("/master/items/{item_id}")
def update_item(item_id: str, body: ItemUpdateBody, db: Session = Depends(get_db)) -> dict:
    item = db.query(Item).filter(Item.item_id == item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    data = body.model_dump(exclude_unset=True)
    try:
        if "item_type" in data:
            data["item_type"] = ItemType(data["item_type"].upper())
        if "make_or_buy" in data:
            data["make_or_buy"] = MakeOrBuy(data["make_or_buy"].upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    return _item_dict(item)


@router.delete("/master/items/{item_id}")
def delete_item(item_id: str, db: Session = Depends(get_db)) -> dict:
    item = db.query(Item).filter(Item.item_id == item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    # Every table with a FK to items.item_id — deleting with any of these
    # present would otherwise 500 on the raw FK violation instead of telling
    # the caller what to clean up first.
    blockers = {
        "BOM component": db.query(BomLine).filter(BomLine.component_item_id == item_id).first(),
        "BOM parent": db.query(Bom).filter(Bom.parent_item_id == item_id).first(),
        "routing": db.query(Routing).filter(Routing.item_id == item_id).first(),
        "inventory": db.query(Inventory).filter(Inventory.item_id == item_id).first(),
        "supplier link": db.query(ItemSupplier).filter(ItemSupplier.item_id == item_id).first(),
        "sales order": db.query(SalesOrder).filter(SalesOrder.item_id == item_id).first(),
        "work order": db.query(WorkOrder).filter(WorkOrder.item_id == item_id).first(),
        "purchase order line": db.query(PurchaseOrderLine).filter(
            PurchaseOrderLine.item_id == item_id).first(),
        "overhaul finding": db.query(OverhaulFinding).filter(OverhaulFinding.item_id == item_id).first(),
    }
    hit = [name for name, row in blockers.items() if row is not None]
    if hit:
        raise HTTPException(
            status_code=409,
            detail=f"{item_id} is referenced by: {', '.join(hit)} — remove those first",
        )
    db.delete(item)
    db.commit()
    return {"item_id": item_id, "deleted": True}


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------


class SupplierBody(BaseModel):
    supplier_id: str
    name: str
    reliability_rating: float | None = Field(default=None, ge=0, le=1)


class SupplierUpdateBody(BaseModel):
    name: str
    reliability_rating: float | None = Field(default=None, ge=0, le=1)


@router.get("/master/suppliers")
def list_suppliers(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(Supplier).order_by(Supplier.supplier_id).all()
    return [
        {"supplier_id": s.supplier_id, "name": s.name,
         "reliability_rating": float(s.reliability_rating) if s.reliability_rating is not None else None}
        for s in rows
    ]


@router.post("/master/suppliers", status_code=201)
def create_supplier(body: SupplierBody, db: Session = Depends(get_db)) -> dict:
    if db.query(Supplier).filter(Supplier.supplier_id == body.supplier_id).one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Supplier {body.supplier_id} already exists")
    s = Supplier(supplier_id=body.supplier_id, name=body.name, reliability_rating=body.reliability_rating)
    db.add(s)
    db.commit()
    return {"supplier_id": s.supplier_id, "name": s.name,
            "reliability_rating": float(s.reliability_rating) if s.reliability_rating is not None else None}


@router.put("/master/suppliers/{supplier_id}")
def update_supplier(supplier_id: str, body: SupplierUpdateBody, db: Session = Depends(get_db)) -> dict:
    s = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    s.name = body.name
    s.reliability_rating = body.reliability_rating
    db.commit()
    return {"supplier_id": s.supplier_id, "name": s.name,
            "reliability_rating": float(s.reliability_rating) if s.reliability_rating is not None else None}


@router.delete("/master/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.query(Supplier).filter(Supplier.supplier_id == supplier_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    if db.query(ItemSupplier).filter(ItemSupplier.supplier_id == supplier_id).first() is not None:
        raise HTTPException(status_code=409, detail=f"{supplier_id} supplies items — remove those links first")
    db.delete(s)
    db.commit()
    return {"supplier_id": supplier_id, "deleted": True}


class ItemSupplierBody(BaseModel):
    item_id: str
    supplier_id: str
    lead_time_days: int = Field(ge=0)
    price: float = Field(ge=0)
    is_preferred: bool = False


@router.post("/master/item-suppliers", status_code=201)
def link_item_supplier(body: ItemSupplierBody, db: Session = Depends(get_db)) -> dict:
    if db.query(Item).filter(Item.item_id == body.item_id).one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Item {body.item_id} not found")
    if db.query(Supplier).filter(Supplier.supplier_id == body.supplier_id).one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Supplier {body.supplier_id} not found")
    if body.is_preferred:
        db.query(ItemSupplier).filter(ItemSupplier.item_id == body.item_id).update({"is_preferred": False})
    link = ItemSupplier(item_id=body.item_id, supplier_id=body.supplier_id,
                         lead_time_days=body.lead_time_days, price=body.price,
                         is_preferred=body.is_preferred)
    db.add(link)
    db.commit()
    return {"id": link.id, "item_id": link.item_id, "supplier_id": link.supplier_id}


# --------------------------------------------------------------------------
# Work centers (creating one also seeds its capacity calendar across the
# existing horizon, so it's immediately usable by the planner)
# --------------------------------------------------------------------------


class WorkCenterBody(BaseModel):
    work_center_id: str
    name: str
    area: str
    hourly_rate: float = 0
    daily_hours: float = Field(default=8.0, gt=0, le=168)


@router.post("/master/work-centers", status_code=201)
def create_work_center(body: WorkCenterBody, db: Session = Depends(get_db)) -> dict:
    if db.query(WorkCenter).filter(WorkCenter.work_center_id == body.work_center_id).one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Work center {body.work_center_id} already exists")
    try:
        area = WorkCenterArea(body.area.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    plant_id = db.query(WorkCenter.plant_id).first()
    plant_id = plant_id[0] if plant_id else "PLANT-01"

    wc = WorkCenter(work_center_id=body.work_center_id, plant_id=plant_id, name=body.name,
                     area=area, hourly_rate=body.hourly_rate)
    db.add(wc)
    db.flush()

    # Match the existing calendar horizon so this work center is schedulable
    # immediately rather than silently having zero capacity everywhere.
    bounds = db.query(func.min(CapacityCalendar.calendar_date),
                       func.max(CapacityCalendar.calendar_date)).first()
    start, end = bounds if bounds and bounds[0] else (date.today(), date.today() + timedelta(days=365))
    d = start
    rows = []
    while d <= end:
        if d.weekday() < 5:
            rows.append(CapacityCalendar(work_center_id=wc.work_center_id, calendar_date=d,
                                          available_hours=body.daily_hours))
        d += timedelta(days=1)
    db.bulk_save_objects(rows)
    db.commit()
    return {"work_center_id": wc.work_center_id, "name": wc.name, "area": wc.area.value,
            "calendar_days_seeded": len(rows)}


class WorkCenterUpdateBody(BaseModel):
    name: str | None = None
    hourly_rate: float | None = None


@router.put("/master/work-centers/{work_center_id}")
def update_work_center(work_center_id: str, body: WorkCenterUpdateBody,
                        db: Session = Depends(get_db)) -> dict:
    wc = db.query(WorkCenter).filter(WorkCenter.work_center_id == work_center_id).one_or_none()
    if wc is None:
        raise HTTPException(status_code=404, detail=f"Work center {work_center_id} not found")
    if body.name is not None:
        wc.name = body.name
    if body.hourly_rate is not None:
        wc.hourly_rate = body.hourly_rate
    db.commit()
    return {"work_center_id": wc.work_center_id, "name": wc.name, "hourly_rate": float(wc.hourly_rate)}


# --------------------------------------------------------------------------
# Inventory — there was no view or edit for this at all before.
# --------------------------------------------------------------------------


class InventoryBody(BaseModel):
    item_id: str
    location: str = "MAIN"
    qty_on_hand: float = Field(ge=0)
    qty_allocated: float = Field(default=0, ge=0)


def _inv_dict(i: Inventory) -> dict:
    return {"id": i.id, "item_id": i.item_id, "location": i.location,
            "qty_on_hand": float(i.qty_on_hand), "qty_allocated": float(i.qty_allocated)}


@router.get("/master/inventory")
def list_inventory(q: str | None = None, limit: int = 100, offset: int = 0,
                    db: Session = Depends(get_db)) -> dict:
    query = db.query(Inventory)
    if q:
        query = query.filter(Inventory.item_id.ilike(f"%{q}%"))
    total = query.count()
    rows = query.order_by(Inventory.item_id).offset(offset).limit(limit).all()
    return {"total": total, "rows": [_inv_dict(i) for i in rows]}


@router.post("/master/inventory", status_code=201)
def upsert_inventory(body: InventoryBody, db: Session = Depends(get_db)) -> dict:
    if db.query(Item).filter(Item.item_id == body.item_id).one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Item {body.item_id} not found")
    if body.qty_allocated > body.qty_on_hand:
        raise HTTPException(status_code=422, detail="qty_allocated cannot exceed qty_on_hand")
    row = db.query(Inventory).filter(Inventory.item_id == body.item_id,
                                      Inventory.location == body.location).one_or_none()
    if row is None:
        row = Inventory(item_id=body.item_id, location=body.location,
                         qty_on_hand=body.qty_on_hand, qty_allocated=body.qty_allocated)
        db.add(row)
    else:
        row.qty_on_hand = body.qty_on_hand
        row.qty_allocated = body.qty_allocated
    db.commit()
    return _inv_dict(row)


@router.delete("/master/inventory/{inventory_id}")
def delete_inventory(inventory_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(Inventory).filter(Inventory.id == inventory_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Inventory row {inventory_id} not found")
    db.delete(row)
    db.commit()
    return {"id": inventory_id, "deleted": True}


# --------------------------------------------------------------------------
# BOMs / Routings — view the full structure, and bulk-replace lines/ops in
# one call rather than building a line-by-line editor.
# --------------------------------------------------------------------------


class BomLineBody(BaseModel):
    component_item_id: str
    qty_per: float = Field(gt=0)
    scrap_pct: float = Field(default=0, ge=0, lt=1)


class BomBody(BaseModel):
    parent_item_id: str
    bom_type: str
    version: str = "1.0"
    lines: list[BomLineBody]


@router.get("/master/boms/{parent_item_id}")
def get_bom(parent_item_id: str, db: Session = Depends(get_db)) -> dict:
    bom = db.query(Bom).filter(Bom.parent_item_id == parent_item_id).one_or_none()
    if bom is None:
        raise HTTPException(status_code=404, detail=f"No BOM for {parent_item_id}")
    lines = db.query(BomLine).filter(BomLine.bom_id == bom.bom_id).all()
    return {
        "bom_id": bom.bom_id, "parent_item_id": bom.parent_item_id, "bom_type": bom.bom_type.value,
        "version": bom.version,
        "lines": [{"component_item_id": l.component_item_id, "qty_per": float(l.qty_per),
                   "scrap_pct": float(l.scrap_pct)} for l in lines],
    }


@router.put("/master/boms/{parent_item_id}")
def replace_bom(parent_item_id: str, body: BomBody, db: Session = Depends(get_db)) -> dict:
    """Create-or-fully-replace a BOM's line list. Simpler and less error-prone
    than a line-by-line editor for a POC, at the cost of not supporting
    partial edits — you resubmit the whole component list."""
    if db.query(Item).filter(Item.item_id == parent_item_id).one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Item {parent_item_id} not found")
    missing = [
        line.component_item_id for line in body.lines
        if db.query(Item).filter(Item.item_id == line.component_item_id).one_or_none() is None
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown component items: {missing}")
    try:
        bom_type = BomType(body.bom_type.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    bom = db.query(Bom).filter(Bom.parent_item_id == parent_item_id).one_or_none()
    if bom is None:
        bom = Bom(parent_item_id=parent_item_id, bom_type=bom_type, version=body.version)
        db.add(bom)
        db.flush()
    else:
        bom.bom_type = bom_type
        bom.version = body.version
        db.query(BomLine).filter(BomLine.bom_id == bom.bom_id).delete()

    for line in body.lines:
        db.add(BomLine(bom_id=bom.bom_id, component_item_id=line.component_item_id,
                        qty_per=line.qty_per, scrap_pct=line.scrap_pct))
    db.commit()
    return {"bom_id": bom.bom_id, "parent_item_id": parent_item_id, "line_count": len(body.lines)}


class RoutingOpBody(BaseModel):
    seq: int
    work_center_id: str
    setup_time_hours: float = Field(ge=0)
    run_time_hours_per_unit: float = Field(ge=0)
    description: str | None = None


class RoutingBody(BaseModel):
    item_id: str
    routing_type: str
    operations: list[RoutingOpBody]


@router.get("/master/routings/{item_id}")
def get_routing(item_id: str, db: Session = Depends(get_db)) -> dict:
    routing = db.query(Routing).filter(Routing.item_id == item_id).one_or_none()
    if routing is None:
        raise HTTPException(status_code=404, detail=f"No routing for {item_id}")
    ops = db.query(RoutingOperation).filter(
        RoutingOperation.routing_id == routing.routing_id).order_by(RoutingOperation.seq).all()
    return {
        "routing_id": routing.routing_id, "item_id": routing.item_id,
        "routing_type": routing.routing_type.value,
        "operations": [
            {"seq": o.seq, "work_center_id": o.work_center_id,
             "setup_time_hours": float(o.setup_time_hours),
             "run_time_hours_per_unit": float(o.run_time_hours_per_unit), "description": o.description}
            for o in ops
        ],
    }


@router.put("/master/routings/{item_id}")
def replace_routing(item_id: str, body: RoutingBody, db: Session = Depends(get_db)) -> dict:
    if db.query(Item).filter(Item.item_id == item_id).one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    missing = [
        op.work_center_id for op in body.operations
        if db.query(WorkCenter).filter(WorkCenter.work_center_id == op.work_center_id).one_or_none() is None
    ]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown work centers: {missing}")
    try:
        routing_type = RoutingType(body.routing_type.upper())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    routing = db.query(Routing).filter(Routing.item_id == item_id).one_or_none()
    if routing is None:
        routing = Routing(item_id=item_id, routing_type=routing_type)
        db.add(routing)
        db.flush()
    else:
        routing.routing_type = routing_type
        db.query(RoutingOperation).filter(RoutingOperation.routing_id == routing.routing_id).delete()

    for op in body.operations:
        db.add(RoutingOperation(routing_id=routing.routing_id, seq=op.seq,
                                 work_center_id=op.work_center_id, setup_time_hours=op.setup_time_hours,
                                 run_time_hours_per_unit=op.run_time_hours_per_unit,
                                 description=op.description))
    db.commit()
    return {"routing_id": routing.routing_id, "item_id": item_id, "operation_count": len(body.operations)}
