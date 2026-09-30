const API_BASE = "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST ${path} failed: ${res.status} ${detail}`);
  }
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`PUT ${path} failed: ${res.status} ${detail}`);
  }
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`DELETE ${path} failed: ${res.status} ${detail}`);
  }
  return res.json();
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`UPLOAD ${path} failed: ${res.status} ${detail}`);
  }
  return res.json();
}

export interface Summary {
  items: number;
  work_centers: number;
  suppliers: number;
  projects: {
    firm: number;
    quoted: number;
    lost: number;
    cancelled: number;
    firm_contract_value: number;
    quoted_pipeline_value: number;
  };
  sales_orders: { count: number; revenue: number };
  overhaul_jobs: { count: number; value: number };
  work_orders: number;
  purchase_orders: number;
}

export interface WeekLoad {
  week_start: string;
  load_hours: number;
  available_hours: number;
  utilization_pct: number;
  required_hours: number;
  required_pct: number;
  excess_hours: number;
}

export interface WorkCenterLoad {
  work_center_id: string;
  work_center_name: string;
  area: string;
  weeks: WeekLoad[];
  annual_load_hours: number;
  annual_available_hours: number;
  annual_utilization_pct: number;
  annual_required_hours: number;
  annual_required_pct: number;
  overloaded_weeks: number;
  total_excess_hours: number;
}

export interface OverloadedWeek {
  work_center_id: string;
  work_center_name: string;
  area: string;
  week_start: string;
  load_hours: number;
  available_hours: number;
  utilization_pct: number;
}

export interface PlanningRunResult {
  run_date: string;
  demand_count: number;
  planned_work_orders: number;
  planned_purchase_orders: number;
  exceptions: {
    created: number;
    updated: number;
    auto_resolved: number;
    open: number;
    total: number;
  };
  capacity_weeks_evaluated: number;
  overloaded_week_count: number;
  capacity_by_work_center: WorkCenterLoad[];
  top_overloaded: OverloadedWeek[];
}

export interface PlanException {
  exception_id: string;
  category: string;
  severity: string;
  status: string;
  message: string;
  item_id: string | null;
  source: string | null;
  source_ref: string | null;
  customer: string | null;
  work_center_id: string | null;
  days_late: number;
  value_at_risk: number;
  need_date: string | null;
  snooze_until: string | null;
  note: string | null;
}

export interface ExceptionsPage {
  total: number;
  total_value_at_risk: number;
  rows: PlanException[];
}

export interface SeveritySummary {
  by_severity: Record<string, { count: number; value_at_risk: number }>;
}

export interface PegNode {
  node_type: "WORK_ORDER" | "PURCHASE_ORDER";
  order_id: string;
  item_id: string;
  description: string;
  qty: number;
  start_date: string | null;
  due_date: string | null;
  status: string;
  bom_level: number;
  expedite_days: number;
  supplier_id: string | null;
  children: PegNode[];
}

export interface DemandInfo {
  type: string;
  ref: string;
  customer: string;
  due_date: string | null;
  value: number;
  order_type?: string;
  priority?: number;
  status?: string;
}

export interface PegTree {
  source_ref: string;
  demand: DemandInfo | null;
  total_orders: number;
  max_expedite_days: number;
  root_cause: Omit<PegNode, "children"> | null;
  tree: PegNode[];
}

export interface PlanActionRow {
  action_id: number;
  action_type: string;
  target_type: string;
  target_id: string;
  before_value: string | null;
  after_value: string | null;
  note: string | null;
  actor: string;
  created_at: string | null;
}

export interface Project {
  project_id: string;
  customer: string;
  project_type: string;
  machine_type_id: string;
  status: string;
  contract_date: string | null;
  contract_due_date: string | null;
  contract_value: number | null;
  quoted_value: number | null;
}

export interface SalesOrder {
  order_id: string;
  customer: string;
  item_id: string;
  qty: number;
  unit_price: number;
  order_type: string;
  requested_date: string;
  priority: number;
}

export interface OverhaulJob {
  job_id: string;
  customer: string;
  asset_id: string;
  received_date: string;
  status: string;
  estimated_value: number | null;
}

export interface WorkOrder {
  wo_id: string;
  item_id: string;
  qty: number;
  source: string;
  source_ref: string;
  start_date: string;
  due_date: string;
  status: string;
  projected_end?: string | null;
  capacity_delay_days?: number;
  expedite_days?: number;
}

export interface PurchaseOrderLine {
  item_id: string;
  qty: number;
  due_date: string;
}

export interface PurchaseOrder {
  po_id: string;
  supplier_id: string | null;
  status: string;
  lines: PurchaseOrderLine[];
}

export interface Paged<T> {
  total: number;
  rows: T[];
}

