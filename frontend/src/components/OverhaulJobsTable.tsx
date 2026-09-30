import { useEffect, useState } from "react";
import { api, type OverhaulJob } from "../api";
import { money } from "../format";
import Pagination from "./Pagination";

const LIMIT = 50;
const STATUS_ORDER = ["RECEIVED", "TEARDOWN", "INSPECTION", "AWAITING_APPROVAL", "APPROVED", "IN_REPAIR", "TEST", "COMPLETE"];
const STATUSES = ["", ...STATUS_ORDER];

interface FindingDraft {
  item_id: string;
  recommended_action: string;
  qty: number;
  source: string;
}

export default function OverhaulJobsTable() {
  const [rows, setRows] = useState<OverhaulJob[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const [newForm, setNewForm] = useState<{ customer: string; asset_id: string; received_date: string } | null>(null);
  const [advancing, setAdvancing] = useState<OverhaulJob | null>(null);
  const [advanceStatus, setAdvanceStatus] = useState("");
  const [estimatedValue, setEstimatedValue] = useState<number>(0);
  const [findings, setFindings] = useState<FindingDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api
      .overhaulJobs({ status: status || undefined, limit: LIMIT, offset })
      .then((res) => {
        setRows(res.rows);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }
  useEffect(load, [status, offset]);

  async function submitNew() {
    if (!newForm) return;
    setError(null);
    setBusy(true);
    try {
      if (!newForm.customer || !newForm.asset_id) throw new Error("customer and asset_id are required");
      await api.createOverhaulJob(newForm);
      setNewForm(null);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function startAdvance(job: OverhaulJob) {
    setAdvancing(job);
    const idx = STATUS_ORDER.indexOf(job.status);
    setAdvanceStatus(STATUS_ORDER[Math.min(idx + 1, STATUS_ORDER.length - 1)]);
    setEstimatedValue(job.estimated_value ?? 0);
    setFindings([]);
    setError(null);
  }

  function addFinding() {
    setFindings([...findings, { item_id: "", recommended_action: "REPLACE", qty: 1, source: "BUY" }]);
  }
  function updateFinding(i: number, patch: Partial<FindingDraft>) {
    setFindings(findings.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  }
  function removeFinding(i: number) {
    setFindings(findings.filter((_, idx) => idx !== i));
  }

  async function submitAdvance() {
    if (!advancing) return;
    setError(null);
    setBusy(true);
    try {
      const cleanFindings = findings.filter((f) => f.item_id.trim());
      const res = await api.advanceOverhaulJob(advancing.job_id, {
        status: advanceStatus,
        estimated_value: estimatedValue || undefined,
        findings: cleanFindings,
      });
      setAdvancing(null);
      load();
      if (res.findings_added > 0) alert(`${advancing.job_id} -> ${res.status}, ${res.findings_added} finding(s) added`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const findingsAllowed = advanceStatus !== "RECEIVED" && advanceStatus !== "TEARDOWN";

  return (
    <div>
      <div className="panel-header">
        <h2>Overhaul Jobs</h2>
        <div className="filter-group">
          {STATUSES.map((s) => (
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
        <button onClick={() => { setNewForm({ customer: "", asset_id: "", received_date: new Date().toISOString().slice(0, 10) }); setError(null); }}>
          + New Job
        </button>
      </div>
      <p className="muted">
        Findings/parts demand only exists once a job passes INSPECTION; only APPROVED / IN_REPAIR /
        TEST jobs feed the planning engine (AWAITING_APPROVAL is a hold on elapsed time, not
        capacity).
      </p>

      {newForm && (
        <div className="panel form-panel">
          <h3>New Overhaul Job</h3>
          <div className="form-grid">
            <Field label="Customer">
              <input value={newForm.customer} onChange={(e) => setNewForm({ ...newForm, customer: e.target.value })} />
            </Field>
            <Field label="Asset ID">
              <input value={newForm.asset_id} onChange={(e) => setNewForm({ ...newForm, asset_id: e.target.value })} />
            </Field>
            <Field label="Received Date">
              <input type="date" value={newForm.received_date} onChange={(e) => setNewForm({ ...newForm, received_date: e.target.value })} />
            </Field>
          </div>
          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button disabled={busy} onClick={submitNew}>Create Job</button>
            <button className="secondary" onClick={() => setNewForm(null)}>Cancel</button>
          </div>
        </div>
      )}

      {advancing && (
        <div className="panel form-panel">
          <h3>Advance {advancing.job_id} (currently {advancing.status})</h3>
          <div className="form-grid">
            <Field label="New Status">
              <select value={advanceStatus} onChange={(e) => setAdvanceStatus(e.target.value)}>
                {STATUS_ORDER.slice(STATUS_ORDER.indexOf(advancing.status)).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </Field>
            <Field label="Estimated Value ($)">
              <input type="number" value={estimatedValue} onChange={(e) => setEstimatedValue(Number(e.target.value))} />
            </Field>
          </div>

          {findingsAllowed && (
            <div className="findings-editor">
              <div className="findings-header">
                <span className="field-label">Findings</span>
                <button className="secondary" onClick={addFinding}>+ Add finding</button>
              </div>
              {findings.map((f, i) => (
                <div key={i} className="finding-row">
                  <input placeholder="item_id" value={f.item_id} onChange={(e) => updateFinding(i, { item_id: e.target.value })} />
                  <select value={f.recommended_action} onChange={(e) => updateFinding(i, { recommended_action: e.target.value })}>
                    <option value="REPLACE">REPLACE</option>
                    <option value="REPAIR">REPAIR</option>
                    <option value="REUSE">REUSE</option>
                  </select>
                  <input type="number" min={1} value={f.qty} onChange={(e) => updateFinding(i, { qty: Number(e.target.value) })} />
                  <select value={f.source} onChange={(e) => updateFinding(i, { source: e.target.value })}>
                    <option value="BUY">BUY</option>
                    <option value="MAKE">MAKE</option>
                    <option value="INVENTORY">INVENTORY</option>
                  </select>
                  <button className="secondary" onClick={() => removeFinding(i)}>Remove</button>
                </div>
              ))}
            </div>
          )}

          {error && <div className="error inline-error">{error}</div>}
          <div className="form-actions">
            <button disabled={busy} onClick={submitAdvance}>Save</button>
            <button className="secondary" onClick={() => setAdvancing(null)}>Cancel</button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Job</th>
            <th>Customer</th>
            <th>Asset</th>
            <th>Received</th>
            <th>Status</th>
            <th>Est. Value</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.job_id}>
              <td>{r.job_id}</td>
              <td>{r.customer}</td>
              <td>{r.asset_id}</td>
              <td>{r.received_date}</td>
              <td>
                <span className={`badge badge-${r.status.toLowerCase()}`}>{r.status}</span>
              </td>
              <td>{r.estimated_value != null ? money(r.estimated_value) : "-"}</td>
              <td className="action-cell">
                {r.status !== "COMPLETE" && <button onClick={() => startAdvance(r)}>Advance</button>}
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
