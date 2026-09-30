"""Bulk CSV import — the other half of "getting stuff into the tool".

Hand-entering forms one at a time doesn't scale to loading a real company's
item master or order book. These endpoints take a CSV upload, validate row by
row, and report exactly what happened per row rather than failing the whole
batch on one bad line — a 500-row import shouldn't be all-or-nothing when
499 rows are fine.
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.aftermarket import SalesOrder
from app.models.enums import ItemType, MakeOrBuy, SalesOrderType
from app.models.item import Item
from app.models.supply import Inventory

router = APIRouter(prefix="/import", tags=["import"])


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


async def _read_csv_rows(file: UploadFile) -> list[dict]:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File isn't valid UTF-8 text")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=422, detail="No header row found")
    return list(reader)


def _highest_seq(db: Session, model, id_attr: str, prefix: str) -> int:
    highest = 0
    for (existing,) in db.query(getattr(model, id_attr)).filter(
        getattr(model, id_attr).like(f"{prefix}-%")
    ).all():
        try:
            highest = max(highest, int(str(existing).rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            continue
    return highest  # caller increments per row


REQUIRED_ITEM_COLS = {"item_id", "description", "item_type", "make_or_buy"}


@router.post("/items")
async def import_items(file: UploadFile, db: Session = Depends(get_db)) -> dict:
    rows = await _read_csv_rows(file)
    created = updated = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):  # row 1 is the header
        missing = REQUIRED_ITEM_COLS - row.keys()
        if missing:
            errors.append({"row": i, "message": f"missing columns: {sorted(missing)}"})
            continue
        item_id = row["item_id"].strip()
        if not item_id:
            errors.append({"row": i, "message": "empty item_id"})
            continue
        try:
            item_type = ItemType(row["item_type"].strip().upper())
            make_or_buy = MakeOrBuy(row["make_or_buy"].strip().upper())
            cost = float(row.get("standard_cost") or 0)
            lead_time = int(float(row.get("default_lead_time_days") or 0))
        except ValueError as e:
            errors.append({"row": i, "message": f"invalid value: {e}"})
            continue

        existing = db.query(Item).filter(Item.item_id == item_id).one_or_none()
        if existing is None:
            db.add(Item(
                item_id=item_id, description=row["description"].strip(), item_type=item_type,
                make_or_buy=make_or_buy, uom=(row.get("uom") or "EA").strip(),
                standard_cost=cost, default_lead_time_days=lead_time,
                is_project_item=_to_bool(row.get("is_project_item", "")),
                is_aftermarket_item=_to_bool(row.get("is_aftermarket_item", "")),
            ))
            created += 1
        else:
            existing.description = row["description"].strip()
            existing.item_type = item_type
            existing.make_or_buy = make_or_buy
            existing.standard_cost = cost
            existing.default_lead_time_days = lead_time
            updated += 1

    db.commit()
    return {"total_rows": len(rows), "created": created, "updated": updated,
            "errors": errors, "error_count": len(errors)}


REQUIRED_INVENTORY_COLS = {"item_id", "qty_on_hand"}


@router.post("/inventory")
async def import_inventory(file: UploadFile, db: Session = Depends(get_db)) -> dict:
    rows = await _read_csv_rows(file)
    created = updated = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        missing = REQUIRED_INVENTORY_COLS - row.keys()
        if missing:
            errors.append({"row": i, "message": f"missing columns: {sorted(missing)}"})
            continue
        item_id = row["item_id"].strip()
        if db.query(Item).filter(Item.item_id == item_id).one_or_none() is None:
            errors.append({"row": i, "message": f"unknown item_id {item_id}"})
            continue
        try:
            on_hand = float(row["qty_on_hand"])
            allocated = float(row.get("qty_allocated") or 0)
        except ValueError as e:
            errors.append({"row": i, "message": f"invalid quantity: {e}"})
            continue
        if allocated > on_hand:
            errors.append({"row": i, "message": "qty_allocated exceeds qty_on_hand"})
            continue

        location = (row.get("location") or "MAIN").strip()
        existing = db.query(Inventory).filter(
            Inventory.item_id == item_id, Inventory.location == location).one_or_none()
        if existing is None:
            db.add(Inventory(item_id=item_id, location=location,
                              qty_on_hand=on_hand, qty_allocated=allocated))
            created += 1
        else:
            existing.qty_on_hand = on_hand
            existing.qty_allocated = allocated
            updated += 1

    db.commit()
    return {"total_rows": len(rows), "created": created, "updated": updated,
            "errors": errors, "error_count": len(errors)}


REQUIRED_SO_COLS = {"customer", "item_id", "qty", "unit_price", "requested_date"}


@router.post("/sales-orders")
async def import_sales_orders(file: UploadFile, db: Session = Depends(get_db)) -> dict:
    rows = await _read_csv_rows(file)
    created = 0
    errors: list[dict] = []
    next_seq = _highest_seq(db, SalesOrder, "order_id", "SO")

    for i, row in enumerate(rows, start=2):
        missing = REQUIRED_SO_COLS - row.keys()
        if missing:
            errors.append({"row": i, "message": f"missing columns: {sorted(missing)}"})
            continue
        item_id = row["item_id"].strip()
        item = db.query(Item).filter(Item.item_id == item_id).one_or_none()
        if item is None:
            errors.append({"row": i, "message": f"unknown item_id {item_id}"})
            continue
        if not item.is_aftermarket_item:
            errors.append({"row": i, "message": f"{item_id} isn't an aftermarket item"})
            continue
        try:
            qty = int(row["qty"])
            unit_price = float(row["unit_price"])
            requested_date = datetime.strptime(row["requested_date"].strip(), "%Y-%m-%d").date()
            order_type = SalesOrderType((row.get("order_type") or "STANDARD").strip().upper())
            priority = int(row.get("priority") or 5)
        except ValueError as e:
            errors.append({"row": i, "message": f"invalid value: {e}"})
            continue
        if qty <= 0 or unit_price <= 0:
            errors.append({"row": i, "message": "qty and unit_price must be positive"})
            continue

        next_seq += 1
        db.add(SalesOrder(order_id=f"SO-{next_seq:06d}", customer=row["customer"].strip(),
                           item_id=item_id, qty=qty, unit_price=unit_price, order_type=order_type,
                           requested_date=requested_date, priority=priority))
        created += 1

    db.commit()
    return {"total_rows": len(rows), "created": created, "errors": errors, "error_count": len(errors)}


@router.get("/templates/{kind}")
def download_template(kind: str) -> dict:
    """Column reference for each import type, shown in the UI rather than
    shipped as a separate downloadable file (the sandbox blocks file
    downloads from artifacts, and this is simple enough to render inline)."""
    templates = {
        "items": {
            "required": ["item_id", "description", "item_type", "make_or_buy"],
            "optional": ["uom", "standard_cost", "default_lead_time_days",
                         "is_project_item", "is_aftermarket_item"],
            "item_type_values": [t.value for t in ItemType],
            "make_or_buy_values": [t.value for t in MakeOrBuy],
        },
        "inventory": {
            "required": ["item_id", "qty_on_hand"],
            "optional": ["location (default MAIN)", "qty_allocated (default 0)"],
        },
        "sales-orders": {
            "required": ["customer", "item_id", "qty", "unit_price", "requested_date (YYYY-MM-DD)"],
            "optional": ["order_type (STANDARD/EMERGENCY, default STANDARD)", "priority (1-10, default 5)"],
        },
    }
    if kind not in templates:
        raise HTTPException(status_code=404, detail=f"No template for '{kind}'")
    return templates[kind]
