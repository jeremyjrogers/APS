# Domain Model

Single-plant pump/compressor manufacturer with two operational lines that share
an item master and, in places, shop-floor capacity.

## Business context

- **New Unit Bays** — builds pump/compressor packages (bare unit on skid, motor,
  electrical, lube oil system). ~50 projects/year. Mostly Engineer-to-Order
  (ETO), smaller share Configure-to-Order (CTO).
- **Aftermarket Repair/Overhaul** — manufactures spare/service parts and
  repairs/overhauls customer units in the field or returned to the plant.
  ~$120M/year volume.
- The two lines run mostly separate routings and resources, **except**: some
  machining resources (e.g. impeller/inducer/shaft finishing) are shared and
  contended by both lines. New units also pull certain components (impellers,
  inducers, etc.) that are drawn from the same pool aftermarket uses.
- **Single item master** across both lines — a given part is the same item
  whether it lands in a new skid or ships as a spare.
- Scale target for synthetic data: dozens of end-item packages/configurations,
  dozens of spare/service parts, dozens of work centers.

## Core reference data

### Plant
- `plant_id`, `name` — single plant for now; modeled as an entity so it isn't
  hardcoded, in case phase 2+ adds locations.

### WorkCenter
- `work_center_id`, `name`, `area` (`NEW_UNIT` | `AFTERMARKET` | `SHARED`),
  `capacity_uom` (e.g. hours/day), `hourly_rate`
- Shared work centers are the explicit capacity-contention point between the
  two lines — the planning engine must net demand from both against the same
  calendar.

### Calendar / Capacity
- `work_center_id`, `date`, `available_hours` (supports shift patterns,
  holidays, planned downtime)

### Supplier
- `supplier_id`, `name`, `reliability_rating`

### Item
- `item_id`, `description`, `item_type` (`RAW_MATERIAL` | `PURCHASED_COMPONENT`
  | `MANUFACTURED_PART` | `SUBASSEMBLY` | `FINISHED_PACKAGE`)
- `make_or_buy` (`MAKE` | `BUY`)
- `uom`, `standard_cost`, `default_lead_time_days`
- `is_project_item` (bool) — usable in project BOMs
- `is_aftermarket_item` (bool) — sellable/stockable as a spare
- `reorder_point`, `reorder_qty`, `safety_stock` — for stocked aftermarket
  items only
- Big purchased items (skids, motors, shafts, gearboxes, castings) are `BUY`
  with `MANUFACTURED_PART`/`SUBASSEMBLY` items downstream representing
  in-house final machining/assembly on top of them.

### ItemSupplier
- `item_id`, `supplier_id`, `lead_time_days`, `price`, `is_preferred`
  (supports multi-sourcing)

## BOM & Routing

### BOM
- `bom_id`, `parent_item_id`, `bom_type` (`PROJECT_TEMPLATE` |
  `PROJECT_INSTANCE` | `STANDARD`), `version`, `effective_from`, `effective_to`
- `PROJECT_TEMPLATE` — the CTO starting point (a configurable family, e.g.
  "compressor package, 3 skid sizes, optional lube oil skid")
- `PROJECT_INSTANCE` — the as-built BOM for one project (ETO: built mostly
  from scratch per contract; CTO: template + selected options, still captured
  as its own instance so it can deviate)
- `STANDARD` — aftermarket manufactured parts/kits, normal versioned BOM

### BOMLine
- `bom_id`, `component_item_id`, `qty_per`, `scrap_pct`

### Routing
- `routing_id`, `item_id`, `routing_type` (`NEW_UNIT` | `AFTERMARKET_MFG` |
  `OVERHAUL`)

### RoutingOperation
- `routing_id`, `seq`, `work_center_id`, `setup_time`, `run_time_per_unit`,
  `description`

## Projects (ETO/CTO)