export interface WorkCenterRef {
  work_center_id: string;
  name: string;
  area: string;
  hourly_rate: number;
}

export interface MasterItem {
  item_id: string;
  description: string;
  item_type: string;
  make_or_buy: string;
  uom: string;
  standard_cost: number;
  default_lead_time_days: number;
  is_project_item: boolean;
  is_aftermarket_item: boolean;
  reorder_point: number | null;
  reorder_qty: number | null;
  safety_stock: number | null;
}

export interface MasterSupplier {
  supplier_id: string;
  name: string;
  reliability_rating: number | null;
}

export interface InventoryRow {
  id: number;
  item_id: string;
  location: string;
  qty_on_hand: number;
  qty_allocated: number;
}

export interface MachineType {
  machine_type_id: string;
  name: string;
  avg_lead_time_weeks: number;
  avg_engineering_hours: number;
  avg_assembly_hours: number;
  avg_test_hours: number;
}

export interface BomView {
  bom_id: number;
  parent_item_id: string;
  bom_type: string;
  version: string;
  lines: { component_item_id: string; qty_per: number; scrap_pct: number }[];
}

export interface RoutingView {
  routing_id: number;
  item_id: string;
  routing_type: string;
  operations: {
    seq: number;
    work_center_id: string;
    setup_time_hours: number;
    run_time_hours_per_unit: number;
    description: string | null;
  }[];
}

export interface ImportResult {
  total_rows: number;
  created: number;
  updated?: number;
  errors: { row: number; message: string }[];
  error_count: number;
}

