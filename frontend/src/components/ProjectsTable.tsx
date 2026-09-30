import { useEffect, useState } from "react";
import { api, type MachineType, type Project } from "../api";
import { money } from "../format";
import Pagination from "./Pagination";

const LIMIT = 50;

export default function ProjectsTable() {
  const [rows, setRows] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [machineTypes, setMachineTypes] = useState<MachineType[]>([]);

  const [quoteForm, setQuoteForm] = useState<{ customer: string; machine_type_id: string; project_type: string; quoted_value: number } | null>(null);
  const [firmingId, setFirmingId] = useState<string | null>(null);
  const [firmForm, setFirmForm] = useState<{ contract_date: string; contract_value: number }>({ contract_date: "", contract_value: 0 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api
      .projects({ status: status || undefined, limit: LIMIT, offset })
      .then((res) => {
        setRows(res.rows);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }
  useEffect(load, [status, offset]);
  useEffect(() => { api.machineTypes().then(setMachineTypes); }, []);

  async function submitQuote() {
    if (!quoteForm) return;
    setError(null);
    setBusy(true);
    try {
      if (!quoteForm.customer || !quoteForm.machine_type_id) throw new Error("customer and machine type are required");
      await api.createProjectQuote(quoteForm);
      setQuoteForm(null);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function startFirm(projectId: string) {
    setFirmingId(projectId);
    setFirmForm({ contract_date: new Date().toISOString().slice(0, 10), contract_value: 0 });
    setError(null);
  }

  async function submitFirm() {
    if (!firmingId) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api.firmProject(firmingId, {
        contract_date: firmForm.contract_date,
        contract_value: firmForm.contract_value || undefined,
      });
      setFirmingId(null);
      load();
      alert(`${firmingId} is FIRM. Created ${res.fg_item_id} with ${res.bom_lines} BOM lines and ${res.routing_operations} routing ops.`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel-header">
        <h2>Projects</h2>
        <div className="filter-group">
          {["", "FIRM", "QUOTED", "LOST", "CANCELLED"].map((s) => (
            <button
              key={s}
              className={s === status ? "chip chip-active" : "chip"}
              onClick={() => {
                setStatus(s);
                setOffset(0);
              }}
            >
              {s || "ALL"}
            </button>
          ))}
        </div>
        <button onClick={() => { setQuoteForm({ customer: "", machine_type_id: machineTypes[0]?.machine_type_id ?? "", project_type: "ETO", quoted_value: 0 }); setError(null); }}>
          + New Quote
        </button>
      </div>

      {quoteForm && (
        <div className="panel form-panel">
          <h3>New Project Quote</h3>
          <p className="muted">
            Quotes carry a rough-cut estimate only — no BOM exists until the project is firmed, since
            engineering hasn't designed anything yet.
          </p>
          <div className="form-grid">
            <Field label="Customer">
              <input value={quoteForm.customer} onChange={(e) => setQuoteForm({ ...quoteForm, customer: e.target.value })} />
            </Field>
            <Field label="Machine Type">
              <select value={quoteForm.machine_type_id} onChange={(e) => setQuoteForm({ ...quoteForm, machine_type_id: e.target.value })}>
                {machineTypes.map((mt) => <option key={mt.machine_type_id} value={mt.machine_type_id}>{mt.name}</option>)}
              </select>
            </Field>
            <Field label="Project Type">
              <select value={quoteForm.project_type} onChange={(e) => setQuoteForm({ ...quoteForm, project_type: e.target.value })}>
                <option value="ETO">ETO</option>
                <option value="CTO">CTO</option>
              </select>
            </Field>
            <Field label="Quoted Value ($)">
              <input type="number" value={quoteForm.quoted_value} onChange={(e) => setQuoteForm({ ...quoteForm, quoted_value: Number(e.target.value) })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button disabled={busy} onClick={submitQuote}>Create Quote</button>
            <button className="secondary" onClick={() => setQuoteForm(null)}>Cancel</button>
          </div>
        </div>
      )}

      {firmingId && (
        <div className="panel form-panel">
          <h3>Firm Up {firmingId}</h3>
          <p className="muted">
            Won it. This creates the real top-level item, clones the machine type's template BOM and
            routing into an instance, and lays down milestones.
          </p>
          <div className="form-grid">
            <Field label="Contract Date">
              <input type="date" value={firmForm.contract_date} onChange={(e) => setFirmForm({ ...firmForm, contract_date: e.target.value })} />
            </Field>
            <Field label="Contract Value ($)">
              <input type="number" value={firmForm.contract_value} onChange={(e) => setFirmForm({ ...firmForm, contract_value: Number(e.target.value) })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button disabled={busy} onClick={submitFirm}>Firm Up</button>
            <button className="secondary" onClick={() => setFirmingId(null)}>Cancel</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Customer</th>
            <th>Type</th>
            <th>Machine Type</th>
            <th>Status</th>
            <th>Contract Date</th>
            <th>Due Date</th>
            <th>Value</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.project_id}>
              <td>{r.project_id}</td>
              <td>{r.customer}</td>
              <td>{r.project_type}</td>
              <td>{r.machine_type_id}</td>
              <td>
                <span className={`badge badge-${r.status.toLowerCase()}`}>{r.status}</span>
              </td>
              <td>{r.contract_date ?? "-"}</td>
              <td>{r.contract_due_date ?? "-"}</td>
              <td>{money(r.contract_value ?? r.quoted_value ?? 0)}</td>
              <td className="action-cell">
                {r.status === "QUOTED" && <button onClick={() => startFirm(r.project_id)}>Firm Up</button>}
              </td>
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
