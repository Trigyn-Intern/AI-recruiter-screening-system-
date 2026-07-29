import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Copy, FileText } from "lucide-react";
import "./reportsPanel.css";

function ReportsPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/reports.json")
      .then((r) => r.json())
      .then((j) => { if (!cancelled) setData(j); })
      .catch((e) => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  const grouped = useMemo(() => {
    if (!data || !data.reports) return {};
    return data.reports.reduce((acc, r) => {
      (acc[r.category] = acc[r.category] || []).push(r);
      return acc;
    }, {});
  }, [data]);

  function copy(text, id) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
      });
    }
  }

  if (error) {
    return (
      <section className="reports-panel">
        <header><h2>Reports</h2></header>
        <p className="reports-error">Could not load reports.json: {error}</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="reports-panel">
        <header><h2>Reports</h2></header>
        <p className="reports-loading">Loading reports…</p>
      </section>
    );
  }

  const categoryOrder = ["security", "performance", "integration", "review"];
  const categoryLabels = {
    security: "Security",
    performance: "Performance",
    integration: "Integration",
    review: "AI Review",
  };

  return (
    <section className="reports-panel">
      <header className="reports-header">
        <h2>Reports &amp; test runs</h2>
        <p className="reports-meta">
          Each report lists the command, what must be on the machine first, and what the
          tool is expected to produce. Use the copy button to grab the run command; the
          dashboard reads <code>/reports.json</code> for this list.
        </p>
      </header>
      {categoryOrder.filter((c) => grouped[c]).map((cat) => (
        <div key={cat} className="reports-category">
          <h3>{categoryLabels[cat] || cat}</h3>
          <ul className="reports-list">
            {grouped[cat].map((r) => {
              const open = openId === r.id;
              return (
                <li key={r.id} className={"report-card " + (open ? "open" : "")}>
                  <button
                    type="button"
                    className="report-summary"
                    onClick={() => setOpenId(open ? null : r.id)}
                    aria-expanded={open}
                  >
                    <span className="report-caret">
                      {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </span>
                    <span className="report-name">{r.name}</span>
                    <span className={"report-status " + (r.actualLastRun.exists ? "ok" : "missing")}>
                      {r.actualLastRun.exists ? "artifact on disk" : "no local artifact"}
                    </span>
                  </button>
                  {open && (
                    <div className="report-body">
                      <div className="report-row">
                        <h4>Run command</h4>
                        <div className="report-code-wrap">
                          <pre><code>{r.command}</code></pre>
                          <button
                            type="button"
                            className="report-copy"
                            onClick={() => copy(r.command, r.id)}
                            title="Copy command"
                          >
                            <Copy size={14} />
                            {copiedId === r.id ? "Copied" : "Copy"}
                          </button>
                        </div>
                      </div>
                      <div className="report-row">
                        <h4>Prerequisites</h4>
                        <ul className="report-prereqs">
                          {r.prerequisites.map((p, i) => (
                            <li key={i}>{p}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="report-row">
                        <h4>Expected output</h4>
                        <ul className="report-expected">
                          {r.expectedOutput.map((e, i) => (
                            <li key={i}>{e}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="report-row">
                        <h4>Artifact</h4>
                        <p className="report-artifact">
                          <FileText size={14} />
                          <code>{r.actualLastRun.artifact}</code>
                          <span className="report-artifact-note">
                            ({r.actualLastRun.lastModified})
                          </span>
                        </p>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <footer className="reports-footer">
        Last updated: {data.updated}
      </footer>
    </section>
  );
}

export default ReportsPanel;
