import { useCallback, useEffect, useState } from "react";
import { api, type PlanException, type SeveritySummary } from "../api";
import { money, num } from "../format";
import Pagination from "./Pagination";

const LIMIT = 25;
const SEVERITIES = ["", "CRITICAL", "HIGH", "MEDIUM", "LOW"];
const CATEGORIES = [
  "",
  "CAPACITY_CONSTRAINED_LATE",
  "CAPACITY_INFEASIBLE",
  "PAST_DUE_PO_RELEASE",
  "PAST_DUE_WO_START",
  "CAPACITY_OVERLOAD",
  "NO_ROUTING",
];
const STATUSES = ["", "OPEN", "ACKNOWLEDGED", "SNOOZED", "RESOLVED"];

interface Props {
  onDrillDown: (sourceRef: string) => void;
}

export default function ExceptionsWorkbench({ onDrillDown }: Props) {
  const [rows, setRows] = useState<PlanException[]>([]);
  const [total, setTotal] = useState(0);
  const [valueAtRisk, setValueAtRisk] = useState(0);
  const [summary, setSummary] = useState<SeveritySummary | null>(null);
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.exceptions({
        severity: severity || undefined,
        category: category || undefined,
        status: status || undefined,
        limit: LIMIT,
        offset,
      }),
      api.exceptionsSummary(),
    ])
      .then(([page, sum]) => {
        setRows(page.rows);
        setTotal(page.total);
        setValueAtRisk(page.total_value_at_risk);
        setSummary(sum);
      })
      .finally(() => setLoading(false));
  }, [severity, category, status, offset]);

  useEffect(load, [load]);

  async function act(id: string, fn: () => Promise<unknown>) {
    setBusyId(id);
    try {
      await fn();
      load();
    } catch (e) {
      alert(String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="panel-header">
        <h2>Exception Workbench</h2>
        <span className="muted">
          {num(total)} open · {money(valueAtRisk)} at risk
        </span>
      </div>

      {summary && (
        <div className="card-grid">
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => {
            const entry = summary.by_severity[s];
            if (!entry) return null;
            return (
              <div key={s} className={`stat-card sev-card sev-${s.toLowerCase()}`}>
                <div className="stat-label">{s}</div>
                <div className="stat-value">{num(entry.count)}</div>
                <div className="stat-sub">{money(entry.value_at_risk)} at risk</div>
              </div>
            );
          })}
        </div>
      )}

      <div className="filter-row">
        <FilterSet label="Severity" options={SEVERITIES} value={severity} onChange={(v) => { setSeverity(v); setOffset(0); }} />
        <FilterSet label="Category" options={CATEGORIES} value={category} onChange={(v) => { setCategory(v); setOffset(0); }} />
        <FilterSet label="Status" options={STATUSES} value={status} onChange={(v) => { setStatus(v); setOffset(0); }} />
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Severity</th>
            <th>Problem</th>
            <th>Customer</th>
            <th>Late</th>
            <th>Value at Risk</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.exception_id}>
              <td>
                <span className={`badge sev-badge-${e.severity.toLowerCase()}`}>{e.severity}</span>
              </td>
              <td>
                <div className="exc-message">{e.message}</div>
                <div className="exc-meta">
                  {e.category}
                  {e.source_ref && (
                    <>
                      {" · "}
                      <button className="link-btn" onClick={() => onDrillDown(e.source_ref!.split(" ")[0])}>
                        {e.source_ref} ↗
                      </button>
                    </>
                  )}
                </div>
                {e.note && <div className="exc-note">📝 {e.note}</div>}
              </td>
              <td>{e.customer ?? "-"}</td>
              <td>{e.days_late > 0 ? `${e.days_late}d` : "-"}</td>
              <td>{e.value_at_risk > 0 ? money(e.value_at_risk) : "-"}</td>
              <td>
                <span className={`badge badge-${e.status.toLowerCase()}`}>{e.status}</span>
                {e.snooze_until && <div className="exc-meta">until {e.snooze_until}</div>}
              </td>
              <td className="action-cell">
                <button
                  disabled={busyId === e.exception_id}
                  onClick={() =>
                    act(e.exception_id, () =>
                      api.acknowledgeException(e.exception_id, promptNote("Acknowledge note (optional)")),
                    )
                  }
                >
                  Ack
                </button>
                <button
                  disabled={busyId === e.exception_id}
                  onClick={() => act(e.exception_id, () => api.snoozeException(e.exception_id, 7))}
                >
                  Snooze 7d
                </button>
                <button
                  disabled={busyId === e.exception_id}
                  onClick={() =>
                    act(e.exception_id, () =>
                      api.resolveException(e.exception_id, promptNote("Resolution note (optional)")),
                    )
                  }
                >
                  Resolve
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading && <div className="loading">Loading...</div>}
      {!loading && rows.length === 0 && (
        <div className="muted empty-state">
          No exceptions match. Run planning from the Overview tab if you haven't yet.
        </div>
      )}
      <Pagination offset={offset} limit={LIMIT} total={total} onOffsetChange={setOffset} />
    </div>
  );
}

function promptNote(label: string): string | undefined {
  const v = window.prompt(label);
  return v ?? undefined;
}

function FilterSet({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="filter-set">
      <span className="filter-label">{label}</span>
      <div className="filter-group">
        {options.map((o) => (
          <button key={o} className={o === value ? "chip chip-active" : "chip"} onClick={() => onChange(o)}>
            {o || "ALL"}
          </button>
        ))}
      </div>
    </div>
  );
}
