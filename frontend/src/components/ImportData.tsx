import { useState } from "react";
import { api, type ImportResult } from "../api";

const KINDS = [
  { key: "items", label: "Items", fn: api.importItems, endpoint: "/import/items" },
  { key: "inventory", label: "Inventory", fn: api.importInventory, endpoint: "/import/inventory" },
  { key: "sales-orders", label: "Sales Orders", fn: api.importSalesOrders, endpoint: "/import/sales-orders" },
] as const;

export default function ImportData() {
  const [kind, setKind] = useState<(typeof KINDS)[number]["key"]>("items");
  const [template, setTemplate] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const active = KINDS.find((k) => k.key === kind)!;

  function loadTemplate(k: string) {
    setKind(k as (typeof KINDS)[number]["key"]);
    setResult(null);
    setError(null);
    api.importTemplate(k).then(setTemplate);
  }

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await active.fn(file);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel-header">
        <h2>Import Data</h2>
        <div className="filter-group">
          {KINDS.map((k) => (
            <button key={k.key} className={k.key === kind ? "chip chip-active" : "chip"} onClick={() => loadTemplate(k.key)}>
              {k.label}
            </button>
          ))}
        </div>
      </div>
      <p className="muted">
        CSV upload with a header row. Bad rows are reported individually — the rest of the file still
        imports.
      </p>

      <div className="panel">
        <h3>{active.label} columns</h3>
        {template ? (
          <div className="template-cols">
            <div>
              <strong>Required:</strong> {(template.required as string[])?.join(", ")}
            </div>
            {!!template.optional && (
              <div>
                <strong>Optional:</strong> {(template.optional as string[]).join(", ")}
              </div>
            )}
            {!!template.item_type_values && (
              <div className="muted">item_type: {(template.item_type_values as string[]).join(" | ")}</div>
            )}
            {!!template.make_or_buy_values && (
              <div className="muted">make_or_buy: {(template.make_or_buy_values as string[]).join(" | ")}</div>
            )}
          </div>
        ) : (
          <button onClick={() => loadTemplate(kind)}>Show column reference</button>
        )}

        <div className="upload-row">
          <input
            type="file"
            accept=".csv"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
              e.target.value = "";
            }}
          />
          {busy && <span className="muted">Importing...</span>}
        </div>

        {error && <div className="error inline-error">{error}</div>}

        {result && (
          <div className="import-result">
            <div className="card-grid">
              <div className="stat-card">
                <div className="stat-label">Rows Processed</div>
                <div className="stat-value">{result.total_rows}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Created</div>
                <div className="stat-value">{result.created}</div>
              </div>
              {result.updated !== undefined && (
                <div className="stat-card">
                  <div className="stat-label">Updated</div>
                  <div className="stat-value">{result.updated}</div>
                </div>
              )}
              <div className={`stat-card ${result.error_count > 0 ? "stat-card-highlight" : ""}`}>
                <div className="stat-label">Errors</div>
                <div className="stat-value">{result.error_count}</div>
              </div>
            </div>
            {result.errors.length > 0 && (
              <table className="data-table">
                <thead><tr><th>Row</th><th>Problem</th></tr></thead>
                <tbody>
                  {result.errors.map((e, i) => (
                    <tr key={i}><td>{e.row}</td><td>{e.message}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
