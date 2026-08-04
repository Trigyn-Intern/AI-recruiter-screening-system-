import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  LogOut,
  PlayCircle,
  Copy,
  ExternalLink,
  Loader2,
  FlaskConical,
  Trash2,
  Plus,
  RefreshCw,
  Download,
  FileText,
  CheckCircle2,
  XCircle,
  Search,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ClipboardList,
} from "lucide-react";
import {
  authApi,
  clearSession,
  executeCommand,
  getReportMetadata,
  getStoredToken,
  getStoredUser,
  storeSession,
} from "../api";
import { TEST_CATALOG } from "../testCatalog";
import { SAMPLE_FIXTURES, REPORT_CATALOG } from "../reportCatalog";
import { COLUMNS as XLSX_COLUMNS, exportRunsToXlsx, toRows as runsToXlsxRows } from "../xlsxExport";

const RUNS_KEY = "testing.runs";
const FIXTURES_KEY = "testing.fixtures";
const SELECTED_FIXTURES_KEY = "testing.selected.fixtures";
const REPORTS_STATE_KEY = "testing.reports.state";
const SELECTED_ROWS_KEY = "testing.selected.rows";

function loadRuns() {
  try {
    const raw = localStorage.getItem(RUNS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}
function saveRuns(runs) { localStorage.setItem(RUNS_KEY, JSON.stringify(runs.slice(0, 50))); }

function loadFixtures() {
  try {
    const raw = localStorage.getItem(FIXTURES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) && parsed.length ? parsed : SAMPLE_FIXTURES;
  } catch { return SAMPLE_FIXTURES; }
}
function saveFixtures(list) { localStorage.setItem(FIXTURES_KEY, JSON.stringify(list)); }

function loadSelectedFixtureIds() {
  try {
    const raw = localStorage.getItem(SELECTED_FIXTURES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}
function saveSelectedFixtureIds(ids) { localStorage.setItem(SELECTED_FIXTURES_KEY, JSON.stringify(ids)); }

function loadReportsState() {
  try {
    const raw = localStorage.getItem(REPORTS_STATE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}
function saveReportsState(map) { localStorage.setItem(REPORTS_STATE_KEY, JSON.stringify(map)); }

function loadSelectedRowIds() {
  try {
    const raw = localStorage.getItem(SELECTED_ROWS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}
function saveSelectedRowIds(ids) { localStorage.setItem(SELECTED_ROWS_KEY, JSON.stringify(ids)); }

function fmtBytes(n) {
  if (!Number.isFinite(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function gradePill(grade) {
  const g = String(grade || "?").toUpperCase();
  return <span className={`testing-pill grade-${g}`}>{g}</span>;
}
function kindPill(kind) {
  if (!kind) return null;
  return <span className={`testing-pill kind-${kind}`}>{kind}</span>;
}

function summarize(detail) {
  if (!detail) return null;
  const resumeName = detail.resume_name || detail.candidate_name || "Resume";
  const score = detail.match_score ?? detail.score ?? null;
  const grade = (detail.grading && detail.grading.grade) || detail.grade || null;
  const summary = (detail.grading && detail.grading.summary) || detail.summary || "";
  return { resumeName, score, grade, summary };
}

function toBrowserPath(targetPath) {
  if (!targetPath) return null;
  const normalized = String(targetPath).replace(/\\/g, "/");
  return /^[a-zA-Z]:\//.test(normalized) ? `file:///${normalized}` : `/${normalized}`;
}

function recentRunCell(row, key) {
  const value = row[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function reportPathForRow(row) {
  if (!row) return "";
  if (row.file) {
    const normalized = String(row.file).replace(/\\/g, "/");
    const marker = "/AI-recruiter-screening-system-/";
    const idx = normalized.indexOf(marker);
    return idx >= 0 ? normalized.slice(idx + marker.length) : normalized;
  }
  if (String(row.command || "").includes("tests/run.ps1")) return "reports/report.html";
  if (String(row.command || "").includes("junit-xml=reports/junit.json")) return "reports/junit.json";
  return "";
}

function MetricCard({ label, value, sub, pct }) {
  return (
    <div className="metric-card">
      <span className="m-label">{label}</span>
      <span className="m-value">{value}</span>
      {sub ? <span className="m-sub">{sub}</span> : null}
      {typeof pct === "number" ? (
        <div className="bar"><span style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>
      ) : null}
    </div>
  );
}

function ReportCard({ report, meta, onOpen, onDownload, onRefresh, onRun, runDetail, collapsed, onToggleCollapsed }) {
  const exists = !!meta && meta.exists;
  const isRunning = runDetail && runDetail.status === "Running";
  const statusCls = runDetail
    ? runDetail.status === "Done" ? "ok" : runDetail.status === "Failed" ? "err" : "run"
    : "";
  return (
    <div className={`testing-report-card ${collapsed ? "collapsed" : ""}`}>
      <button type="button" className="rc-toggle" onClick={() => onToggleCollapsed(report.id)}>
        {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        <div className="rc-title">
          <FileText size={16} />
          {report.title}
          {runDetail && (
            <span className={`testing-status ${statusCls}`} style={{ marginLeft: 6, fontSize: 10.5 }}>
              {runDetail.status}
            </span>
          )}
        </div>
      </button>
      {!collapsed ? (
        <>
          {report.description ? (
            <div className="rc-desc">{report.description}</div>
          ) : null}
          {exists ? (
            <div className="rc-meta">
              {meta.size ? <div>Size: {fmtBytes(meta.size)}</div> : null}
              {meta.mtime ? <div>Modified: {new Date(meta.mtime).toLocaleString()}</div> : null}
              {meta.path ? <div className="testing-mono" style={{ wordBreak: "break-all" }}>{meta.path}</div> : null}
            </div>
          ) : (
            <div className="rc-empty">No report yet — click Run to generate it.</div>
          )}
          <div className="rc-actions">
            {report.command ? (
              <button className="primary tiny" type="button" onClick={() => onRun(report)} disabled={isRunning}>
                {isRunning ? <Loader2 size={11} className="spin" /> : <PlayCircle size={11} />}
                {isRunning ? "Running…" : "Run"}
              </button>
            ) : null}
            <button className="secondary tiny" type="button" onClick={() => onOpen(report)} disabled={!exists}>
              <ExternalLink size={12} /> Open
            </button>
            <button className="secondary tiny" type="button" onClick={() => onDownload(report)} disabled={!exists}>
              <Download size={12} /> Download
            </button>
            <button className="ghost tiny" type="button" onClick={() => onRefresh(report)} title="Refresh metadata">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {runDetail && runDetail.logs ? (
            <div className="testing-console-output">
              <div className="console-header">
                <span>Elapsed: {(runDetail.elapsedMs / 1000).toFixed(1)}s</span>
                {runDetail.exitCode !== null && runDetail.exitCode !== undefined && (
                  <span>Exit: {runDetail.exitCode}</span>
                )}
              </div>
              <pre className="console-logs">{runDetail.logs}</pre>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default function TestingDashboard() {
  const [user, setUser] = useState(getStoredUser());
  const [authStatus, setAuthStatus] = useState({ state: "checking", message: "" });
  const [analysisStatus, setAnalysisStatus] = useState({ state: "unknown", message: "" });

  const [activeTab, setActiveTab] = useState("unit");
  const [query, setQuery] = useState("");
  const [filterKind, setFilterKind] = useState("all");
  const [selectedRowIds, setSelectedRowIds] = useState(loadSelectedRowIds);

  const [fixtures, setFixtures] = useState(loadFixtures);
  const [activeId, setActiveId] = useState(loadFixtures()[0]?.id || "");
  const [selectedIds, setSelectedIds] = useState(() => {
    const stored = loadSelectedFixtureIds();
    const all = loadFixtures();
    const valid = stored.filter((id) => all.some((f) => f.id === id));
    return valid.length ? valid : all.map((f) => f.id);
  });
  const [jobText, setJobText] = useState(loadFixtures()[0]?.job || "");
  const [resumeText, setResumeText] = useState(loadFixtures()[0]?.resume || "");
  const [isRunning, setIsRunning] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState("");
  const [runs, setRuns] = useState(loadRuns);

  const [reportsState, setReportsState] = useState(loadReportsState);
  const [refreshingReports, setRefreshingReports] = useState(false);
  const [reportQuery, setReportQuery] = useState("");
  const [reportKind, setReportKind] = useState("all");
  const [collapsedReports, setCollapsedReports] = useState({});
  const [toast, setToast] = useState(null);
  const [runningRows, setRunningRows] = useState([]);
  const [executionDetails, setExecutionDetails] = useState({});
  const [reportRunDetails, setReportRunDetails] = useState({});

  const active = useMemo(() => fixtures.find((f) => f.id === activeId) || null, [fixtures, activeId]);
  const selectedFixtures = useMemo(() => fixtures.filter((f) => selectedIds.includes(f.id)), [fixtures, selectedIds]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      storeSession(token, null);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      const token = getStoredToken();
      if (!token) {
        if (!cancelled) setAuthStatus({ state: "error", message: "No session. Please log in from the recruiter app." });
        return;
      }
      try {
        const data = await authApi("/api/auth/me");
        if (cancelled) return;
        const u = (data && data.user) || null;
        if (!u) throw new Error("Auth response missing user.");
        if (u.role !== "manager") {
          setAuthStatus({ state: "error", message: `Account '${u.email}' is not a manager.` });
          return;
        }
        setUser(u);
        storeSession(token, u);
        setAuthStatus({ state: "ok", message: `Signed in as ${u.email}` });
      } catch (err) {
        if (!cancelled) setAuthStatus({ state: "error", message: err.message || "Session invalid." });
      }
    }
    check();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch((import.meta.env.VITE_FASTAPI_URL || "") + "/health")
      .then((r) => { if (!cancelled) setAnalysisStatus({ state: r.ok ? "ok" : "warn", message: `HTTP ${r.status}` }); })
      .catch((err) => { if (!cancelled) setAnalysisStatus({ state: "err", message: err.message }); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    void refreshAllReports();
  }, []);

  useEffect(() => { if (!active) return; setJobText(active.job); setResumeText(active.resume); }, [activeId, active]);

  function pickFixture(id) { setActiveId(id); setLastResult(null); setError(""); }
  function toggleSelected(id) {
    setSelectedIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      saveSelectedFixtureIds(next);
      return next;
    });
  }
  function selectAll() { const all = fixtures.map((f) => f.id); setSelectedIds(all); saveSelectedFixtureIds(all); }
  function selectNone() { setSelectedIds([]); saveSelectedFixtureIds([]); }
  function addFixture() {
    const id = `fx-${Date.now().toString(36)}`;
    const next = { id, label: "New fixture", job: "", resume: "" };
    const updated = [...fixtures, next];
    setFixtures(updated); saveFixtures(updated);
    setSelectedIds((prev) => { const out = [...prev, id]; saveSelectedFixtureIds(out); return out; });
    setActiveId(id);
  }
  function deleteFixture(id) {
    const updated = fixtures.filter((f) => f.id !== id);
    const list = updated.length ? updated : SAMPLE_FIXTURES;
    setFixtures(list); saveFixtures(list);
    setSelectedIds((prev) => { const out = prev.filter((x) => x !== id); saveSelectedFixtureIds(out); return out; });
    if (activeId === id) setActiveId(list[0].id);
  }
  function updateActiveField(field, value) {
    const updated = fixtures.map((f) => f.id === activeId ? { ...f, [field]: value, label: f.label } : f);
    setFixtures(updated); saveFixtures(updated);
    if (field === "job") setJobText(value);
    if (field === "resume") setResumeText(value);
  }
  function renameActive(label) {
    const updated = fixtures.map((f) => f.id === activeId ? { ...f, label } : f);
    setFixtures(updated); saveFixtures(updated);
  }

  async function runAnalysisFor(fixture) {
    const started = Date.now();
    function storeRun(run) {
      setRuns((prev) => {
        const next = [run, ...prev].slice(0, 50);
        saveRuns(next);
        return next;
      });
    }
    try {
      const r = await fetch((import.meta.env.VITE_FASTAPI_URL || "") + "/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_text: fixture.job, resumes: [{ name: fixture.label, text: fixture.resume }] }),
      });
      const payload = await r.json();
      const detail = (payload && payload.details && payload.details[0])
        || (payload && payload.top_details && payload.top_details[0])
        || (payload && payload.detail)
        || payload;
      const summary = summarize(detail);
      const run = {
        id: `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        fixtureId: fixture.id,
        fixtureLabel: fixture.label,
        at: new Date().toISOString(),
        elapsedMs: Date.now() - started,
        score: summary ? summary.score : null,
        grade: summary ? summary.grade : null,
        summary: summary ? summary.summary : "",
        ok: r.ok,
        raw: detail,
      };
      storeRun(run);
      // Auto-refresh reports
      await refreshAllReports();
      return run;
    } catch (err) {
      const run = {
        id: `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        fixtureId: fixture.id,
        fixtureLabel: fixture.label,
        at: new Date().toISOString(),
        elapsedMs: Date.now() - started,
        score: null, grade: null, summary: "", ok: false,
        error: err.message || String(err),
      };
      storeRun(run);
      return run;
    }
  }
  async function runAnalysis() {
    if (!active) return;
    setError(""); setLastResult(null); setIsRunning(true);
    try { const run = await runAnalysisFor(active); setLastResult(run); if (!run.ok) setError(run.error || "Analysis request failed."); }
    finally { setIsRunning(false); }
  }
  async function runSelectedFixtures() {
    if (selectedFixtures.length === 0) return;
    setError(""); setIsRunning(true);
    const results = [];
    for (const fx of selectedFixtures) { results.push(await runAnalysisFor(fx)); }
    setLastResult(results[results.length - 1] || null);
    if (results.some((r) => !r.ok)) setError(`${results.filter((r) => !r.ok).length} of ${results.length} run(s) failed.`);
    setIsRunning(false);
  }

  async function refreshReport(report) {
    try {
      const [meta] = await getReportMetadata([{ ...report, path: report.path || "" }]);
      setReportsState((prev) => {
        const next = { ...prev, [report.id]: { ...(prev[report.id] || {}), ...meta, checkedAt: new Date().toISOString() } };
        saveReportsState(next);
        return next;
      });
      setToast({ kind: "success", message: `${report.title} refreshed.` });
    } catch (error) {
      setToast({ kind: "error", message: error.message || `Unable to refresh ${report.title}.` });
    }
  }
  async function refreshAllReports() {
    setRefreshingReports(true);
    try {
      const rows = await getReportMetadata(REPORT_CATALOG.map((report) => ({ ...report, path: report.path || "" })));
      const next = { ...reportsState };
      rows.forEach((meta) => {
        next[meta.id] = { ...(next[meta.id] || {}), ...meta, checkedAt: new Date().toISOString() };
      });
      setReportsState(next); saveReportsState(next);
      setToast({ kind: "success", message: `Refreshed ${rows.length} report cards.` });
    } catch (error) {
      setToast({ kind: "error", message: error.message || "Unable to refresh reports." });
    } finally {
      setRefreshingReports(false);
    }
  }
  function openReport(report) {
    // If the catalog entry has a staticUrl, open it directly so relative assets (CSS/JS/PNG) load correctly.
    if (report.staticUrl) {
      window.open(report.staticUrl, "_blank", "noopener,noreferrer");
      return;
    }
    const meta = reportsState[report.id];
    if (meta && meta.exists && meta.path) {
      window.open(`/api/reports/view?path=${encodeURIComponent(meta.path)}`, "_blank", "noopener,noreferrer");
    }
  }
  function downloadReport(report) {
    const meta = reportsState[report.id];
    if (!meta || !meta.exists || !meta.path) return;
    const link = document.createElement("a");
    link.href = `/api/reports/view?path=${encodeURIComponent(meta.path)}&download=true`;
    link.download = report.filename || report.id;
    link.rel = "noopener";
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
  }

  async function handleRunReport(report) {
    if (!report.command) return;
    setReportRunDetails((prev) => ({
      ...prev,
      [report.id]: { status: "Running", logs: `$ ${report.command}\n`, exitCode: null, elapsedMs: 0 },
    }));
    setToast({ kind: "info", message: `Running ${report.title}…` });
    const started = Date.now();
    try {
      const response = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cwd: report.cwd, command: report.command }),
      });
      if (!response.ok) throw new Error(`Server error ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let logs = `$ ${report.command}\n`;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "stdout" || data.type === "stderr") {
              logs += data.text;
              setReportRunDetails((prev) => ({
                ...prev,
                [report.id]: { ...prev[report.id], logs, elapsedMs: Date.now() - started },
              }));
            } else if (data.type === "close") {
              const ok = data.code === 0;
              setReportRunDetails((prev) => ({
                ...prev,
                [report.id]: { ...prev[report.id], status: ok ? "Done" : "Failed", exitCode: data.code, elapsedMs: Date.now() - started },
              }));
              setToast({ kind: ok ? "success" : "error", message: ok ? `${report.title} done.` : `${report.title} failed (exit ${data.code}).` });
            } else if (data.type === "error") {
              logs += `\nError: ${data.message}\n`;
              setReportRunDetails((prev) => ({
                ...prev,
                [report.id]: { ...prev[report.id], status: "Failed", logs, elapsedMs: Date.now() - started },
              }));
            }
          } catch (_) {}
        }
      }
      await refreshAllReports();
    } catch (err) {
      setReportRunDetails((prev) => ({
        ...prev,
        [report.id]: {
          ...prev[report.id],
          status: "Failed",
          logs: (prev[report.id]?.logs || "") + `\nError: ${err.message}\n`,
          elapsedMs: Date.now() - started,
        },
      }));
      setToast({ kind: "error", message: err.message || `Unable to run ${report.title}.` });
    }
  }

  async function handleRunRow(row) {
    if (!row || !row.command) return;
    let finalRun = null;
    setExecutionDetails((prev) => ({
      ...prev,
      [row.id]: {
        status: "Running",
        logs: "Starting test script environment...\n",
        elapsedMs: 0,
        exitCode: null,
        outputDir: row.file || row.cwd || "Project Root",
      }
    }));
    setRunningRows((prev) => (prev.includes(row.id) ? prev : [...prev, row.id]));
    setToast({ kind: "info", message: `Running ${row.label}…` });
    
    const started = Date.now();
    try {
      const response = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cwd: row.cwd, command: row.command }),
      });
      if (!response.ok) {
        throw new Error(`Failed to start command (${response.status})`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let logs = "";
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "stdout" || data.type === "stderr") {
                logs += data.text;
                setExecutionDetails((prev) => ({
                  ...prev,
                  [row.id]: { ...prev[row.id], logs, elapsedMs: Date.now() - started }
                }));
              } else if (data.type === "close") {
                const passed = data.code === 0;
                finalRun = {
                  id: `test-run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
                  kind: "test",
                  fixtureId: row.id,
                  fixtureLabel: row.label,
                  at: new Date().toISOString(),
                  elapsedMs: Date.now() - started,
                  ok: passed,
                  exitCode: data.code,
                  command: row.command,
                  sub: row.sub || "",
                  detail: row.detail || "",
                  reportPath: reportPathForRow(row),
                  summary: passed ? "Command completed and reports were refreshed." : `Command failed with exit code ${data.code}.`,
                };
                setExecutionDetails((prev) => ({
                  ...prev,
                  [row.id]: {
                    ...prev[row.id],
                    status: passed ? "Passed" : "Failed",
                    exitCode: data.code,
                    elapsedMs: Date.now() - started
                  }
                }));
                setToast({ kind: passed ? "success" : "error", message: passed ? `${row.label} completed.` : `${row.label} failed.` });
              } else if (data.type === "error") {
                logs += `\nError: ${data.message}\n`;
                setExecutionDetails((prev) => ({
                  ...prev,
                  [row.id]: { ...prev[row.id], status: "Failed", logs, elapsedMs: Date.now() - started }
                }));
              }
            } catch (e) {}
          }
        }
      }
      await refreshAllReports();
      if (finalRun) {
        setRuns((prev) => {
          const next = [finalRun, ...prev].slice(0, 50);
          saveRuns(next);
          return next;
        });
      }
    } catch (error) {
      const failedRun = {
        id: `test-run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
        kind: "test",
        fixtureId: row.id,
        fixtureLabel: row.label,
        at: new Date().toISOString(),
        elapsedMs: Date.now() - started,
        ok: false,
        command: row.command,
        sub: row.sub || "",
        detail: row.detail || "",
        reportPath: reportPathForRow(row),
        error: error.message || String(error),
      };
      setRuns((prev) => {
        const next = [failedRun, ...prev].slice(0, 50);
        saveRuns(next);
        return next;
      });
      setExecutionDetails((prev) => ({
        ...prev,
        [row.id]: {
          ...prev[row.id],
          status: "Failed",
          logs: (prev[row.id]?.logs || "") + `\nExecution Error: ${error.message}\n`,
          elapsedMs: Date.now() - started
        }
      }));
      setToast({ kind: "error", message: error.message || `Unable to run ${row.label}.` });
    } finally {
      setRunningRows((prev) => prev.filter((id) => id !== row.id));
    }
  }
  function handleCopyRow(row) { navigator.clipboard.writeText(row.command || ""); }
  async function runAllVisible() {
    for (const row of rows) {
      if (row.command) await handleRunRow(row);
    }
  }
  async function runSelectedVisible() {
    for (const row of rows) {
      if (row._selected && row.command) await handleRunRow(row);
    }
  }
  function toggleRowSelected(id) {
    setSelectedRowIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      saveSelectedRowIds(next);
      return next;
    });
  }

  function handleLogout() {
    clearSession(); setUser(null);
    setAuthStatus({ state: "error", message: "Signed out. Log in again from the recruiter app." });
  }

  const tabs = [
    { id: "unit", label: "Unit", count: TEST_CATALOG.unit.length },
    { id: "integration", label: "Integration", count: TEST_CATALOG.integration.length },
    { id: "performance", label: "Performance", count: TEST_CATALOG.performance.length },
  ];
  const allRows = TEST_CATALOG[activeTab] || [];
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allRows
      .map((r) => ({ ...r, _selected: selectedRowIds.includes(r.id) }))
      .filter((r) => {
        if (filterKind !== "all" && r.kind !== filterKind) return false;
        if (!q) return true;
        return (r.label + " " + (r.sub || "") + " " + (r.detail || "")).toLowerCase().includes(q);
      });
  }, [allRows, query, filterKind, selectedRowIds]);

  const kindOptions = useMemo(() => {
    const set = new Set(allRows.map((r) => r.kind).filter(Boolean));
    return ["all", ...Array.from(set)];
  }, [allRows]);

  const reportKindOptions = useMemo(() => {
    const set = new Set(REPORT_CATALOG.map((r) => r.kind).filter(Boolean));
    return ["all", ...Array.from(set)];
  }, []);

  const filteredReports = useMemo(() => {
    const q = reportQuery.trim().toLowerCase();
    return REPORT_CATALOG.filter((report) => {
      const matchesQuery = !q || [report.title, report.kind, report.filename, report.path].filter(Boolean).join(" ").toLowerCase().includes(q);
      const matchesKind = reportKind === "all" || report.kind === reportKind;
      return matchesQuery && matchesKind;
    });
  }, [reportKind, reportQuery]);
  const recentRunRows = useMemo(() => runsToXlsxRows(runs).slice(0, 10), [runs]);

  return (
    <div className="testing-shell">
      <header className="testing-header">
        <div className="testing-brand">
          <div className="testing-brand-mark"><FlaskConical size={18} /></div>
          <div>
            <h1>Testing Dashboard</h1>
            <p>Manager-only view for evaluating the resume analyzer.</p>
          </div>
        </div>
        <div className="testing-user">
          <span className={`testing-status ${authStatus.state === "ok" ? "ok" : authStatus.state === "error" ? "err" : ""}`}>
            {authStatus.state === "ok" ? "Session valid" : authStatus.state === "error" ? "Session invalid" : "Checking..."}
          </span>
          <span>·</span>
          <span className={`testing-status ${analysisStatus.state === "ok" ? "ok" : analysisStatus.state === "err" ? "err" : ""}`}>
            {analysisStatus.state === "ok" ? "FastAPI up" : analysisStatus.state === "err" ? "FastAPI down" : "Checking..."}
          </span>
          {user ? <strong style={{ marginLeft: 6 }}>{user.email}</strong> : null}
          <Link
            to="/report-summary"
            className="rs-nav-btn"
            type="button"
            title="View, summarize, and download previously generated reports"
          >
            <ClipboardList size={13} />
            Report Summary
          </Link>
          <button className="secondary tiny" onClick={handleLogout} type="button">
            <LogOut size={12} /> Logout
          </button>
        </div>
      </header>

      {toast ? (
        <div className={`testing-toast ${toast.kind}`}>{toast.message}</div>
      ) : null}

      <aside className="testing-sidebar">
        <div className="testing-sidebar-header">
          <div>
            <h2>Fixture Workbench</h2>
            <p>{selectedFixtures.length}/{fixtures.length} selected</p>
          </div>
          <div className="testing-badge"><Sparkles size={12} /> Live</div>
        </div>
        <div className="testing-sidebar-tools">
          <button className="secondary tiny" type="button" onClick={selectAll}>Select all</button>
          <button className="secondary tiny" type="button" onClick={selectNone}>Clear</button>
          <button className="secondary tiny" type="button" onClick={addFixture}><Plus size={12} /> New</button>
          {active ? (
            <button className="secondary tiny danger" type="button" onClick={() => deleteFixture(active.id)}>
              <Trash2 size={12} /> Delete
            </button>
          ) : null}
        </div>
        <ul className="testing-list">
          {fixtures.map((f) => {
            const isActive = f.id === activeId;
            const isSelected = selectedIds.includes(f.id);
            return (
              <li key={f.id} style={{ display: "flex", gap: 6, alignItems: "stretch" }}>
                <button
                  type="button"
                  className={`testing-list-item ${isActive ? "active" : ""}`}
                  onClick={() => pickFixture(f.id)}
                  style={{ flex: 1 }}
                  title={f.label}
                >
                  <span style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
                    <span className="li-name">{f.label}</span>
                    <span className="li-meta">{f.resume ? `${f.resume.length} chars` : "no resume"}</span>
                  </span>
                </button>
                <label
                  className="testing-list-item"
                  style={{ flex: "0 0 auto", padding: "0 10px", cursor: "pointer" }}
                  title={isSelected ? "Remove from batch" : "Add to batch"}
                >
                  <input type="checkbox" checked={isSelected} onChange={() => toggleSelected(f.id)} />
                </label>
              </li>
            );
          })}
        </ul>

        {active ? (
          <div className="testing-fixture-card">
            <h3>Active fixture</h3>
            <label>
              Label
              <input type="text" value={active.label} onChange={(e) => renameActive(e.target.value)} />
            </label>
            <label>
              Job description
              <textarea value={jobText} onChange={(e) => updateActiveField("job", e.target.value)} />
            </label>
            <label>
              Resume text
              <textarea value={resumeText} onChange={(e) => updateActiveField("resume", e.target.value)} />
            </label>
            <div className="row">
              <button className="primary" type="button" onClick={runAnalysis} disabled={isRunning} title="Run analyzer against this fixture only">
                {isRunning ? <Loader2 size={14} className="spin" /> : <PlayCircle size={14} />}
                {isRunning ? "Running..." : "Run this fixture"}
              </button>
              <button className="secondary" type="button" onClick={runSelectedFixtures} disabled={isRunning || selectedFixtures.length === 0}>
                <PlayCircle size={14} /> Run selected ({selectedFixtures.length})
              </button>
            </div>
            {error ? <div className="testing-error">{error}</div> : null}
          </div>
        ) : (
          <div className="testing-empty">Pick or create a fixture to begin.</div>
        )}
      </aside>

      <main className="testing-main">
        <section className="testing-section">

          <div className="testing-section-header">
            <div>
              <h2>Reports Generated</h2>
              <p>Auto-discover, open, download, or refresh generated reports.</p>
            </div>
            <div style={{ flex: 1 }} />
            <div className="testing-inline-tools">
              <input type="text" placeholder="Search reports" value={reportQuery} onChange={(e) => setReportQuery(e.target.value)} />
              <select value={reportKind} onChange={(e) => setReportKind(e.target.value)}>
                {reportKindOptions.map((k) => <option key={k} value={k}>{k === "all" ? "All kinds" : k}</option>)}
              </select>
              <button className="secondary tiny" type="button" onClick={refreshAllReports} disabled={refreshingReports}>
                {refreshingReports ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh all
              </button>
            </div>
          </div>
          <div className="testing-section-body">
            {REPORT_CATALOG.length === 0 ? (
              <div className="testing-empty">No report types configured yet. Add entries to <code>reportCatalog.js</code>.</div>
            ) : (
              <div className="testing-report-grid">
                {filteredReports.map((r) => (
                  <ReportCard
                    key={r.id}
                    report={r}
                    meta={reportsState[r.id]}
                    onOpen={openReport}
                    onDownload={downloadReport}
                    onRefresh={refreshReport}
                    onRun={handleRunReport}
                    runDetail={reportRunDetails[r.id]}
                    collapsed={!!collapsedReports[r.id]}
                    onToggleCollapsed={(id) => setCollapsedReports((prev) => ({ ...prev, [id]: !prev[id] }))}
                  />
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="testing-section">
          <div className="testing-section-header">
            <h2>Tests</h2>
            <p>Unit · Integration · Performance</p>
          </div>
          <div className="testing-section-body">
            <div className="testing-tests-toolbar">
              <div className="nav-tabs">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`testing-tab ${activeTab === tab.id ? "active" : ""}`}
                    onClick={() => { setActiveTab(tab.id); setSelectedRowIds([]); }}
                  >
                    {tab.label}
                    <span className="testing-tab-count">{tab.count}</span>
                  </button>
                ))}
              </div>
              <div style={{ flex: 1 }} />
              <div style={{ position: "relative" }}>
                <Search size={14} style={{ position: "absolute", left: 8, top: 10, color: "#9aa6a0" }} />
                <input
                  type="text"
                  placeholder="Search tests"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  style={{ paddingLeft: 28, minWidth: 180 }}
                />
              </div>
              <select value={filterKind} onChange={(e) => setFilterKind(e.target.value)}>
                {kindOptions.map((k) => <option key={k} value={k}>{k === "all" ? "All kinds" : k}</option>)}
              </select>
              <button className="secondary tiny" type="button" onClick={runSelectedVisible} disabled={selectedRowIds.length === 0}>
                <PlayCircle size={12} /> Run selected ({selectedRowIds.length})
              </button>
              <button className="primary tiny" type="button" onClick={runAllVisible}>
                <PlayCircle size={12} /> Run all ({rows.length})
              </button>
            </div>

            <div className="testing-rows-container">
              {rows.length === 0 ? (
                <div className="testing-empty">No tests match the current search/filter.</div>
              ) : (
                <div className="testing-rows">
                  {rows.map((row) => (
                    <div className="testing-row" key={row.id} style={{ display: "block" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between" }}>
                        <div className="testing-row-main" style={{ textAlign: "left" }}>
                          <div className="testing-row-label">
                            <input
                              type="checkbox"
                              checked={row._selected}
                              onChange={() => toggleRowSelected(row.id)}
                              style={{ width: 14, height: 14, accentColor: "#82b4a7" }}
                            />
                            <span className="testing-row-name" style={{ marginLeft: 8 }}>{row.label}</span>
                            {kindPill(row.kind)}
                            {executionDetails[row.id] && (
                              <span className={`testing-status ${
                                executionDetails[row.id].status === "Passed" ? "ok" :
                                executionDetails[row.id].status === "Failed" ? "err" : "run"
                              }`} style={{ marginLeft: 8 }}>
                                {executionDetails[row.id].status}
                              </span>
                            )}
                          </div>
                          <div className="testing-row-sub">{row.sub}</div>
                          {row.detail ? <div className="testing-row-sub" style={{ fontStyle: "italic", color: "#7a8580" }}>{row.detail}</div> : null}
                        </div>
                        <div className="testing-row-actions">
                          {row.file ? (
                            <button className="secondary" type="button" onClick={() => window.open(toBrowserPath(row.file), "_blank", "noopener,noreferrer")} title={`Open ${row.file}`}>
                              <ExternalLink size={12} /> View
                            </button>
                          ) : null}
                          {row.command ? (
                            <>
                              <button className="primary" type="button" onClick={() => handleRunRow(row)} title={row.command} disabled={runningRows.includes(row.id)}>
                                {runningRows.includes(row.id) ? <Loader2 size={12} className="spin" /> : <PlayCircle size={12} />}
                                {runningRows.includes(row.id) ? "Running" : "Run"}
                              </button>
                              <button className="secondary" type="button" onClick={() => handleCopyRow(row)} title={row.command}>
                                <Copy size={12} /> Copy cmd
                              </button>
                            </>
                          ) : null}
                        </div>
                      </div>
                      {executionDetails[row.id] && (
                        <div className="testing-console-output">
                          <div className="console-header">
                            <span>Elapsed: {(executionDetails[row.id].elapsedMs / 1000).toFixed(1)}s</span>
                            {executionDetails[row.id].exitCode !== null && <span>Exit code: {executionDetails[row.id].exitCode}</span>}
                            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Artifacts: <code>{executionDetails[row.id].outputDir}</code></span>
                          </div>
                          <pre className="console-logs">{executionDetails[row.id].logs}</pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {activeTab === "performance" ? (
              <div style={{ marginTop: 14 }}>
                <h3 style={{ marginBottom: 8 }}>Performance summary</h3>
                <div className="metric-grid">
                  <MetricCard label="Total runs" value={runs.length} sub="Stored in this browser" />
                  <MetricCard label="Successful" value={runs.filter((r) => r.ok).length} sub={`${runs.length ? Math.round((runs.filter((r) => r.ok).length / runs.length) * 100) : 0}% success`} pct={runs.length ? (runs.filter((r) => r.ok).length / runs.length) * 100 : 0} />
                  <MetricCard label="Avg latency" value={`${runs.length ? Math.round(runs.reduce((a, r) => a + (r.elapsedMs || 0), 0) / runs.length) : 0} ms`} sub="Across visible fixture runs" />
                  <MetricCard label="p95 latency" value={`${runs.length ? (runs.map((r) => r.elapsedMs || 0).sort((a, b) => a - b)[Math.floor(runs.length * 0.95)] || 0) : 0} ms`} sub="Approximation, browser-side" />
                </div>
                <p className="testing-muted" style={{ marginTop: 8 }}>More graphs (latency histogram, p99 over time, success rate trend) will live here.</p>
              </div>
            ) : null}

            <div className="testing-recent-runs">
              <div className="testing-sidebar-header testing-recent-runs-header">
                <div>
                  <h3>Recent runs</h3>
                  <p>Latest test and analyzer runs in the same 13-column layout used by the XLSX report.</p>
                </div>
                <div style={{ flex: 1 }} />
                <button
                  className="primary tiny"
                  type="button"
                  onClick={() => exportRunsToXlsx(runs)}
                  disabled={runs.length === 0}
                  title="Download all stored recent runs as a 13-column XLSX file"
                >
                  <Download size={12} /> Export XLSX
                </button>
                <button className="secondary tiny" type="button" onClick={() => { setRuns([]); saveRuns([]); }} disabled={runs.length === 0}>
                  <Trash2 size={12} /> Clear
                </button>
              </div>
              {runs.length === 0 ? (
                <div className="testing-empty">No recent runs yet. Click any Run button or Run all to populate this table and enable XLSX export.</div>
              ) : (
              <div className="testing-recent-runs">
                <div className="testing-table-scroll">
                  <table className="testing-table testing-recent-table">
                    <thead>
                      <tr>
                        {XLSX_COLUMNS.map((column) => (
                          <th key={column.key}>{column.header}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {recentRunRows.map((row) => (
                        <tr key={`${row.index}-${row.timestamp}-${row.fixture}`}>
                          {XLSX_COLUMNS.map((column) => (
                            <td
                              key={column.key}
                              className={["srNo", "crNo"].includes(column.key) ? "testing-mono" : ""}
                            >
                              {column.key === "passFail" ? (
                                row.passFail === "Pass"
                                  ? <span className="testing-status ok"><CheckCircle2 size={12} /> Pass</span>
                                  : <span className="testing-status err"><XCircle size={12} /> Failed</span>
                              ) : (
                                recentRunCell(row, column.key)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