### MachineType
- `machine_type_id`, `name` (e.g. "API 610 horizontal pump package, mid
  frame", "screw compressor package w/ lube oil skid")
- Reference profile built from historical project actuals, used for
  quote-stage rough-cut capacity checks before a design exists:
  - `avg_engineering_hours`
  - `avg_assembly_hours`, `avg_test_hours` (typically New Unit Bay)
  - `avg_shared_machining_hours` (the contended resource pool)
  - `avg_lead_time_weeks` (quote-to-ship, historical)
- This is intentionally coarse (a profile, not a routing) — it exists so a
  `QUOTED` project has *something* to check against plant capacity before
  engineering produces a real BOM/routing.

### Project
- `project_id`, `customer`, `project_type` (`ETO` | `CTO`), `machine_type_id`,
  `status` (`QUOTED` | `FIRM` | `LOST` | `CANCELLED`)
- `contract_date`, `contract_due_date` — populated on firming
- Links to a `PROJECT_INSTANCE` BOM once `FIRM` (the top-level
  `FINISHED_PACKAGE` item); `QUOTED` projects instead reference their
  `MachineType`'s rough-cut profile, scaled/adjusted per opportunity as
  needed (e.g. sales estimates a size/complexity multiplier)

### ProjectMilestone
- `project_id`, `milestone_name` (e.g. design freeze, procurement release,
  assembly start, test, ship), `planned_date`, `actual_date`
- Only meaningful once `FIRM`

Demand for a project is driven by the won contract's due date and milestones,
not a forecast — it's firm from the point of contract signature (mostly
recognized on firm PO received). `QUOTED` projects are not demand the phase-1
planning engine commits capacity/material against; they're inputs to the
capable-to-promise check (phase 2 what-if) that uses `MachineType` history to
estimate whether and when a new opportunity could be slotted in alongside
existing `FIRM` load.

## Aftermarket orders

### SalesOrder
- `order_id`, `customer`, `item_id`, `qty`, `order_type` (`STANDARD` |
  `EMERGENCY`), `requested_date`, `priority`
- `EMERGENCY` orders (breakdown/turnaround) carry hard lead-time pressure and
  need to be able to jump the queue / trigger expedite logic in the planning
  engine, distinct from `STANDARD` planned/longer-horizon orders.

## Overhaul / repair jobs

Overhaul is **not** a static BOM+routing work order — it's a stateful process
where the parts demand isn't known until inspection, and the job then holds
on customer approval (elapsed time, not resource time) before repair work can
be scheduled.

### OverhaulJob
- `job_id`, `customer`, `asset_id` (customer's unit/serial), `received_date`
- `status`: `RECEIVED` → `TEARDOWN` → `INSPECTION` → `AWAITING_APPROVAL` →
  `APPROVED` → `IN_REPAIR` → `TEST` → `COMPLETE`
- Teardown and inspection consume a known routing/work-center time regardless
  of findings. `AWAITING_APPROVAL` consumes elapsed calendar time, not
  work-center capacity, and its duration is uncertain — the plan needs to
  treat it as a hold, not a scheduled operation.

### OverhaulFinding
- `job_id`, `item_id`, `recommended_action` (`REPLACE` | `REPAIR` | `REUSE`),
  `qty`, `source` (`MAKE` | `BUY` | `INVENTORY`)
- Populated after inspection; once the job is `APPROVED`, findings marked
  `REPLACE`/`REPAIR` with source `MAKE`/`BUY` generate derived demand that
  feeds the same planning engine as project and aftermarket demand.

## Supply / execution

### PurchaseOrder / PurchaseOrderLine
- `item_id`, `qty`, `supplier_id`, `due_date`, `status`

### WorkOrder
- `item_id`, `qty`, `routing_id`, `start_date`, `due_date`, `status`
- Source-agnostic: created from project BOM explosion, aftermarket
  MRP/reorder logic, or approved overhaul findings

### Inventory
- `item_id`, `location`, `qty_on_hand`, `qty_allocated`

## Planning engine (phase 1 target)

Given:
- Demand: project milestones + aftermarket sales orders (standard and
  emergency) + approved overhaul findings
- Supply capability: BOMs, routings, work center capacity calendars
  (including shared work centers), supplier lead times, on-hand inventory

Produce: a time-phased supply plan (suggested purchase orders and work
orders) that is feasible against capacity and lead times, with emergency
aftermarket orders and contract milestones both able to compete for the same
shared machining capacity as new-unit builds.

Explicitly out of scope for phase 1: true concurrent (instant-renet)
planning — this is a batch/regenerative planning run, not a live shared
in-memory model. That's the phase 2 option under consideration.
