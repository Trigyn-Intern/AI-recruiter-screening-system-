import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  FlaskConical, LogOut, FileText, Download, ExternalLink, Loader2,
  ClipboardList, RefreshCw, AlertTriangle, CheckCircle2, Search,
  ShieldAlert, ListChecks, BarChart3, Filter, Sparkles,
  Activity, ArrowDownAZ, ArrowUpAZ, ChevronDown, ChevronRight,
  Gauge, Layers, Zap,
} from "lucide-react";
import { clearSession, getStoredUser, listReports, getReportSummary } from "../api";

const FASTAPI_BASE =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_FASTAPI_URL) ||
  "http://localhost:8000";

const KIND_FILTERS = [
  { id: "all",       label: "All",         match: () => true },
  { id: "security",  label: "Security",    icon: ShieldAlert, match: (k, t) => k === "security" || /security/i.test(t) },
  { id: "code",      label: "Code",        icon: ListChecks,  match: (k, t) => k === "code"     || /code|coverage/i.test(t) },
  { id: "perf",      label: "Performance", icon: BarChart3,   match: (k, t) => k === "perf"     || /performance|lighthouse|allure/i.test(t) },
  { id: "ci",        label: "CI",          icon: Activity,    match: (k)      => k === "ci" },
];

function formatBytes(n) {
  if (!Number.isFinite(n) || n <= 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
function formatDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function BulletList({ items }) {
  if (!items || !items.length) return <div className="rs-bullets-empty">No items.</div>;
  return (
    <ul className="rs-bullets">
      {items.map((it, i) => <li key={i}>{it}</li>)}
    </ul>
  );
}

function StatTile({ label, value, icon: Icon, accent }) {
  return (
    <div className={`rs-stat ${accent || ""}`}>
      {Icon ? <Icon size={16} className="rs-stat-icon" /> : null}
      <div className="rs-stat-label">{label}</div>
      <div className="rs-stat-value">{value}</div>
    </div>
  );
}

function SummaryPanel({ summary, report }) {
  if (!summary) return null;
  return (
    <div className="rs-summary-card">
      <div className="rs-summary-card-header">
        <h4><Sparkles size={14} /> AI Summary · {report.name}</h4>
      </div>
      <div className="rs-summary-grid">
        <div className="rs-section"><h5>Overall Assessment</h5><p>{summary.overall_assessment || "—"}</p></div>
        <div className="rs-section"><h5>Key Findings</h5><BulletList items={summary.key_findings} /></div>
        <div className="rs-section rs-critical-section"><h5 className="rs-critical">Critical Issues</h5><BulletList items={summary.critical_issues} /></div>
        <div className="rs-section rs-medium-section"><h5 className="rs-medium">Medium Issues</h5><BulletList items={summary.medium_issues} /></div>
        <div className="rs-section"><h5>Recommendations</h5><BulletList items={summary.recommendations} /></div>
        <div className="rs-section rs-positive-section"><h5 className="rs-positive">Positive Findings</h5><BulletList items={summary.positive_observations} /></div>
        <div className="rs-section rs-verdict-section"><h5>Conclusion</h5><p>{summary.final_verdict || "—"}</p></div>
      </div>
      <div className="rs-summary-footer">
        <a className="primary tiny" href={`${FASTAPI_BASE}/api/report-view/${report.id}`} target="_blank" rel="noreferrer">
          <ExternalLink size={12} /> Open Full Report
        </a>
        <a className="secondary tiny" href={`${FASTAPI_BASE}/api/report-download/${report.id}`} download>
          <Download size={12} /> Download Report
        </a>
      </div>
    </div>
  );
}

function ReportCard({ report, summary, onOpen, onRegenerate }) {
  const kind = (report.kind || "").toLowerCase();
  const review = report.review_type || report.type || "Report";
  return (
    <details
      className="rs-dropdown"
      onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.toggleAttribute("open"); }}
    >
      <summary
        className="rs-dropdown-summary"
        onClick={(e) => { e.preventDefault(); const d = e.currentTarget.parentElement; d.open = !d.open; onOpen(report); }}
      >
        <span className="rs-caret"><ChevronRight size={14} /></span>
        <span className="rs-card-title"><FileText size={14} /> {report.name}</span>
        <span className={`testing-pill kind-${kind || "report"}`}>{review}</span>
        <code className="rs-card-path" title={report.path}>{report.path}</code>
      </summary>
      <div className="rs-card-meta">
        <span><strong>Generated:</strong> {formatDate(report.generated_at || report.generated_date)}</span>
        <span><strong>Size:</strong> {formatBytes(report.size)}</span>
        {summary && summary.summary ? <span className="rs-badge rs-badge-ok"><CheckCircle2 size={12} /> Summary Ready</span> : null}
        {summary && summary.cached ? <span className="rs-badge rs-badge-info">cached</span> : null}
        {summary && summary.error ? <span className="rs-badge rs-badge-err"><AlertTriangle size={12} /> Summary Failed</span> : null}
      </div>
      <div className="rs-card-actions">
        <button className="secondary tiny" type="button" onClick={() => onRegenerate(report)}>
          <RefreshCw size={12} /> Regenerate
        </button>
        <a className="secondary tiny" href={`${FASTAPI_BASE}/api/report-view/${report.id}`} target="_blank" rel="noreferrer">
          <ExternalLink size={12} /> Open HTML
        </a>
        <a className="secondary tiny" href={`${FASTAPI_BASE}/api/report-download/${report.id}`} download>
          <Download size={12} /> Download
        </a>
      </div>
      <div className="rs-dropdown-body">
        {summary && summary.loading ? (
          <div className="rs-loading">
            <Loader2 size={14} className="spin" /> Generating chunked summary…
            {typeof summary.chunk_count === "number" ? ` (${summary.chunk_count} chunks)` : null}
          </div>
        ) : summary && summary.error ? (
          <div className="rs-error">
            <div className="rs-error-headline">Unable to generate report summary.</div>
            <div className="rs-error-detail">{summary.error}</div>
            <button className="secondary tiny" type="button" onClick={() => onRegenerate(report)}>
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        ) : summary && summary.summary ? (
          <SummaryPanel summary={summary.summary} report={report} />
        ) : (
          <div className="rs-loading"><Loader2 size={14} className="spin" /> Preparing summary…</div>
        )}
      </div>
    </details>
  );
}

