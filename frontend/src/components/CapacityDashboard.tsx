import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PlanningRunResult, WorkCenterLoad } from "../api";
import { num } from "../format";

interface Props {
  lastRun: PlanningRunResult | null;
}

const AREAS = ["ALL", "NEW_UNIT", "AFTERMARKET", "SHARED"];
type Mode = "required" | "scheduled";

// Status is a fourth color job (state), distinct from categorical/sequential —
// never themed, fixed meaning: healthy / tight / oversubscribed. Reads via
// CSS var so light/dark stay in sync with index.css's validated palette.
function statusColor(pct: number): string {
  if (pct > 100) return "var(--red)";
  if (pct >= 80) return "var(--amber)";
  return "var(--green)";
}
function statusLabel(pct: number): string {
  if (pct > 100) return "Over capacity";
  if (pct >= 80) return "Tight";
  return "Healthy";
}

export default function CapacityDashboard({ lastRun }: Props) {
  const [area, setArea] = useState("ALL");
  const [mode, setMode] = useState<Mode>("required");
  const [selectedWc, setSelectedWc] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!lastRun) return [];
    return lastRun.capacity_by_work_center.filter((wc) => area === "ALL" || wc.area === area);
  }, [lastRun, area]);

  const ranked = useMemo(() => {
    const pctOf = (wc: WorkCenterLoad) => (mode === "required" ? wc.annual_required_pct : wc.annual_utilization_pct);
    return [...filtered].sort((a, b) => pctOf(b) - pctOf(a));
  }, [filtered, mode]);

  const selected = useMemo(
    () => ranked.find((wc) => wc.work_center_id === selectedWc) ?? ranked[0] ?? null,
    [ranked, selectedWc],
  );

  const kpis = useMemo(() => {
    const pctOf = (wc: WorkCenterLoad) => (mode === "required" ? wc.annual_required_pct : wc.annual_utilization_pct);
    const overCount = filtered.filter((wc) => pctOf(wc) > 100).length;
    const totalExcess = filtered.reduce((sum, wc) => sum + wc.total_excess_hours, 0);
    const busiest = ranked[0];
    return { overCount, totalExcess, busiest };
  }, [filtered, ranked, mode]);

  if (!lastRun) {
    return <div className="panel">Run planning from the Overview tab first to see capacity visuals.</div>;
  }

  const pctKey = mode === "required" ? "annual_required_pct" : "annual_utilization_pct";

  return (
    <div>
      <div className="panel-header">
        <h2>Capacity</h2>
        <div className="filter-group">
          {AREAS.map((a) => (
            <button key={a} className={a === area ? "chip chip-active" : "chip"} onClick={() => setArea(a)}>
              {a}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-row">
        <div className="filter-set">
          <span className="filter-label">View</span>
          <div className="filter-group">
            <button className={mode === "required" ? "chip chip-active" : "chip"} onClick={() => setMode("required")}>
              Required (demand)
            </button>
            <button className={mode === "scheduled" ? "chip chip-active" : "chip"} onClick={() => setMode("scheduled")}>
              Scheduled (actual)
            </button>
          </div>
        </div>
        <StatusLegend />
      </div>

      <p className="muted">
        {mode === "required"
          ? "Required = hours the demand wanted, ignoring contention. Over 100% means that excess got pushed to another week — that's what makes orders late."
          : "Scheduled = what the finite scheduler actually placed. Can never exceed 100% — two orders can't share a machine hour. A cell pinned at 100% is a saturated bottleneck."}
      </p>

      <div className="card-grid">
        <StatTile label="Work centers over capacity" value={num(kpis.overCount)} highlight={kpis.overCount > 0} />
        <StatTile label="Total excess hours" value={num(Math.round(kpis.totalExcess))} highlight={kpis.totalExcess > 0} />
        <StatTile
          label="Busiest work center"
          value={kpis.busiest ? `${kpis.busiest[pctKey].toFixed(0)}%` : "-"}
          sub={kpis.busiest?.work_center_name}
        />
      </div>

      <div className="panel chart-panel">
        <h3>Utilization by work center</h3>
        <p className="muted chart-subtitle">Click a bar to see its weekly trend below.</p>
        <RankedBarChart data={ranked} pctKey={pctKey} selectedId={selected?.work_center_id ?? null} onSelect={setSelectedWc} />
      </div>

      {selected && (
        <div className="panel chart-panel">
          <h3>{selected.work_center_name}</h3>
          <p className="muted chart-subtitle">
            {selected.area} · weekly {mode === "required" ? "required" : "scheduled"} hours vs. available capacity
          </p>
          <TrendChart workCenter={selected} mode={mode} />
        </div>
      )}

      <HeatmapGrid rows={ranked} mode={mode} />
    </div>
  );
}

function HeatmapGrid({ rows, mode }: { rows: WorkCenterLoad[]; mode: Mode }) {
  const [open, setOpen] = useState(false);
  const weekLabels = rows.length ? rows[0].weeks.map((w) => w.week_start) : [];

  return (
    <div className="panel chart-panel">
      <button className="secondary grid-toggle" onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} weekly grid {open ? "▴" : "▾"}
      </button>
      {open && (
        <div className="heatmap-scroll">
          <table className="heatmap">
            <thead>
              <tr>
                <th className="heatmap-name-col">Work Center</th>
                <th className="heatmap-annual-col">Horizon</th>
                {weekLabels.map((w) => (
                  <th key={w}>{shortDate(w)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((wc) => {
                const annual = mode === "required" ? wc.annual_required_pct : wc.annual_utilization_pct;
                return (
                  <tr key={wc.work_center_id}>
                    <td className="heatmap-name-col">
                      <div className="wc-name">{wc.work_center_name}</div>
                      <div className="wc-area">
                        {wc.area}
                        {wc.overloaded_weeks > 0 && (
                          <span className="wc-excess">
                            {" "}
                            · {wc.overloaded_weeks} wk over, {Math.round(wc.total_excess_hours)}h excess
                          </span>
                        )}
                      </div>
                    </td>
                    <td className={`heatmap-cell ${cellClass(annual, mode)} heatmap-annual-col`}>
                      {fmtPct(annual)}%
                    </td>
                    {wc.weeks.map((w) => {
                      const pct = mode === "required" ? w.required_pct : w.utilization_pct;
                      return (
                        <td key={w.week_start} className={`heatmap-cell ${cellClass(pct, mode)}`}>
                          {fmtPct(pct)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function fmtPct(pct: number | null | undefined): string {
  if (pct == null || Number.isNaN(pct)) return "-";
  return pct > 999 ? "999+" : pct.toFixed(0);
}

function cellClass(pct: number | null | undefined, mode: Mode): string {
  if (pct == null || Number.isNaN(pct)) return "";
  if (pct > 100) return "cell-red";
  if (mode === "scheduled" && pct >= 99.5) return "cell-amber";
  if (pct >= 80) return "cell-amber";
  return "cell-green";
}

function RankedBarChart({
  data,
  pctKey,
  selectedId,
  onSelect,
}: {
  data: WorkCenterLoad[];
  pctKey: "annual_required_pct" | "annual_utilization_pct";
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const rows = data.map((wc) => ({
    id: wc.work_center_id,
    name: wc.work_center_name,
    area: wc.area,
    pct: wc[pctKey],
  }));
  const maxPct = Math.max(100, ...rows.map((r) => r.pct));
  const height = Math.max(220, rows.length * 28);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 48, left: 8, bottom: 4 }} barCategoryGap={4}>
        <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
        <XAxis
          type="number"
          domain={[0, Math.ceil((maxPct + 10) / 10) * 10]}
          tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={false}
          unit="%"
        />
        <YAxis
          type="category"
          dataKey="name"
          width={190}
          tick={{ fill: "var(--text-h)", fontSize: 12 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={false}
        />
        <Tooltip content={<RankedTooltip />} cursor={{ fill: "var(--accent-bg)" }} />
        <Bar
          dataKey="pct"
          radius={[0, 4, 4, 0]}
          maxBarSize={22}
          onClick={(d: any) => onSelect((d?.payload?.id ?? d?.id) as string)}
          cursor="pointer"
          isAnimationActive={false}
        >
          {rows.map((r) => (
            <Cell
              key={r.id}
              fill={statusColor(r.pct)}
              opacity={selectedId && r.id !== selectedId ? 0.55 : 1}
              stroke={r.id === selectedId ? "var(--text-h)" : "none"}
              strokeWidth={r.id === selectedId ? 1 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function RankedTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{d.name}</div>
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-key" style={{ borderColor: statusColor(d.pct) }} />
        <span className="chart-tooltip-value">{d.pct.toFixed(1)}%</span>
        <span className="chart-tooltip-label">{statusLabel(d.pct)}</span>
      </div>
      <div className="chart-tooltip-meta">{d.area}</div>
    </div>
  );
}

function TrendChart({ workCenter, mode }: { workCenter: WorkCenterLoad; mode: Mode }) {
  const rows = workCenter.weeks.map((w) => ({
    week: w.week_start,
    label: shortDate(w.week_start),
    load: mode === "required" ? w.required_hours : w.load_hours,
    available: w.available_hours,
    pct: mode === "required" ? w.required_pct : w.utilization_pct,
  }));

  return (
    <>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 4 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            width={40}
          />
          <Tooltip content={<TrendTooltip />} cursor={{ fill: "var(--accent-bg)" }} />
          <Bar dataKey="load" name={mode === "required" ? "Required hrs" : "Scheduled hrs"} maxBarSize={18} radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {rows.map((r, i) => (
              <Cell key={i} fill={statusColor(r.pct)} />
            ))}
          </Bar>
          <Line
            type="stepAfter"
            dataKey="available"
            name="Available capacity"
            stroke="var(--chart-muted)"
            strokeWidth={2}
            strokeDasharray="4 3"
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-line" style={{ background: "var(--chart-muted)", borderStyle: "dashed" }} /> Available capacity</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--green)" }} /> Healthy</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--amber)" }} /> Tight (&ge;80%)</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--red)" }} /> Over capacity (&gt;100%)</span>
      </div>
    </>
  );
}

function TrendTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">Week of {d.week}</div>
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-key" style={{ borderColor: statusColor(d.pct) }} />
        <span className="chart-tooltip-value">{num(Math.round(d.load))}h</span>
        <span className="chart-tooltip-label">load ({d.pct.toFixed(0)}%)</span>
      </div>
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-key" style={{ borderColor: "var(--chart-muted)", borderStyle: "dashed" }} />
        <span className="chart-tooltip-value">{num(Math.round(d.available))}h</span>
        <span className="chart-tooltip-label">available</span>
      </div>
    </div>
  );
}

function StatusLegend() {
  return (
    <div className="status-legend">
      <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--green)" }} /> &lt;80%</span>
      <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--amber)" }} /> 80-100%</span>
      <span className="legend-item"><span className="legend-swatch" style={{ background: "var(--red)" }} /> &gt;100%</span>
    </div>
  );
}

function StatTile({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`stat-card ${highlight ? "stat-card-highlight" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
