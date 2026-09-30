import { useEffect, useState } from "react";
import { api, type PlanActionRow } from "../api";
import Pagination from "./Pagination";

const LIMIT = 50;

export default function ActionLog() {
  const [rows, setRows] = useState<PlanActionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .actions({ limit: LIMIT, offset })
      .then((res) => {
        setRows(res.rows);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [offset]);

  return (
    <div>
      <div className="panel-header">
        <h2>Action Log</h2>
      </div>
      <p className="muted">
        Every planner decision, with before/after values — the audit trail behind the current plan.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Action</th>
            <th>Target</th>
            <th>Before</th>
            <th>After</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.action_id}>
              <td>{a.created_at ? new Date(a.created_at).toLocaleString() : "-"}</td>
              <td>
                <span className="badge">{a.action_type}</span>
              </td>
              <td>
                <div>{a.target_id}</div>
                <div className="exc-meta">{a.target_type}</div>
              </td>
              <td className="mono-cell">{a.before_value ?? "-"}</td>
              <td className="mono-cell">{a.after_value ?? "-"}</td>
              <td>{a.note ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading && <div className="loading">Loading...</div>}
      {!loading && rows.length === 0 && (
        <div className="muted empty-state">No actions taken yet.</div>
      )}
      <Pagination offset={offset} limit={LIMIT} total={total} onOffsetChange={setOffset} />
    </div>
  );
}
