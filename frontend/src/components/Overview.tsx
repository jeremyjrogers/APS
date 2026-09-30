import { useEffect, useState } from "react";
import { api, type PlanningRunResult, type Summary } from "../api";
import { money, num } from "../format";

interface Props {
  onRunComplete: (result: PlanningRunResult) => void;
  lastRun: PlanningRunResult | null;
}

export default function Overview({ onRunComplete, lastRun }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.summary().then(setSummary).catch((e) => setError(String(e)));
  }, [lastRun]);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.runPlanning();
      onRunComplete(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  if (error) return <div className="error">Failed to load: {error}. Is the backend running on :8000?</div>;
  if (!summary) return <div className="loading">Loading...</div>;

  return (
    <div>
      <div className="card-grid">
        <Card label="Items (shared master)" value={num(summary.items)} />
        <Card label="Work Centers" value={num(summary.work_centers)} />
        <Card label="Suppliers" value={num(summary.suppliers)} />
        <Card
          label="Firm Projects"
          value={num(summary.projects.firm)}
          sub={money(summary.projects.firm_contract_value)}
        />
        <Card
          label="Quoted Pipeline"
          value={num(summary.projects.quoted)}
          sub={money(summary.projects.quoted_pipeline_value)}
        />
        <Card
          label="Sales Orders"
          value={num(summary.sales_orders.count)}
          sub={money(summary.sales_orders.revenue)}
        />
        <Card
          label="Overhaul Jobs"
          value={num(summary.overhaul_jobs.count)}
          sub={money(summary.overhaul_jobs.value)}
        />
        <Card label="Work Orders (planned)" value={num(summary.work_orders)} />
        <Card label="Purchase Orders (planned)" value={num(summary.purchase_orders)} />
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Planning Engine</h2>
          <button onClick={handleRun} disabled={running}>
            {running ? "Running..." : "Run Planning"}
          </button>
        </div>
        <p className="muted">
          Gathers demand from firm projects, aftermarket sales orders, and approved overhaul
          findings; explodes BOMs; nets against inventory; backward-schedules against work center
          calendars; persists planned work orders and purchase orders.
        </p>

        {running && (
          <p className="muted running-note">
            This can take up to a minute the first time — if the backend has been idle it's waking
            back up from sleep on top of actually running the plan. It isn't stuck.
          </p>
        )}

        {lastRun && (
          <div className="run-result">
            <div className="card-grid">
              <Card label="Demand records" value={num(lastRun.demand_count)} />
              <Card label="Planned Work Orders" value={num(lastRun.planned_work_orders)} />
              <Card label="Planned Purchase Orders" value={num(lastRun.planned_purchase_orders)} />
              <Card
                label="Open Exceptions"
                value={num(lastRun.exceptions.open)}
                sub={`${lastRun.exceptions.created} new · ${lastRun.exceptions.auto_resolved} auto-resolved`}
                highlight={lastRun.exceptions.open > 0}
              />
              <Card
                label="Overloaded Weeks"
                value={num(lastRun.overloaded_week_count)}
                sub={`of ${lastRun.capacity_weeks_evaluated} evaluated`}
                highlight={lastRun.overloaded_week_count > 0}
              />
            </div>
            <p className="muted">
              Triage state is preserved across runs — acknowledged and snoozed exceptions stay that
              way, and problems the plan no longer produces are auto-resolved. Head to the{" "}
              <strong>Exceptions</strong> tab to work the queue.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Card({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`stat-card ${highlight ? "stat-card-highlight" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
