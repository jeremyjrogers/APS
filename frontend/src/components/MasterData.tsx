import { useEffect, useState } from "react";
import { api, type InventoryRow, type MasterItem, type MasterSupplier, type WorkCenterRef } from "../api";
import { money, num } from "../format";
import Pagination from "./Pagination";

const SECTIONS = ["Items", "Suppliers", "Work Centers", "Inventory"] as const;
type Section = (typeof SECTIONS)[number];

export default function MasterData() {
  const [section, setSection] = useState<Section>("Items");
  return (
    <div>
      <div className="panel-header">
        <h2>Master Data</h2>
        <div className="filter-group">
          {SECTIONS.map((s) => (
            <button key={s} className={s === section ? "chip chip-active" : "chip"} onClick={() => setSection(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>
      {section === "Items" && <ItemsSection />}
      {section === "Suppliers" && <SuppliersSection />}
      {section === "Work Centers" && <WorkCentersSection />}
      {section === "Inventory" && <InventorySection />}
    </div>
  );
}

const ITEM_TYPES = ["RAW_MATERIAL", "PURCHASED_COMPONENT", "MANUFACTURED_PART", "SUBASSEMBLY", "FINISHED_PACKAGE"];
const MAKE_OR_BUY = ["MAKE", "BUY"];

function emptyItem(): Partial<MasterItem> {
  return {
    item_id: "", description: "", item_type: "MANUFACTURED_PART", make_or_buy: "MAKE",
    uom: "EA", standard_cost: 0, default_lead_time_days: 0,
    is_project_item: false, is_aftermarket_item: false,
  };
}

function ItemsSection() {
  const [rows, setRows] = useState<MasterItem[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [form, setForm] = useState<Partial<MasterItem> | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const LIMIT = 50;

  function load() {
    api.masterItems({ q: q || undefined, limit: LIMIT, offset }).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
    });
  }
  useEffect(load, [q, offset]);

  function startCreate() {
    setEditing(null);
    setForm(emptyItem());
    setError(null);
  }
  function startEdit(item: MasterItem) {
    setEditing(item.item_id);
    setForm({ ...item });
    setError(null);
  }

  async function save() {
    if (!form) return;
    setError(null);
    try {
      if (editing) {
        await api.updateItem(editing, form);
      } else {
        if (!form.item_id || !form.description) throw new Error("item_id and description are required");
        await api.createItem(form);
      }
      setForm(null);
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  async function remove(itemId: string) {
    if (!confirm(`Delete item ${itemId}?`)) return;
    try {
      await api.deleteItem(itemId);
      load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <div>
      <div className="panel-header">
        <input className="text-input" placeholder="Search items..." value={q}
               onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
        <button onClick={startCreate}>+ New Item</button>
      </div>

      {form && (
        <div className="panel form-panel">
          <h3>{editing ? `Edit ${editing}` : "New Item"}</h3>
          <div className="form-grid">
            {!editing && (
              <Field label="Item ID">
                <input value={form.item_id ?? ""} onChange={(e) => setForm({ ...form, item_id: e.target.value })} />
              </Field>
            )}
            <Field label="Description">
              <input value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            <Field label="Type">
              <select value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value })}>
                {ITEM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Make/Buy">
              <select value={form.make_or_buy} onChange={(e) => setForm({ ...form, make_or_buy: e.target.value })}>
                {MAKE_OR_BUY.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Standard Cost">
              <input type="number" step="0.01" value={form.standard_cost ?? 0}
                     onChange={(e) => setForm({ ...form, standard_cost: Number(e.target.value) })} />
            </Field>
            <Field label="Lead Time (days)">
              <input type="number" value={form.default_lead_time_days ?? 0}
                     onChange={(e) => setForm({ ...form, default_lead_time_days: Number(e.target.value) })} />
            </Field>
            <Field label="Project item?">
              <input type="checkbox" checked={!!form.is_project_item}
                     onChange={(e) => setForm({ ...form, is_project_item: e.target.checked })} />
            </Field>
            <Field label="Aftermarket item?">
              <input type="checkbox" checked={!!form.is_aftermarket_item}
                     onChange={(e) => setForm({ ...form, is_aftermarket_item: e.target.checked })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button onClick={save}>{editing ? "Save" : "Create"}</button>
            <button className="secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Item ID</th><th>Description</th><th>Type</th><th>Make/Buy</th>
            <th>Cost</th><th>Lead Time</th><th>Flags</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.item_id}>
              <td>{r.item_id}</td>
              <td>{r.description}</td>
              <td>{r.item_type}</td>
              <td>{r.make_or_buy}</td>
              <td>{money(r.standard_cost)}</td>
              <td>{r.default_lead_time_days}d</td>
              <td>
                {r.is_project_item && <span className="badge">PROJECT</span>}{" "}
                {r.is_aftermarket_item && <span className="badge">AFTERMARKET</span>}
              </td>
              <td className="action-cell">
                <button onClick={() => startEdit(r)}>Edit</button>
                <button onClick={() => remove(r.item_id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination offset={offset} limit={LIMIT} total={total} onOffsetChange={setOffset} />
    </div>
  );
}

function SuppliersSection() {
  const [rows, setRows] = useState<MasterSupplier[]>([]);
  const [form, setForm] = useState<MasterSupplier | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.masterSuppliers().then(setRows);
  }
  useEffect(load, []);

  async function save() {
    if (!form) return;
    setError(null);
    try {
      if (editing) {
        await api.updateSupplier(editing, { name: form.name, reliability_rating: form.reliability_rating });
      } else {
        if (!form.supplier_id || !form.name) throw new Error("supplier_id and name are required");
        await api.createSupplier(form);
      }
      setForm(null);
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  async function remove(id: string) {
    if (!confirm(`Delete supplier ${id}?`)) return;
    try {
      await api.deleteSupplier(id);
      load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <div>
      <div className="panel-header">
        <span />
        <button onClick={() => { setEditing(null); setForm({ supplier_id: "", name: "", reliability_rating: null }); }}>
          + New Supplier
        </button>
      </div>
      {form && (
        <div className="panel form-panel">
          <h3>{editing ? `Edit ${editing}` : "New Supplier"}</h3>
          <div className="form-grid">
            {!editing && (
              <Field label="Supplier ID">
                <input value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })} />
              </Field>
            )}
            <Field label="Name">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Reliability (0-1)">
              <input type="number" step="0.01" min="0" max="1" value={form.reliability_rating ?? ""}
                     onChange={(e) => setForm({ ...form, reliability_rating: e.target.value ? Number(e.target.value) : null })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button onClick={save}>{editing ? "Save" : "Create"}</button>
            <button className="secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}
      <table className="data-table">
        <thead><tr><th>ID</th><th>Name</th><th>Reliability</th><th></th></tr></thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.supplier_id}>
              <td>{s.supplier_id}</td>
              <td>{s.name}</td>
              <td>{s.reliability_rating != null ? `${(s.reliability_rating * 100).toFixed(0)}%` : "-"}</td>
              <td className="action-cell">
                <button onClick={() => { setEditing(s.supplier_id); setForm({ ...s }); setError(null); }}>Edit</button>
                <button onClick={() => remove(s.supplier_id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const AREAS = ["NEW_UNIT", "AFTERMARKET", "SHARED"];

function WorkCentersSection() {
  const [rows, setRows] = useState<WorkCenterRef[]>([]);
  const [form, setForm] = useState<{ work_center_id: string; name: string; area: string; hourly_rate: number; daily_hours: number } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  function load() {
    api.workCenters().then(setRows);
  }
  useEffect(load, []);

  async function save() {
    if (!form) return;
    setError(null);
    try {
      if (editing) {
        await api.updateWorkCenter(editing, { name: form.name, hourly_rate: form.hourly_rate });
        setResult(null);
      } else {
        if (!form.work_center_id || !form.name) throw new Error("work_center_id and name are required");
        const res = await api.createWorkCenter(form);
        setResult(`Seeded ${res.calendar_days_seeded} calendar days for ${res.work_center_id}`);
      }
      setForm(null);
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <div className="panel-header">
        <span />
        <button onClick={() => { setEditing(null); setForm({ work_center_id: "", name: "", area: "AFTERMARKET", hourly_rate: 85, daily_hours: 8 }); setResult(null); }}>
          + New Work Center
        </button>
      </div>
      {result && <div className="muted result-note">{result}</div>}
      {form && (
        <div className="panel form-panel">
          <h3>{editing ? `Edit ${editing}` : "New Work Center"}</h3>
          <div className="form-grid">
            {!editing && (
              <Field label="Work Center ID">
                <input value={form.work_center_id} onChange={(e) => setForm({ ...form, work_center_id: e.target.value })} />
              </Field>
            )}
            <Field label="Name">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            {!editing && (
              <Field label="Area">
                <select value={form.area} onChange={(e) => setForm({ ...form, area: e.target.value })}>
                  {AREAS.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </Field>
            )}
            <Field label="Hourly Rate ($)">
              <input type="number" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: Number(e.target.value) })} />
            </Field>
            {!editing && (
              <Field label="Daily Capacity (hrs)">
                <input type="number" value={form.daily_hours} onChange={(e) => setForm({ ...form, daily_hours: Number(e.target.value) })} />
              </Field>
            )}
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button onClick={save}>{editing ? "Save" : "Create"}</button>
            <button className="secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}
      <table className="data-table">
        <thead><tr><th>ID</th><th>Name</th><th>Area</th><th>Hourly Rate</th><th></th></tr></thead>
        <tbody>
          {rows.map((wc) => (
            <tr key={wc.work_center_id}>
              <td>{wc.work_center_id}</td>
              <td>{wc.name}</td>
              <td><span className="badge">{wc.area}</span></td>
              <td>{money(wc.hourly_rate)}</td>
              <td className="action-cell">
                <button onClick={() => {
                  setEditing(wc.work_center_id);
                  setForm({ work_center_id: wc.work_center_id, name: wc.name, area: wc.area, hourly_rate: wc.hourly_rate, daily_hours: 8 });
                  setError(null);
                }}>Edit</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InventorySection() {
  const [rows, setRows] = useState<InventoryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [form, setForm] = useState<{ item_id: string; location: string; qty_on_hand: number; qty_allocated: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const LIMIT = 50;

  function load() {
    api.masterInventory({ q: q || undefined, limit: LIMIT, offset }).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
    });
  }
  useEffect(load, [q, offset]);

  async function save() {
    if (!form) return;
    setError(null);
    try {
      await api.upsertInventory(form);
      setForm(null);
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this inventory row?")) return;
    try {
      await api.deleteInventory(id);
      load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <div>
      <div className="panel-header">
        <input className="text-input" placeholder="Search item..." value={q}
               onChange={(e) => { setQ(e.target.value); setOffset(0); }} />
        <button onClick={() => { setForm({ item_id: "", location: "MAIN", qty_on_hand: 0, qty_allocated: 0 }); setError(null); }}>
          + Set Inventory
        </button>
      </div>
      <p className="muted">
        Posting with an item_id/location that already exists updates it in place — this is how you record a
        physical count or receipt.
      </p>
      {form && (
        <div className="panel form-panel">
          <h3>Set Inventory</h3>
          <div className="form-grid">
            <Field label="Item ID">
              <input value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })} />
            </Field>
            <Field label="Location">
              <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </Field>
            <Field label="Qty On Hand">
              <input type="number" value={form.qty_on_hand} onChange={(e) => setForm({ ...form, qty_on_hand: Number(e.target.value) })} />
            </Field>
            <Field label="Qty Allocated">
              <input type="number" value={form.qty_allocated} onChange={(e) => setForm({ ...form, qty_allocated: Number(e.target.value) })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button onClick={save}>Save</button>
            <button className="secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}
      <table className="data-table">
        <thead><tr><th>Item</th><th>Location</th><th>On Hand</th><th>Allocated</th><th>Available</th><th></th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.item_id}</td>
              <td>{r.location}</td>
              <td>{num(r.qty_on_hand)}</td>
              <td>{num(r.qty_allocated)}</td>
              <td>{num(r.qty_on_hand - r.qty_allocated)}</td>
              <td className="action-cell">
                <button onClick={() => { setForm({ item_id: r.item_id, location: r.location, qty_on_hand: r.qty_on_hand, qty_allocated: r.qty_allocated }); setError(null); }}>Edit</button>
                <button onClick={() => remove(r.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination offset={offset} limit={LIMIT} total={total} onOffsetChange={setOffset} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
