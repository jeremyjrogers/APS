import { useEffect, useState } from "react";
import { api, type SalesOrder } from "../api";
import { money } from "../format";
import Pagination from "./Pagination";

const LIMIT = 50;

function emptyForm() {
  return {
    customer: "", item_id: "", qty: 1, unit_price: 0,
    order_type: "STANDARD", requested_date: new Date().toISOString().slice(0, 10), priority: 5,
  };
}

export default function SalesOrdersTable() {
  const [rows, setRows] = useState<SalesOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [orderType, setOrderType] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<ReturnType<typeof emptyForm> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api
      .salesOrders({ order_type: orderType || undefined, limit: LIMIT, offset })
      .then((res) => {
        setRows(res.rows);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }
  useEffect(load, [orderType, offset]);

  async function submit() {
    if (!form) return;
    setError(null);
    setBusy(true);
    try {
      if (!form.customer || !form.item_id) throw new Error("customer and item_id are required");
      await api.createSalesOrder(form);
      setForm(null);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel-header">
        <h2>Sales Orders</h2>
        <div className="filter-group">
          {["", "STANDARD", "EMERGENCY"].map((s) => (
            <button
              key={s}
              className={s === orderType ? "chip chip-active" : "chip"}
              onClick={() => {
                setOrderType(s);
                setOffset(0);
              }}
            >
              {s || "ALL"}
            </button>
          ))}
        </div>
        <button onClick={() => { setForm(emptyForm()); setError(null); }}>+ New Order</button>
      </div>

      {form && (
        <div className="panel form-panel">
          <h3>New Sales Order</h3>
          <p className="muted">Item must already be flagged as an aftermarket item in Master Data.</p>
          <div className="form-grid">
            <Field label="Customer">
              <input value={form.customer} onChange={(e) => setForm({ ...form, customer: e.target.value })} />
            </Field>
            <Field label="Item ID">
              <input value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })} placeholder="e.g. MP-SHAFT-M" />
            </Field>
            <Field label="Qty">
              <input type="number" value={form.qty} onChange={(e) => setForm({ ...form, qty: Number(e.target.value) })} />
            </Field>
            <Field label="Unit Price ($)">
              <input type="number" step="0.01" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: Number(e.target.value) })} />
            </Field>
            <Field label="Type">
              <select value={form.order_type} onChange={(e) => setForm({ ...form, order_type: e.target.value })}>
                <option value="STANDARD">STANDARD</option>
                <option value="EMERGENCY">EMERGENCY</option>
              </select>
            </Field>
            <Field label="Requested Date">
              <input type="date" value={form.requested_date} onChange={(e) => setForm({ ...form, requested_date: e.target.value })} />
            </Field>
            <Field label="Priority (1=urgent, 10=low)">
              <input type="number" min={1} max={10} value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button disabled={busy} onClick={submit}>Create Order</button>
            <button className="secondary" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Order</th>
            <th>Customer</th>
            <th>Item</th>
            <th>Qty</th>
            <th>Unit Price</th>
            <th>Type</th>
            <th>Requested Date</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.order_id}>
              <td>{r.order_id}</td>
              <td>{r.customer}</td>
              <td>{r.item_id}</td>
              <td>{r.qty}</td>
              <td>{money(r.unit_price)}</td>
              <td>
                <span className={`badge badge-${r.order_type.toLowerCase()}`}>{r.order_type}</span>
              </td>
              <td>{r.requested_date}</td>
              <td>{r.priority}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading && <div className="loading">Loading...</div>}
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
