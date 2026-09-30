import { useCallback, useEffect, useState } from "react";
import { api, type PegNode, type PegTree } from "../api";
import { money } from "../format";

interface Props {
  sourceRef: string | null;
  onSourceRefChange: (ref: string) => void;
}

export default function PeggingView({ sourceRef, onSourceRefChange }: Props) {
  const [input, setInput] = useState(sourceRef ?? "");
  const [tree, setTree] = useState<PegTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback((ref: string) => {
    if (!ref) return;
    setLoading(true);
    setError(null);
    api
      .pegDemand(ref)
      .then(setTree)
      .catch((e) => {
        setTree(null);
        setError(String(e));
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (sourceRef) {
      setInput(sourceRef);
      load(sourceRef);
    }
  }, [sourceRef, load]);

  async function act(orderId: string, fn: () => Promise<unknown>) {
    setBusy(orderId);
    try {
      await fn();
      if (tree) load(tree.source_ref);
    } catch (e) {
      alert(String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="panel-header">
        <h2>Pegging / Root Cause</h2>
        <form
          className="peg-search"
          onSubmit={(e) => {
            e.preventDefault();
            onSourceRefChange(input.trim());
            load(input.trim());
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="PRJ-000022 / SO-000123 / OHJ-000005"
          />
          <button type="submit">Trace</button>
        </form>
      </div>
      <p className="muted">
        Walks the full supply tree the planner generated for one demand, so you can see which
        component is actually driving a late delivery rather than only that the top-level order is
        late.
      </p>

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error">{error}</div>}

      {tree && (
        <>
          {tree.demand && (
            <div className="card-grid">
              <Stat label="Demand" value={tree.demand.ref} sub={tree.demand.type} />
              <Stat label="Customer" value={tree.demand.customer} />
              <Stat label="Value" value={money(tree.demand.value)} />
              <Stat label="Due" value={tree.demand.due_date ?? "-"} />
              <Stat label="Orders in tree" value={String(tree.total_orders)} />
              <Stat
                label="Worst delay"
                value={tree.max_expedite_days > 0 ? `${tree.max_expedite_days}d` : "on time"}
                highlight={tree.max_expedite_days > 0}
              />
            </div>
          )}

          {tree.root_cause && (
            <div className="root-cause">
              <strong>Root cause:</strong> {tree.root_cause.order_id} — {tree.root_cause.item_id}{" "}
              ({tree.root_cause.description}) at BOM level {tree.root_cause.bom_level},{" "}
              <strong>{tree.root_cause.expedite_days}d late</strong>
              {tree.root_cause.supplier_id && <> · supplier {tree.root_cause.supplier_id}</>}
            </div>
          )}

          <div className="peg-tree">
            {tree.tree.map((n) => (
              <TreeNode key={n.order_id} node={n} depth={0} busy={busy} onAct={act} />
            ))}
          </div>
        </>
      )}

      {!tree && !loading && !error && (
        <div className="muted empty-state">
          Enter a project, sales order, or overhaul job reference above — or click a reference from
          the Exceptions tab.
        </div>
      )}
    </div>
  );
}

function TreeNode({
  node,
  depth,
  busy,
  onAct,
}: {
  node: PegNode;
  depth: number;
  busy: string | null;
  onAct: (orderId: string, fn: () => Promise<unknown>) => void;
}) {
  const isWO = node.node_type === "WORK_ORDER";
  const late = node.expedite_days > 0;

  return (
    <>
      <div className={`peg-node ${late ? "peg-node-late" : ""}`} style={{ marginLeft: depth * 24 }}>
        <span className={`peg-kind ${isWO ? "peg-wo" : "peg-po"}`}>{isWO ? "WO" : "PO"}</span>
        <span className="peg-id">{node.order_id}</span>
        <span className="peg-item">
          {node.item_id}
          {node.description && <span className="peg-desc"> — {node.description}</span>}
        </span>
        <span className="peg-qty">×{node.qty.toFixed(2)}</span>
        <span className="peg-date">due {node.due_date ?? "-"}</span>
        {late && <span className="peg-late">{node.expedite_days}d late</span>}
        <span className={`badge badge-${node.status.toLowerCase()}`}>{node.status}</span>
        {node.supplier_id && <span className="peg-supplier">{node.supplier_id}</span>}

        <span className="peg-actions">
          {isWO ? (
            <>
              <button
                disabled={busy === node.order_id}
                onClick={() => {
                  const d = window.prompt("Pull in by how many days?", "14");
                  if (d) onAct(node.order_id, () => api.expediteWorkOrder(node.order_id, Number(d)));
                }}
              >
                Expedite
              </button>
              <button
                disabled={busy === node.order_id || node.status !== "PLANNED"}
                onClick={() => onAct(node.order_id, () => api.releaseWorkOrder(node.order_id))}
              >
                Release
              </button>
            </>
          ) : (
            <>
              <button
                disabled={busy === node.order_id}
                onClick={() => {
                  const d = window.prompt("New due date (YYYY-MM-DD)", node.due_date ?? "");
                  if (d) onAct(node.order_id, () => api.reschedulePurchaseOrder(node.order_id, d));
                }}
              >
                Reschedule
              </button>
              <button
                disabled={busy === node.order_id || node.status !== "PLANNED"}
                onClick={() => onAct(node.order_id, () => api.releasePurchaseOrder(node.order_id))}
              >
                Release
              </button>
            </>
          )}
        </span>
      </div>
      {node.children.map((c) => (
        <TreeNode key={c.order_id} node={c} depth={depth + 1} busy={busy} onAct={onAct} />
      ))}
    </>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`stat-card ${highlight ? "stat-card-highlight" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value stat-value-sm">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