export const api = {
  summary: () => get<Summary>("/summary"),
  workCenters: () => get<WorkCenterRef[]>("/reference/work-centers"),
  runPlanning: () => post<PlanningRunResult>("/planning/run"),
  projects: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<Project>>(`/demand/projects?${qs(params)}`),
  salesOrders: (params: { order_type?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<SalesOrder>>(`/demand/sales-orders?${qs(params)}`),
  overhaulJobs: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<OverhaulJob>>(`/demand/overhaul-jobs?${qs(params)}`),
  workOrders: (params: { source?: string; status?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<WorkOrder>>(`/supply/work-orders?${qs(params)}`),
  purchaseOrders: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<PurchaseOrder>>(`/supply/purchase-orders?${qs(params)}`),

  exceptions: (params: {
    status?: string;
    severity?: string;
    category?: string;
    source?: string;
    limit?: number;
    offset?: number;
  } = {}) => get<ExceptionsPage>(`/exceptions?${qs(params)}`),
  exceptionsSummary: () => get<SeveritySummary>("/exceptions/summary"),
  acknowledgeException: (id: string, note?: string) =>
    post<{ status: string }>(`/exceptions/${encodeURIComponent(id)}/acknowledge`, { note }),
  snoozeException: (id: string, snooze_days: number, note?: string) =>
    post<{ status: string }>(`/exceptions/${encodeURIComponent(id)}/snooze`, { snooze_days, note }),
  resolveException: (id: string, note?: string) =>
    post<{ status: string }>(`/exceptions/${encodeURIComponent(id)}/resolve`, { note }),

  pegDemand: (sourceRef: string) =>
    get<PegTree>(`/pegging/demand/${encodeURIComponent(sourceRef)}`),
  pegOrder: (orderId: string) =>
    get<{ order_id: string; source_ref: string | null; demand: DemandInfo | null; chain_to_root: PegNode[] }>(
      `/pegging/order/${encodeURIComponent(orderId)}`,
    ),

  expediteWorkOrder: (woId: string, pull_in_days: number, note?: string) =>
    post<WorkOrder>(`/supply/work-orders/${woId}/expedite`, { pull_in_days, note }),
  rescheduleWorkOrder: (woId: string, due_date: string, note?: string) =>
    post<WorkOrder>(`/supply/work-orders/${woId}/reschedule`, { due_date, note }),
  releaseWorkOrder: (woId: string) => post<WorkOrder>(`/supply/work-orders/${woId}/release`),
  releasePurchaseOrder: (poId: string) =>
    post<{ po_id: string; status: string }>(`/supply/purchase-orders/${poId}/release`),
  reschedulePurchaseOrder: (poId: string, due_date: string, note?: string) =>
    post<{ po_id: string; due_date: string }>(`/supply/purchase-orders/${poId}/reschedule`, {
      due_date,
      note,
    }),
  adjustCapacity: (body: {
    work_center_id: string;
    week_start: string;
    daily_hours: number;
    note?: string;
  }) => post<{ before: string; after: string }>("/reference/capacity", body),

  actions: (params: { limit?: number; offset?: number } = {}) =>
    get<Paged<PlanActionRow>>(`/actions?${qs(params)}`),

  // --- Master data ---
  masterItems: (params: { q?: string; item_type?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<MasterItem>>(`/master/items?${qs(params)}`),
  createItem: (body: Partial<MasterItem>) => post<MasterItem>("/master/items", body),
  updateItem: (itemId: string, body: Partial<MasterItem>) =>
    put<MasterItem>(`/master/items/${encodeURIComponent(itemId)}`, body),
  deleteItem: (itemId: string) => del<{ deleted: boolean }>(`/master/items/${encodeURIComponent(itemId)}`),

  masterSuppliers: () => get<MasterSupplier[]>("/master/suppliers"),
  createSupplier: (body: MasterSupplier) => post<MasterSupplier>("/master/suppliers", body),
  updateSupplier: (supplierId: string, body: { name: string; reliability_rating: number | null }) =>
    put<MasterSupplier>(`/master/suppliers/${encodeURIComponent(supplierId)}`, body),
  deleteSupplier: (supplierId: string) =>
    del<{ deleted: boolean }>(`/master/suppliers/${encodeURIComponent(supplierId)}`),

  createWorkCenter: (body: { work_center_id: string; name: string; area: string; hourly_rate: number; daily_hours: number }) =>
    post<{ work_center_id: string; calendar_days_seeded: number }>("/master/work-centers", body),
  updateWorkCenter: (wcId: string, body: { name?: string; hourly_rate?: number }) =>
    put<WorkCenterRef>(`/master/work-centers/${encodeURIComponent(wcId)}`, body),

  masterInventory: (params: { q?: string; limit?: number; offset?: number } = {}) =>
    get<Paged<InventoryRow>>(`/master/inventory?${qs(params)}`),
  upsertInventory: (body: { item_id: string; location?: string; qty_on_hand: number; qty_allocated?: number }) =>
    post<InventoryRow>("/master/inventory", body),
  deleteInventory: (id: number) => del<{ deleted: boolean }>(`/master/inventory/${id}`),

  getBom: (itemId: string) => get<BomView>(`/master/boms/${encodeURIComponent(itemId)}`),
  replaceBom: (itemId: string, body: { bom_type: string; version?: string; lines: { component_item_id: string; qty_per: number; scrap_pct?: number }[] }) =>
    put<{ bom_id: number; line_count: number }>(`/master/boms/${encodeURIComponent(itemId)}`, {
      parent_item_id: itemId,
      ...body,
    }),

  getRouting: (itemId: string) => get<RoutingView>(`/master/routings/${encodeURIComponent(itemId)}`),
  replaceRouting: (itemId: string, body: { routing_type: string; operations: RoutingView["operations"] }) =>
    put<{ routing_id: number; operation_count: number }>(`/master/routings/${encodeURIComponent(itemId)}`, {
      item_id: itemId,
      ...body,
    }),

  // --- Demand entry ---
  machineTypes: () => get<MachineType[]>("/master/machine-types"),
  createSalesOrder: (body: {
    customer: string; item_id: string; qty: number; unit_price: number;
    order_type?: string; requested_date: string; priority?: number;
  }) => post<{ order_id: string }>("/demand/sales-orders", body),
  createProjectQuote: (body: { customer: string; machine_type_id: string; project_type?: string; quoted_value?: number }) =>
    post<{ project_id: string }>("/demand/projects", body),
  firmProject: (projectId: string, body: { contract_date?: string; contract_value?: number; lead_time_variance?: number }) =>
    post<{ project_id: string; fg_item_id: string; bom_lines: number; routing_operations: number }>(
      `/demand/projects/${encodeURIComponent(projectId)}/firm`,
      body,
    ),
  createOverhaulJob: (body: { customer: string; asset_id: string; received_date?: string }) =>
    post<{ job_id: string }>("/demand/overhaul-jobs", body),
  advanceOverhaulJob: (
    jobId: string,
    body: {
      status: string;
      estimated_value?: number;
      findings?: { item_id: string; recommended_action: string; qty: number; source: string }[];
    },
  ) =>
    post<{ job_id: string; status: string; findings_added: number }>(
      `/demand/overhaul-jobs/${encodeURIComponent(jobId)}/advance`,
      body,
    ),

  // --- Import ---
  importItems: (file: File) => upload<ImportResult>("/import/items", file),
  importInventory: (file: File) => upload<ImportResult>("/import/inventory", file),
  importSalesOrders: (file: File) => upload<ImportResult>("/import/sales-orders", file),
  importTemplate: (kind: string) => get<Record<string, unknown>>(`/import/templates/${kind}`),
};

function qs(params: Record<string, string | number | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") parts.push(`${k}=${encodeURIComponent(v)}`);
  }
  return parts.join("&");
}