function PerfFolder({ reports, summaryState, onOpen, onRegenerate, onBulkSummarize, bulk, bulkLoading }) {
  const [open, setOpen] = useState(false);
  const total = reports.length;
  const ready = reports.filter((r) => summaryState[r.id] && summaryState[r.id].summary).length;
  return (
    <section className={`rs-group rs-group-perf ${open ? "open" : "collapsed"}`}>
      <header className="rs-group-header" onClick={() => setOpen((o) => !o)}>
        <span className="rs-caret">{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
        <Gauge size={16} className="rs-group-icon" />
        <h3>Performance &amp; Allure Results</h3>
        <span className="rs-group-count">{total.toLocaleString()} reports · {ready} summarized</span>
        <div className="rs-group-actions" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="primary tiny"
            disabled={bulkLoading}
            onClick={onBulkSummarize}
          >
            {bulkLoading
              ? <><Loader2 size={12} className="spin" /> Summarizing…</>
              : <><Sparkles size={12} /> Summarize all</>}
          </button>
          <button type="button" className="secondary tiny" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "Show"}
          </button>
        </div>
      </header>
      {open ? (
        <>
          <p className="rs-group-caption">
            <Layers size={12} /> These {total.toLocaleString()} artifacts are very large. They open in a new tab so the dashboard stays responsive.
          </p>
          {bulk && bulk.items ? (
            <div className="rs-bulk-summary">
              <h4><Zap size={14} /> Collective Summary ({bulk.items.filter((i) => i.ok).length}/{bulk.items.length})</h4>
              {bulk.items.slice(0, 12).map((it) => (
                <div key={it.id} className={`rs-bulk-item ${it.ok ? "ok" : "fail"}`}>
                  <div className="rs-bulk-name">
                    {it.ok ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                    <span>{it.name}</span>
                    {it.cached ? <span className="rs-badge rs-badge-info">cached</span> : null}
                  </div>
                  {it.ok && it.summary ? <p>{it.summary.overall_assessment || "—"}</p> : null}
                  {!it.ok ? <p className="rs-bulk-error">{it.error}</p> : null}
                </div>
              ))}
              {bulk.items.length > 12 ? (
                <details className="rs-bulk-more">
                  <summary>+ {bulk.items.length - 12} more</summary>
                  {bulk.items.slice(12).map((it) => (
                    <div key={it.id} className={`rs-bulk-item ${it.ok ? "ok" : "fail"}`}>
                      <div className="rs-bulk-name">
                        {it.ok ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                        <span>{it.name}</span>
                      </div>
                      {it.ok && it.summary ? <p>{it.summary.overall_assessment || "—"}</p> : null}
                      {!it.ok ? <p className="rs-bulk-error">{it.error}</p> : null}
                    </div>
                  ))}
                </details>
              ) : null}
            </div>
          ) : null}
          <details className="rs-perf-list">
            <summary><ChevronRight size={12} /> Browse individual reports</summary>
            <div className="rs-dropdown-grid">
              {reports.map((r) => (
                <ReportCard
                  key={r.id}
                  report={r}
                  summary={summaryState[r.id] || {}}
                  onOpen={onOpen}
                  onRegenerate={onRegenerate}
                />
              ))}
            </div>
          </details>
        </>
      ) : null}
    </section>
  );
}

export default function ReportSummary() {
  const [user] = useState(getStoredUser());
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [summaryState, setSummaryState] = useState({});
  const [toast, setToast] = useState(null);
  const [filterKind, setFilterKind] = useState("all");
  const [query, setQuery] = useState("");
  const [sortDir, setSortDir] = useState("newest");
  const [bulk, setBulk] = useState(null);
  const [bulkLoading, setBulkLoading] = useState(false);

  const showToast = useCallback((kind, message) => {
    setToast({ kind, message });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setListError("");
    try {
      const list = await listReports();
      setReports(list);
    } catch (e) {
      setListError("Unable to load reports. Check backend connection. (" + (e && e.message ? e.message : "network error") + ")");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadReports(); }, [loadReports]);

  const loadSummary = useCallback(async (report, refresh = false) => {
    setSummaryState((prev) => ({
      ...prev,
      [report.id]: { ...(prev[report.id] || {}), loading: true, regenerating: !!refresh, error: "" },
    }));
    try {
      const data = await getReportSummary(report.id, { refresh });
      setSummaryState((prev) => ({
        ...prev,
        [report.id]: {
          loading: false, regenerating: false,
          summary: data.summary, cached: !!data.cached,
          chunk_count: data.chunk_count, error: "",
        },
      }));
    } catch (e) {
      setSummaryState((prev) => ({
        ...prev,
        [report.id]: { ...(prev[report.id] || {}), loading: false, regenerating: false, error: e.message || "Failed to generate summary." },
      }));
      showToast("error", "Unable to generate report summary.");
    }
  }, [showToast]);

  const handleOpen = useCallback((report) => {
    const existing = summaryState[report.id];
    if (!existing || (!existing.summary && !existing.loading)) {
      void loadSummary(report, false);
    }
  }, [summaryState, loadSummary]);

  const handleRegenerate = useCallback((report) => { void loadSummary(report, true); }, [loadSummary]);
  const handleLogout = useCallback(() => { clearSession(); window.location.assign("/"); }, []);

  const handleBulkSummarize = useCallback(async () => {
    setBulkLoading(true);
    try {
      const res = await fetch(`${FASTAPI_BASE}/api/reports/bulk-summary?group=performance`);
      const data = await res.json();
      if (!res.ok) throw new Error((data && data.detail) || `HTTP ${res.status}`);
      setBulk(data);
      const next = { ...summaryState };
      for (const it of (data.items || [])) {
        if (it.ok && it.summary) {
          next[it.id] = { loading: false, summary: it.summary, cached: !!it.cached, error: "" };
        }
      }
      setSummaryState(next);
      showToast("success", `Summarized ${data.items.filter((i) => i.ok).length}/${data.total} perf reports.`);
    } catch (e) {
      showToast("error", "Bulk summary failed: " + (e.message || "network error"));
    } finally {
      setBulkLoading(false);
    }
  }, [summaryState, showToast]);

  const { reportRows, perfRows } = useMemo(() => {
    const filter = KIND_FILTERS.find((f) => f.id === filterKind) || KIND_FILTERS[0];
    const q = query.trim().toLowerCase();
    const matches = (r) => {
      if (!filter.match((r.kind || "").toLowerCase(), (r.review_type || r.type || "").toLowerCase())) return false;
      if (!q) return true;
      return [r.name, r.review_type, r.type, r.path].filter(Boolean).join(" ").toLowerCase().includes(q);
    };
    const sortFn = (a, b) => {
      const da = new Date(a.generated_at || a.generated_date || 0).getTime();
      const db = new Date(b.generated_at || b.generated_date || 0).getTime();
      return sortDir === "oldest" ? da - db : db - da;
    };
    const filtered = reports.filter(matches);
    return {
      reportRows: filtered.filter((r) => (r.group || "report") !== "performance").sort(sortFn),
      perfRows:   filtered.filter((r) => (r.group || "report") === "performance").sort(sortFn),
    };
  }, [reports, filterKind, query, sortDir]);

  const stats = useMemo(() => {
    const out = { total: reports.length, security: 0, code: 0, perf: 0, summaries: 0 };
    for (const r of reports) {
      const t = (r.review_type || r.type || "").toLowerCase();
      const k = (r.kind || "").toLowerCase();
      if (k === "security" || /security/.test(t)) out.security++;
      if (k === "code" || /code|coverage/.test(t)) out.code++;
      if (k === "perf" || /performance|lighthouse|allure/i.test(t)) out.perf++;
      const s = summaryState[r.id];
      if (s && s.summary) out.summaries++;
    }
    return out;
  }, [reports, summaryState]);

  const showPerf = filterKind === "all" || filterKind === "perf";
  const showReports = filterKind !== "perf";

  return (
    <div className="testing-shell rs-shell">
      <header className="testing-header">
        <div className="testing-brand">
          <div className="testing-brand-mark"><FlaskConical size={18} /></div>
          <div>
            <h1>Report Summary Dashboard</h1>
            <p>Browse, summarize, and download every generated report. Performance artifacts are grouped so the page stays fast.</p>
          </div>
        </div>
        <div className="testing-user">
          <Link to="/" className="secondary tiny" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>
            ← Testing Dashboard
          </Link>
          {user ? <strong style={{ marginLeft: 6 }}>{user.email}</strong> : null}
          <button className="secondary tiny" onClick={handleLogout} type="button">
            <LogOut size={12} /> Logout
          </button>
        </div>
      </header>

      {toast ? <div className={`testing-toast ${toast.kind}`}>{toast.message}</div> : null}

      <main className="testing-main rs-main">
        <section className="testing-section">
          <div className="testing-section-header">
            <div>
              <h2>Generated Reports</h2>
              <p>Reports open one at a time. The Performance &amp; Allure bucket is collapsed by default.</p>
            </div>
          </div>
          <div className="testing-section-body">
            <div className="rs-stat-grid">
              <StatTile label="Total Reports"        value={stats.total}    icon={ClipboardList} />
              <StatTile label="Security Reviews"     value={stats.security} icon={ShieldAlert} accent="rs-stat-red" />
              <StatTile label="Code Reviews"         value={stats.code}     icon={ListChecks}  accent="rs-stat-blue" />
              <StatTile label="Performance Reviews"  value={stats.perf}     icon={BarChart3}   accent="rs-stat-amber" />
              <StatTile label="Summaries Generated"  value={stats.summaries} icon={Sparkles}   accent="rs-stat-green" />
            </div>

            <div className="rs-filters">
              <div className="rs-filter-pills">
                {KIND_FILTERS.map((f) => {
                  const Icon = f.icon || Filter;
                  return (
                    <button key={f.id} type="button" className={`rs-pill ${filterKind === f.id ? "active" : ""}`} onClick={() => setFilterKind(f.id)}>
                      <Icon size={12} /> {f.label}
                    </button>
                  );
                })}
              </div>
              <div className="rs-filter-tools">
                <div style={{ position: "relative" }}>
                  <Search size={14} style={{ position: "absolute", left: 8, top: 10, color: "#9aa6a0" }} />
                  <input type="text" placeholder="Search reports" value={query} onChange={(e) => setQuery(e.target.value)} style={{ paddingLeft: 28, minWidth: 200 }} />
                </div>
                <button type="button" className="secondary tiny" onClick={() => setSortDir((d) => (d === "newest" ? "oldest" : "newest"))}>
                  {sortDir === "newest" ? <ArrowDownAZ size={12} /> : <ArrowUpAZ size={12} />} {sortDir === "newest" ? "Newest First" : "Oldest First"}
                </button>
                <button className="secondary tiny" type="button" onClick={loadReports} disabled={loading}>
                  {loading ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Refresh
                </button>
              </div>
            </div>

            {listError ? (
              <div className="rs-load-error">
                <div className="rs-error-headline"><AlertTriangle size={14} /> Unable to load reports.</div>
                <div className="rs-error-detail">Check backend connection. {listError}</div>
                <button className="primary tiny" type="button" onClick={loadReports} disabled={loading}>
                  {loading ? <Loader2 size={12} className="spin" /> : <RefreshCw size={12} />} Retry
                </button>
              </div>
            ) : loading && reports.length === 0 ? (
              <div className="testing-empty"><Loader2 size={14} className="spin" /> Loading reports…</div>
            ) : reportRows.length === 0 && perfRows.length === 0 ? (
              <div className="testing-empty">No generated reports found. Run a review to populate this list.</div>
            ) : (
              <>
                {showReports ? (
                  <section className="rs-group rs-group-reports">
                    <header className="rs-group-header static">
                      <FileText size={16} className="rs-group-icon" />
                      <h3>Reports</h3>
                      <span className="rs-group-count">{reportRows.length} reports</span>
                    </header>
                    <div className="rs-dropdown-grid">
                      {reportRows.map((r) => (
                        <ReportCard
                          key={r.id}
                          report={r}
                          summary={summaryState[r.id] || {}}
                          onOpen={handleOpen}
                          onRegenerate={handleRegenerate}
                        />
                      ))}
                    </div>
                  </section>
                ) : null}

                {showPerf ? (
                  <PerfFolder
                    reports={perfRows}
                    summaryState={summaryState}
                    onOpen={handleOpen}
                    onRegenerate={handleRegenerate}
                    onBulkSummarize={handleBulkSummarize}
                    bulk={bulk}
                    bulkLoading={bulkLoading}
                  />
                ) : null}
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
