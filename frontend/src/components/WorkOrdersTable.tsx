import { useEffect, useState } from "react";
import { api, type WorkOrder } from "../api";
import Pagination from "./Pagination";

const LIMIT = 50;

function lateDays(dueDate: string, projectedEnd?: string | null): number {
  if (!projectedEnd) return 0;
  const ms = new Date(projectedEnd).getTime() - new Date(dueDate).getTime();
  return Math.max(0, Math.round(ms / 86_400_000));
}

export default function WorkOrdersTable() {
  const [rows, setRows] = useState<WorkOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .workOrders({ source: source || undefined, limit: LIMIT, offset })
      .then((res) => {
        setRows(res.rows);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [source, offset]);

  return (
    <div>
      <div className="panel-header">
        <h2>Work Orders (planned)</h2>
        <div className="filter-group">
          {["", "PROJECT", "AFTERMARKET", "OVERHAUL"].map((s) => (
            <button
              key={s}
              className={s === source ? "chip chip-active" : "chip"}
              onClick={() => {
                setSource(s);
                setOffset(0);
              }}
            >
              {s || "ALL"}
            </button>
          ))}
        </div>
      </div>
      <p className="muted">
        Scheduled against finite capacity. Same-item demand of the same urgency within a week is
        batched into one work order (one setup, not one per order) — source_ref shows "+N more"
        when batched. <strong>Projected</strong> is the finite-capacity completion date; when it
        falls after Due, the order genuinely cannot be delivered on time as planned.
      </p>
      <table className="data-table">
        <thead>
          <tr>
            <th>WO</th>
            <th>Item</th>
            <th>Qty</th>
            <th>Source</th>
            <th>Source Ref</th>
            <th>Start</th>
            <th>Due</th>
            <th>Projected</th>
            <th>Late</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const late = lateDays(r.due_date, r.projected_end);
            return (
              <tr key={r.wo_id}>
                <td>{r.wo_id}</td>
                <td>{r.item_id}</td>
                <td>{r.qty}</td>
                <td>
                  <span className={`badge badge-${r.source.toLowerCase()}`}>{r.source}</span>
                </td>
                <td className="truncate">{r.source_ref}</td>
                <td>{r.start_date}</td>
                <td>{r.due_date}</td>
                <td>{r.projected_end ?? "-"}</td>
                <td>
                  {late > 0 ? (
                    <span className="peg-late">
                      {late}d
                      {r.capacity_delay_days ? (
                        <span className="exc-meta"> ({r.capacity_delay_days}d capacity)</span>
                      ) : null}
                    </span>
                  ) : (
                    <span className="on-time">on time</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {loading && <div className="loading">Loading...</div>}
      {!loading && rows.length === 0 && <div className="muted">No work orders yet — run planning from the Overview tab.</div>}
      <Pagination offset={offset} limit={LIMIT} total={total} onOffsetChange={setOffset} />
    </div>
  );
}
