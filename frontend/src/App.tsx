import { useState } from "react";
import "./App.css";
import Overview from "./components/Overview";
import ExceptionsWorkbench from "./components/ExceptionsWorkbench";
import PeggingView from "./components/PeggingView";
import CapacityDashboard from "./components/CapacityDashboard";
import ProjectsTable from "./components/ProjectsTable";
import SalesOrdersTable from "./components/SalesOrdersTable";
import OverhaulJobsTable from "./components/OverhaulJobsTable";
import WorkOrdersTable from "./components/WorkOrdersTable";
import PurchaseOrdersTable from "./components/PurchaseOrdersTable";
import ActionLog from "./components/ActionLog";
import MasterData from "./components/MasterData";
import ImportData from "./components/ImportData";
import ErrorBoundary from "./components/ErrorBoundary";
import type { PlanningRunResult } from "./api";

const TABS = [
  "Overview",
  "Exceptions",
  "Root Cause",
  "Capacity",
  "Projects",
  "Sales Orders",
  "Overhaul Jobs",
  "Work Orders",
  "Purchase Orders",
  "Master Data",
  "Import",
  "Action Log",
] as const;
type Tab = (typeof TABS)[number];

function App() {
  const [tab, setTab] = useState<Tab>("Overview");
  const [lastRun, setLastRun] = useState<PlanningRunResult | null>(null);
  const [pegRef, setPegRef] = useState<string | null>(null);

  function drillDown(sourceRef: string) {
    setPegRef(sourceRef);
    setTab("Root Cause");
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>APS Planning POC</h1>
        <span className="muted">Single-plant pump/compressor manufacturer — new-unit + aftermarket</span>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "tab tab-active" : "tab"} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>

      <main className="app-main">
        <ErrorBoundary key={tab} label={tab}>
          {tab === "Overview" && <Overview lastRun={lastRun} onRunComplete={setLastRun} />}
          {tab === "Exceptions" && <ExceptionsWorkbench onDrillDown={drillDown} />}
          {tab === "Root Cause" && <PeggingView sourceRef={pegRef} onSourceRefChange={setPegRef} />}
          {tab === "Capacity" && <CapacityDashboard lastRun={lastRun} />}
          {tab === "Projects" && <ProjectsTable />}
          {tab === "Sales Orders" && <SalesOrdersTable />}
          {tab === "Overhaul Jobs" && <OverhaulJobsTable />}
          {tab === "Work Orders" && <WorkOrdersTable />}
          {tab === "Purchase Orders" && <PurchaseOrdersTable />}
          {tab === "Master Data" && <MasterData />}
          {tab === "Import" && <ImportData />}
          {tab === "Action Log" && <ActionLog />}
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default App;
