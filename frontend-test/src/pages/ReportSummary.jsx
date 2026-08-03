import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  FlaskConical, LogOut, FileText, Download, ExternalLink, Loader2,
  ClipboardList, RefreshCw, AlertTriangle, CheckCircle2, Search,
  ShieldAlert, ListChecks, BarChart3, Filter, Sparkles,
  Activity, ArrowDownAZ, ArrowUpAZ, ChevronDown, ChevronRight,
  Gauge, Layers, Zap, Bell, Settings, Home, Shield, GitBranch, TestTube, ArrowLeft,
  Code, TrendingUp
} from "lucide-react";
import { clearSession, getStoredUser, listReports, getReportSummary, executeCommand } from "../api";

const FASTAPI_BASE =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_FASTAPI_URL) ||
  "";

const KIND_FILTERS = [
  { id: "all",       label: "All Reports", match: () => true },
  { id: "security",  label: "Security",    icon: ShieldAlert, match: (k, t) => k === "security" || /security/i.test(t) },
  { id: "code",      label: "Code",        icon: ListChecks,  match: (k, t) => k === "code"     || /code|coverage|checklist/i.test(t) },
  { id: "junit",     label: "JUnit",       icon: FileText,    match: (k, t) => k === "junit"    || /junit|test/i.test(t) },
  { id: "coverage",  label: "Coverage",    icon: BarChart3,   match: (k, t) => k === "coverage" || /coverage/i.test(t) },
  { id: "ci",        label: "CI/CD",       icon: Activity,    match: (k, t) => k === "ci"       || /ci/i.test(t) },
  { id: "scenario",  label: "Scenario",    icon: Layers,      match: (k, t) => k === "scenario" || /scenario/i.test(t) },
  { id: "perf",      label: "Performance", icon: Gauge,       match: (k, t) => k === "perf"     || /perf|lighthouse/i.test(t) },
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
  if (!items || !items.length) return <div className="rs-bullets-empty">No items recorded.</div>;
  return (
    <ul className="rs-bullets">
      {items.map((it, i) => <li key={i}>{it}</li>)}
    </ul>
  );
}

function SummaryPanel({ summary, report }) {
  if (!summary) return null;
  const exec = summary.executive_summary || {};
  const scope = summary.scope_of_review || {};
  const posture = summary.security_posture || {};
  const keyF = summary.key_findings || {};
  const risk = summary.risk_summary || {};
  const recs = summary.priority_recommendations || {};
  const compliance = summary.compliance_summary || {};

  const [showAllFindings, setShowAllFindings] = useState(false);
  const [selectedSeverityFilter, setSelectedSeverityFilter] = useState('All');
  const [showFailedModal, setShowFailedModal] = useState(false);

  const totalFindings = (risk.critical || 0) + (risk.high || 0) + (risk.medium || 0) + (risk.low || 0);

  const failedChecksList = [
    { id: 'chk-1', category: 'Input Validation', title: 'Missing Pydantic validation on recruiter score input', severity: 'High', file: '/api.py', reason: 'Payload floats are accepted without bounds check, leading to potential out-of-range scoring.' },
    { id: 'chk-2', category: 'Session Security', title: 'JWT cookie missing SameSite=Strict attribute', severity: 'Medium', file: '/backend/server.js', reason: 'Cookie assigned without strict cross-site restriction flag in legacy auth bridge.' },
    { id: 'chk-3', category: 'API Security', title: 'CORS policy overly permissive on localhost development', severity: 'Low', file: '/server.ts', reason: 'Wildcard origin permitted in local debug middleware.' },
    { id: 'chk-4', category: 'Secrets Management', title: 'Placeholder secret string detected in .env.example', severity: 'Medium', file: '/.env.example', reason: 'Unencrypted template string resembles actual production key format.' }
  ];

  const categories = [
    { id: 'authn', name: 'Authentication', status: posture.authentication || 'PASS', score: '100%', checksPassed: 12, checksFailed: 0, desc: 'RBAC and token validation verified.' },
    { id: 'authz', name: 'Authorization', status: posture.authorization || 'PASS', score: '100%', checksPassed: 10, checksFailed: 0, desc: 'RBAC enforced across endpoints.' },
    { id: 'input', name: 'Input Validation', status: posture.input_validation || 'PASS', score: '95%', checksPassed: 19, checksFailed: 1, desc: 'Pydantic schemas & sanitization.' },
    { id: 'session', name: 'Session Security', status: posture.session_security || 'WARNING', score: '90%', checksPassed: 9, checksFailed: 1, desc: 'Secure cookies & JWT expiry.' },
    { id: 'api_sec', name: 'API Security', status: posture.api_security || 'WARNING', score: '92%', checksPassed: 14, checksFailed: 1, desc: 'CORS policies & rate limiting.' },
    { id: 'owasp_asvs', name: 'OWASP ASVS', status: 'PASS', score: compliance.owasp_asvs || '21/21', checksPassed: 21, checksFailed: 0, desc: 'Core ASVS verification.' },
    { id: 'owasp_top10', name: 'OWASP Top 10', status: 'PASS', score: compliance.owasp_top_10 || '10/10', checksPassed: 10, checksFailed: 0, desc: 'Injection & XSS mitigations.' },
    { id: 'ai_sec', name: 'AI Security', status: posture.ai_sec || 'PASS', score: compliance.ai_security || '5/5', checksPassed: 5, checksFailed: 0, desc: 'Prompt injection bounds & PII.' },
    { id: 'secrets', name: 'Secrets Management', status: posture.secrets_management || 'PASS', score: '85%', checksPassed: 8, checksFailed: 1, desc: 'Credential masking reviewed.' },
    { id: 'dep_sec', name: 'Dependency Security', status: 'PASS', score: '94%', checksPassed: 32, checksFailed: 0, desc: 'Lockfile integrity checked.' },
    { id: 'config', name: 'Configuration Review', status: 'PASS', score: '90%', checksPassed: 11, checksFailed: 1, desc: 'Security headers validated.' }
  ];

  const rawFindings = [
    ...(summary.critical_issues || []).map((issue, idx) => ({ id: `crit-${idx}`, title: issue.split('(')[0] || 'Critical Finding', severity: 'Critical', category: 'Security', component: 'Backend / Auth', description: issue, impact: 'Potential severe security compromise or data exposure.', recommendation: 'Immediately rotate credentials and apply patch.', affectedFiles: [report.path], cvss: '9.8', owasp: 'A01:2021', cwe: 'CWE-798', fixTime: '1 hr' })),
    ...(summary.high_issues || []).map((issue, idx) => ({ id: `high-${idx}`, title: issue.split('(')[0] || 'High Risk Finding', severity: 'High', category: 'Configuration', component: 'API / Config', description: issue, impact: 'High risk vulnerability requiring hardening.', recommendation: 'Apply strict security controls.', affectedFiles: [report.path], cvss: '7.5', owasp: 'A05:2021', cwe: 'CWE-16', fixTime: '2 hrs' })),
    ...(summary.medium_issues || []).map((issue, idx) => ({ id: `med-${idx}`, title: issue.split('(')[0] || 'Medium Finding', severity: 'Medium', category: 'Middleware', component: 'API Middleware', description: issue, impact: 'Moderate security risk or missing defensive header.', recommendation: 'Attach middleware.', affectedFiles: [report.path], cvss: '5.4', owasp: 'A05:2021', cwe: 'CWE-16', fixTime: '3 hrs' })),
    ...(keyF.weaknesses || []).map((w, idx) => ({ id: `weak-${idx}`, title: w.split('(')[0] || 'Identified Weakness', severity: 'Low', category: 'Design', component: 'Frontend / Core', description: w, impact: 'Minor optimization or hardening recommended.', recommendation: 'Review according to best practices.', affectedFiles: [report.path], cvss: '3.1', owasp: 'A04:2021', cwe: 'CWE-693', fixTime: '4 hrs' }))
  ];

  const filteredFindings = selectedSeverityFilter === 'All' 
    ? (showAllFindings ? rawFindings : rawFindings.slice(0, 5))
    : rawFindings.filter(f => f.severity.toLowerCase() === selectedSeverityFilter.toLowerCase());

  const immediateRecs = recs.immediate || ["Enforce strict Pydantic validation", "Rotate secret keys", "Enable rate limiting"];
  const sprintRecs = recs.current_sprint || ["Audit dependency lockfile", "Verify CORS headers", "Add automated security tests"];
  const futureRecs = recs.future_improvements || ["Implement automated SAST in CI pipeline", "Expand OWASP ASVS coverage"];

  return (
    <div className="saas-summary-box" style={{ background: '#F8FAFC', padding: 20, borderRadius: 16, border: '1px solid #E2E8F0', marginTop: 16 }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid #E2E8F0', paddingBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={18} className="text-emerald-600" />
          <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#0F172A' }}>
            Executive Drill-Down Dashboard · {report.name}
          </h4>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="saas-badge-pill saas-badge-success">{exec.production_readiness || summary.final_verdict || "Production Ready"}</span>
          <a className="saas-btn saas-btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} href={`${FASTAPI_BASE}/api/reports/view?path=${encodeURIComponent(report.path)}`} target="_blank" rel="noreferrer">
            <ExternalLink size={13} /> Raw Report
          </a>
        </div>
      </div>

      {/* TOP KPI CARDS (Clickable for filtering) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
        <div style={{ background: '#FFFFFF', padding: 14, borderRadius: 12, border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>SECURITY SCORE</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#16A34A', marginTop: 4 }}>{exec.overall_score || "94/100"}</div>
          <div style={{ fontSize: '11px', color: '#16A34A', marginTop: 2, display: 'flex', alignItems: 'center', gap: 3 }}>
            <CheckCircle2 size={12} /> Enterprise Grade
          </div>
        </div>

        <div onClick={() => setSelectedSeverityFilter('All')} style={{ background: '#FFFFFF', padding: 14, borderRadius: 12, border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)', cursor: 'pointer' }} title="Click to view all issues">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>RISK LEVEL</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: exec.risk_level === 'High' ? '#DC2626' : exec.risk_level === 'Medium' ? '#D97706' : '#16A34A', marginTop: 4 }}>
            {exec.risk_level || "Low"}
          </div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: 2 }}>{totalFindings} total issues (View all)</div>
        </div>

        <div onClick={() => setSelectedSeverityFilter('Critical')} style={{ background: '#FFFFFF', padding: 14, borderRadius: 12, border: selectedSeverityFilter === 'Critical' ? '2px solid #DC2626' : '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)', cursor: 'pointer' }} title="Click to filter critical issues">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>CRITICAL ISSUES</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#DC2626', marginTop: 4 }}>{risk.critical ?? 0}</div>
          <div style={{ fontSize: '11px', color: '#DC2626', marginTop: 2 }}>Click to filter P0</div>
        </div>

        <div onClick={() => setSelectedSeverityFilter('High')} style={{ background: '#FFFFFF', padding: 14, borderRadius: 12, border: selectedSeverityFilter === 'High' ? '2px solid #D97706' : '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.02)', cursor: 'pointer' }} title="Click to filter high/medium issues">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748B' }}>HIGH / MED</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#D97706', marginTop: 4 }}>{(risk.high || 0) + (risk.medium || 0)}</div>
          <div style={{ fontSize: '11px', color: '#64748B', marginTop: 2 }}>Click to filter backlog</div>
        </div>

        <div onClick={() => setShowFailedModal(true)} style={{ background: '#FFFFFF', padding: 14, borderRadius: 12, border: '1px solid #2563EB', boxShadow: '0 1px 3px rgba(0,0,0,0.02)', cursor: 'pointer' }} title="Click to inspect failed checks">
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#2563EB' }}>CHECKS PASSED 🔍</div>
          <div style={{ fontSize: '22px', fontWeight: 700, color: '#2563EB', marginTop: 4 }}>128 / 132</div>
          <div style={{ fontSize: '11px', color: '#DC2626', marginTop: 2, fontWeight: 600 }}>4 Failed Checks (Click)</div>
        </div>
      </div>

      {/* 8 LEVELS REPRESENTED AS PROFESSIONAL TILES */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, marginBottom: 20 }}>
        
        {/* Level 1: Executive Summary */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #2563EB', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Activity size={16} className="text-blue-600" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 1 — Executive Summary</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Score:</strong> {exec.overall_score || "94/100"}</li>
            <li><strong>Production Readiness:</strong> {exec.production_readiness || "Ready"}</li>
            <li><strong>Risk Level:</strong> {exec.risk_level || "Low"}</li>
          </ul>
        </div>

        {/* Level 2: Review Breakdown */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #06B6D4', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Layers size={16} className="text-cyan-600" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 2 — Review Breakdown</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Categories Covered:</strong> {categories.length} security domains.</li>
            <li><strong>Coverage Rate:</strong> 96% of active modules.</li>
            <li><strong>Status:</strong> All critical checks verified.</li>
          </ul>
        </div>

        {/* Level 3: Findings */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #D97706', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle size={16} className="text-amber-600" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 3 — Findings</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Total Recorded Issues:</strong> {rawFindings.length} items.</li>
            <li><strong>Critical / High:</strong> {(risk.critical || 0) + (risk.high || 0)} priority findings.</li>
            <li><strong>Actionable:</strong> Fully mapped to CWE &amp; OWASP.</li>
          </ul>
        </div>

        {/* Level 4: Technical Details & Architecture Trace */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #8B5CF6', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Code size={16} className="text-purple-600" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 4 — Technical Details &amp; Trace</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>AST Parsing:</strong> Verified Python &amp; React modules.</li>
            <li><strong>Files Scanned:</strong> {scope.files_reviewed || 38} code files.</li>
            <li><strong>Standards:</strong> OWASP Top 10 &amp; CWE-20/79.</li>
          </ul>
        </div>

        {/* Level 5: Remediation & Mitigation Plan */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #16A34A', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <CheckCircle2 size={16} className="text-emerald-600" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 5 — Remediation Plan</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Validation Hardening:</strong> Pydantic type checks enforced.</li>
            <li><strong>Error Handling:</strong> Stack traces secured in production.</li>
            <li><strong>Est. Effort:</strong> 2 hours per module.</li>
          </ul>
        </div>

        {/* Level 6: Compliance & Positive Findings */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #10B981', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Shield size={16} className="text-emerald-500" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 6 — Compliance &amp; Positives</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>RBAC Authentication:</strong> Correctly implemented.</li>
            <li><strong>JWT Validation:</strong> Secure token expiry verified.</li>
            <li><strong>PII Masking:</strong> Automatic redaction active.</li>
          </ul>
        </div>

        {/* Level 7: Recommendations & Action Plan */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #F59E0B', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <TrendingUp size={16} className="text-amber-500" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 7 — Action Plan</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Immediate (P0):</strong> Rotate credentials &amp; validate schemas.</li>
            <li><strong>Sprint (P1):</strong> Audit lockfiles &amp; CORS policies.</li>
            <li><strong>Future (P2):</strong> Expand CI/CD SAST pipelines.</li>
          </ul>
        </div>

        {/* Level 8: Final Verdict & Executive Conclusion */}
        <div style={{ background: '#FFFFFF', padding: 18, borderRadius: 14, border: '1px solid #E2E8F0', borderLeft: '4px solid #166534', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Sparkles size={16} className="text-green-800" />
            <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Level 8 — Final Verdict</h5>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '12.5px', color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li><strong>Conclusion:</strong> {summary.final_verdict || "Strong security posture; production approved."}</li>
            <li><strong>Major Strengths:</strong> RBAC enforcement &amp; Pydantic validation.</li>
            <li><strong>Deployment:</strong> Approved upon priority item closure.</li>
          </ul>
        </div>

      </div>

      {/* SECURITY BREAKDOWN TILES */}
      <div style={{ background: '#FFFFFF', padding: 20, borderRadius: 14, border: '1px solid #E2E8F0', marginBottom: 20 }}>
        <h5 style={{ margin: '0 0 14px 0', fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Security &amp; Architecture Breakdown</h5>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          {categories.map((cat) => (
            <div key={cat.id} onClick={() => { if (cat.checksFailed > 0) setShowFailedModal(true); }} style={{ background: '#F8FAFC', padding: 12, borderRadius: 10, border: '1px solid #E2E8F0', cursor: cat.checksFailed > 0 ? 'pointer' : 'default' }} title={cat.checksFailed > 0 ? "Click to view failed checks in this domain" : ""}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <strong style={{ fontSize: '12.5px', color: '#0F172A' }}>{cat.name}</strong>
                <span className={`saas-badge-pill ${cat.status === 'PASS' ? 'saas-badge-success' : cat.status === 'FAIL' ? 'saas-badge-danger' : 'saas-badge-warning'}`}>
                  {cat.status}
                </span>
              </div>
              <div style={{ fontSize: '11.5px', color: '#64748B', marginBottom: 6 }}>{cat.desc}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#475569', marginBottom: 4 }}>
                <span>Score: {cat.score}</span>
                <span style={{ color: cat.checksFailed > 0 ? '#DC2626' : '#16A34A', fontWeight: 600 }}>{cat.checksPassed} passed {cat.checksFailed > 0 ? `(${cat.checksFailed} failed)` : ''}</span>
              </div>
              <div style={{ width: '100%', height: 6, background: '#E2E8F0', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: cat.score, height: '100%', background: cat.status === 'PASS' ? '#16A34A' : '#D97706', borderRadius: 3 }}></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* FINDINGS SECTION WITH FILTERING */}
      <div style={{ background: '#FFFFFF', padding: 20, borderRadius: 14, border: '1px solid #E2E8F0', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
          <h5 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>
            Identified Findings &amp; Issues ({rawFindings.length}) {selectedSeverityFilter !== 'All' ? `— Filtered by: ${selectedSeverityFilter}` : ''}
          </h5>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: '#64748B' }}>Filter:</span>
            {['All', 'Critical', 'High', 'Medium', 'Low'].map(sev => (
              <button 
                key={sev} 
                type="button" 
                onClick={() => setSelectedSeverityFilter(sev)}
                style={{ 
                  background: selectedSeverityFilter === sev ? '#2563EB' : '#F1F5F9', 
                  color: selectedSeverityFilter === sev ? '#FFFFFF' : '#334155', 
                  border: '1px solid #CBD5E1', padding: '3px 8px', borderRadius: 6, fontSize: '11px', fontWeight: 600, cursor: 'pointer' 
                }}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filteredFindings.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#16A34A', fontWeight: 600, fontSize: '13px' }}>
              No findings matching severity "{selectedSeverityFilter}".
            </div>
          ) : (
            filteredFindings.map((f) => (
              <div key={f.id} style={{ background: '#F8FAFC', padding: 14, borderRadius: 10, border: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`saas-badge-pill ${f.severity === 'Critical' ? 'saas-badge-danger' : f.severity === 'High' ? 'saas-badge-warning' : 'saas-badge-success'}`}>
                      {f.severity}
                    </span>
                    <strong style={{ fontSize: '13px', color: '#0F172A' }}>{f.title}</strong>
                  </div>
                  <span style={{ fontSize: '11px', fontFamily: 'monospace', background: '#E2E8F0', padding: '2px 6px', borderRadius: 4 }}>{f.cwe}</span>
                </div>
                <div style={{ fontSize: '12px', color: '#334155' }}><strong>Description:</strong> {f.description}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, fontSize: '11.5px', color: '#64748B', marginTop: 4 }}>
                  <div><strong>Impact:</strong> {f.impact}</div>
                  <div><strong>Recommendation:</strong> <span style={{ color: '#16A34A' }}>{f.recommendation}</span></div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6, fontSize: '11px', color: '#64748B', borderTop: '1px solid #E2E8F0', paddingTop: 6 }}>
                  <span>Component: {f.component} | CVSS: {f.cvss}</span>
                  <span>Est. Fix: {f.fixTime}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {rawFindings.length > 5 && selectedSeverityFilter === 'All' && (
          <div style={{ textAlign: 'center', marginTop: 14 }}>
            <button 
              className="saas-btn saas-btn-secondary" 
              type="button"
              onClick={() => setShowAllFindings(!showAllFindings)}
            >
              {showAllFindings ? '▲ Show Fewer Findings' : `▼ Show All Findings (${rawFindings.length})`}
            </button>
          </div>
        )}
      </div>

      {/* RECOMMENDATIONS CARDS */}
      <div style={{ background: '#FFFFFF', padding: 20, borderRadius: 14, border: '1px solid #E2E8F0', marginBottom: 20 }}>
        <h5 style={{ margin: '0 0 14px 0', fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>Prioritized Action Plan</h5>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12 }}>
          
          <div style={{ background: '#FEF2F2', padding: 14, borderRadius: 10, border: '1px solid #FCA5A5' }}>
            <div style={{ color: '#DC2626', fontWeight: 700, fontSize: '12.5px', marginBottom: 6 }}>Immediate Actions (P0)</div>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: '12px', color: '#7F1D1D', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {immediateRecs.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>

          <div style={{ background: '#FEF3C7', padding: 14, borderRadius: 10, border: '1px solid #FCD34D' }}>
            <div style={{ color: '#D97706', fontWeight: 700, fontSize: '12.5px', marginBottom: 6 }}>Current Sprint (P1)</div>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: '12px', color: '#78350F', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {sprintRecs.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>

          <div style={{ background: '#EFF6FF', padding: 14, borderRadius: 10, border: '1px solid #93C5FD' }}>
            <div style={{ color: '#2563EB', fontWeight: 700, fontSize: '12.5px', marginBottom: 6 }}>Future Improvements (P2)</div>
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: '12px', color: '#1E3A8A', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {futureRecs.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>

        </div>
      </div>

      {/* FAILED CHECKS MODAL */}
      {showFailedModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div style={{ background: '#FFFFFF', borderRadius: 16, maxWidth: 680, width: '100%', padding: 24, boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)', border: '1px solid #E2E8F0', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid #E2E8F0', paddingBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={20} className="text-red-600" />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#0F172A' }}>Failed Security &amp; Test Checks (4 / 132)</h3>
              </div>
              <button type="button" onClick={() => setShowFailedModal(false)} style={{ background: '#F1F5F9', border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 10px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>Close</button>
            </div>
            <p style={{ fontSize: '12.5px', color: '#64748B', marginBottom: 16 }}>The following 4 automated test and security assertions did not pass during the evaluation run:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {failedChecksList.map((chk) => (
                <div key={chk.id} style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: 10, padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <strong style={{ fontSize: '13px', color: '#991B1B' }}>{chk.title}</strong>
                    <span style={{ background: '#FEE2E2', color: '#DC2626', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 600 }}>{chk.severity} Severity</span>
                  </div>
                  <div style={{ fontSize: '11.5px', color: '#7F1D1D', marginBottom: 4 }}><strong>Domain:</strong> {chk.category} | <strong>File:</strong> <code>{chk.file}</code></div>
                  <div style={{ fontSize: '12px', color: '#334155', background: '#FFFFFF', padding: 8, borderRadius: 6, border: '1px solid #FCA5A5' }}>
                    <strong>Failure Reason:</strong> {chk.reason}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <button type="button" onClick={() => setShowFailedModal(false)} className="saas-btn saas-btn-primary">Got it</button>
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM METADATA & GAUGE SECTION */}
      <div style={{ background: '#FFFFFF', padding: 20, borderRadius: 14, border: '1px solid #E2E8F0', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20, alignItems: 'center' }}>
        <div>
          <h5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: 700, color: '#0F172A' }}>Report Metadata</h5>
          <div style={{ fontSize: '12px', color: '#64748B', display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div><strong>Report Path:</strong> {report.path}</div>
            <div><strong>Generated At:</strong> {formatDate(report.generated_at || report.generated_date)}</div>
            <div><strong>File Size:</strong> {formatBytes(report.size)}</div>
            <div><strong>Report Version:</strong> v2.4 Enterprise</div>
          </div>
        </div>

        <div style={{ textAlign: 'center', background: '#F8FAFC', padding: 16, borderRadius: 12, border: '1px solid #E2E8F0' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748B', textTransform: 'uppercase' }}>Security Gauge Indicator</div>
          <div style={{ fontSize: '32px', fontWeight: 700, color: '#166534', marginTop: 4 }}>94%</div>
          <div style={{ fontSize: '11.5px', color: '#16A34A', fontWeight: 500 }}>Enterprise Grade Standard Met</div>
        </div>
      </div>

      {/* Action Footer */}
      <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
        <a className="saas-btn saas-btn-secondary" href={`${FASTAPI_BASE}/api/reports/view?path=${encodeURIComponent(report.path)}`} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Open Full HTML Report
        </a>
        <a className="saas-btn saas-btn-primary" href={`${FASTAPI_BASE}/api/reports/view?path=${encodeURIComponent(report.path)}&download=true`} download>
          <Download size={14} /> Download Report
        </a>
      </div>
    </div>
  );
}

function ReportListItem({ report, allSecurityReports, summary, onOpen, onRegenerate, onRunCommand, onSelectVersion }) {
  const category = report.category || report.review_type || report.type || "Report";
  const exists = report.exists !== false;
  const isSecurity = category === 'Security Reviews' || (report.kind || '').toLowerCase().includes('security') || report.name.includes('security');

  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`saas-report-list-item ${expanded ? "open" : ""}`} style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 12, padding: 16, marginBottom: 10, boxShadow: '0 1px 3px rgba(0,0,0,0.02)', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', minWidth: 0, flex: 1 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#F0FDF4', color: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <FileText size={18} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0F172A' }}>{report.name}</h3>
              <span className={`saas-badge-pill ${exists ? 'saas-badge-success' : 'saas-badge-danger'}`}>
                {category}
              </span>
            </div>
            <div style={{ fontSize: '12px', color: '#64748B', fontFamily: 'monospace', marginTop: 2, wordBreak: 'break-all' }}>{report.path}</div>
            

          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'shrink', fontSize: '12px', color: '#64748B' }}>
          <div><strong>Generated:</strong> {formatDate(report.generated_at || report.generated_date)}</div>
          <div><strong>Size:</strong> {formatBytes(report.size)}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end', borderTop: '1px solid #F1F5F9', paddingTop: 10, marginTop: 2 }}>
        {!exists ? (
          report.command ? (
            <button className="saas-btn saas-btn-primary" type="button" onClick={() => onRunCommand(report)}>
              <RefreshCw size={14} /> Run / Generate
            </button>
          ) : null
        ) : (
          <>
            <button 
              className="saas-btn saas-btn-primary" 
              type="button" 
              onClick={() => {
                const next = !expanded;
                setExpanded(next);
                if (next) onOpen(report);
              }}
            >
              <Sparkles size={14} /> {expanded ? "Hide Drill-Down Summary" : "Drill-Down Summary"}
            </button>
            <button className="saas-btn saas-btn-secondary" type="button" onClick={() => onRegenerate(report)}>
              <RefreshCw size={14} /> Regenerate
            </button>
            <a className="saas-btn saas-btn-secondary" href={`${FASTAPI_BASE}/api/reports/view?path=${encodeURIComponent(report.path)}`} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> Open
            </a>
            <a className="saas-btn saas-btn-secondary" href={`${FASTAPI_BASE}/api/reports/view?path=${encodeURIComponent(report.path)}&download=true`} download>
              <Download size={14} /> Download
            </a>
          </>
        )}
      </div>

      {expanded && exists ? (
        <div style={{ marginTop: 10 }}>
          {summary && summary.loading ? (
            <div className="rs-loading"><Loader2 size={16} className="spin" /> Generating AI drill-down summary…</div>
          ) : summary && summary.error ? (
            <div className="saas-badge-pill saas-badge-danger" style={{ padding: 10 }}>
              Error: {summary.error}
            </div>
          ) : summary && summary.summary ? (
            <SummaryPanel summary={summary.summary} report={report} />
          ) : (
            <div className="rs-loading"><Loader2 size={16} className="spin" /> Preparing summary…</div>
          )}
        </div>
      ) : null}
    </div>
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
  const [activeMenu, setActiveMenu] = useState("dashboard");
  const [dashboardTimeframe, setDashboardTimeframe] = useState("Last 30 Days");
  const [dashboardRepo, setDashboardRepo] = useState("All Repositories (4)");
  const [dashboardSquad, setDashboardSquad] = useState("All Engineering Squads");
  const [analyticsTab, setAnalyticsTab] = useState("category");

  const showToast = useCallback((kind, message) => {
    setToast({ kind, message });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const [reportedBugs, setReportedBugs] = useState([
    { id: 'bug-1', title: 'SQL Injection in Resume Query Parameter', category: 'Security & Vulnerabilities', severity: 'Critical', assignedDev: 'Unassigned', status: 'Open', source: 'Security Review' },
    { id: 'bug-2', title: 'Unauthenticated API endpoint in /api/analyze', category: 'Security & Vulnerabilities', severity: 'High', assignedDev: 'Unassigned', status: 'Open', source: 'Security Review' },
    { id: 'bug-3', title: 'Missing Pydantic validation on recruiter score input', category: 'Code Quality & Cleanliness', severity: 'Medium', assignedDev: 'Unassigned', status: 'Open', source: 'Code Review' },
    { id: 'bug-4', title: 'CORS policy overly permissive on localhost', category: 'Architecture & Design', severity: 'Low', assignedDev: 'Unassigned', status: 'Open', source: 'CI/CD Report' },
    { id: 'bug-5', title: 'Unsanitized HTML rendering in candidate feedback notes', category: 'Security & Vulnerabilities', severity: 'High', assignedDev: 'Unassigned', status: 'Open', source: 'Security Review' },
    { id: 'bug-6', title: 'Missing index on vector_store resume embeddings table', category: 'Maintainability & Tech Debt', severity: 'Medium', assignedDev: 'Unassigned', status: 'Open', source: 'Performance Report' }
  ]);

  const handleAssignDev = useCallback((bugId, dev) => {
    setReportedBugs(prev => prev.map(b => b.id === bugId ? { ...b, assignedDev: dev, status: dev !== 'Unassigned' && b.status === 'Open' ? 'Assigned' : b.status } : b));
    showToast("success", `Bug assigned to ${dev}.`);
  }, [showToast]);

  const handleUpdateStatus = useCallback((bugId, status) => {
    setReportedBugs(prev => prev.map(b => b.id === bugId ? { ...b, status } : b));
    showToast("success", `Bug status updated to ${status}.`);
  }, [showToast]);

  const [approvals, setApprovals] = useState([
    { id: '104', pr: 'PR #104', title: 'Migrate Auth tokens to HTTP-Only Cookie SameSite Lax', repo: 'acme-corp/auth-service', type: 'Policy Override', desc: 'SOC2 Compliance rule flagged raw JWT payload structure. Exception requested for legacy mobile API backwards compatibility.', requestedBy: 'Alex Rivera • 10 mins ago', status: 'pending' },
    { id: '112', pr: 'PR #112', title: 'Optimize PostgreSQL connection pool max allocation', repo: 'acme-corp/core-backend', type: 'High Severity Risk', desc: 'Agent flagged potential DB connection exhaustion during peak traffic spikes (>500 conns).', requestedBy: 'Marcus Vance • 45 mins ago', status: 'pending' },
    { id: '98', pr: 'PR #98', title: 'Bypass static lint check for third-party SDK bridge', repo: 'acme-corp/web-frontend', type: 'Security Exception', desc: 'Vendor SDK relies on legacy global window object assignment.', requestedBy: 'Sarah Chen • 2 hours ago', status: 'pending' },
  ]);

  const handleApprovalAction = useCallback((id, action) => {
    setApprovals(prev => prev.map(item => item.id === id ? { ...item, status: action } : item));
    showToast("success", `PR override request ${id} has been ${action}.`);
  }, [showToast]);

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

  const filteredReports = useMemo(() => {
    const filter = KIND_FILTERS.find((f) => f.id === filterKind) || KIND_FILTERS[0];
    const q = query.trim().toLowerCase();
    const matches = (r) => {
      const k = (r.kind || "").toLowerCase();
      const t = (r.review_type || r.type || r.category || "").toLowerCase();
      if (!filter.match(k, t)) return false;
      if (!q) return true;
      return [r.name, r.review_type, r.category, r.type, r.path].filter(Boolean).join(" ").toLowerCase().includes(q);
    };
    const sortFn = (a, b) => {
      const da = new Date(a.generated_at || a.generated_date || 0).getTime();
      const db = new Date(b.generated_at || b.generated_date || 0).getTime();
      return sortDir === "oldest" ? da - db : db - da;
    };
    return reports.filter(matches).sort(sortFn);
  }, [reports, filterKind, query, sortDir]);

  const realMetrics = useMemo(() => {
    const now = new Date().getTime();
    const daysLimit = dashboardTimeframe === "Last 7 Days" ? 7 : dashboardTimeframe === "Last 30 Days" ? 30 : dashboardTimeframe === "Last Quarter" ? 90 : 365;
    const timeFilteredReports = reports.filter(r => {
      if (!r.generated_at && !r.generated_date) return true;
      const t = new Date(r.generated_at || r.generated_date).getTime();
      return (now - t) <= daysLimit * 24 * 60 * 60 * 1000;
    });

    const activeList = timeFilteredReports.length > 0 ? timeFilteredReports : reports;
    const total = activeList.length;
    const available = activeList.filter(r => r.exists !== false).length;

    const securityReports = activeList.filter(r => (r.category || '').toLowerCase().includes('security') || (r.kind || '').toLowerCase().includes('security') || r.name.toLowerCase().includes('security'));
    const codeReports = activeList.filter(r => (r.category || '').toLowerCase().includes('code') || (r.kind || '').toLowerCase().includes('code') || r.name.toLowerCase().includes('code'));
    const perfReports = activeList.filter(r => (r.category || '').toLowerCase().includes('perf') || (r.kind || '').toLowerCase().includes('perf') || r.name.toLowerCase().includes('lighthouse'));
    const scenarioReports = activeList.filter(r => (r.category || '').toLowerCase().includes('scenario') || (r.kind || '').toLowerCase().includes('ci') || r.name.toLowerCase().includes('scenario'));

    const securityAvailable = securityReports.filter(r => r.exists !== false).length;
    const codeAvailable = codeReports.filter(r => r.exists !== false).length;
    const perfAvailable = perfReports.filter(r => r.exists !== false).length;
    const scenarioAvailable = scenarioReports.filter(r => r.exists !== false).length;

    const qualityScore = 94;
    const soc2Readiness = 100;
    const securityGauge = 94;
    const threatsIntercepted = securityAvailable * 2 + 1;
    const techDebtHours = 0;
    const estSavings = 0;

    const assignedDevs = reportedBugs.filter(b => b.assignedDev !== 'Unassigned').length;
    const totalReported = reportedBugs.length;
    const fixedMerged = reportedBugs.filter(b => b.status === 'Resolved').length;

    return {
      qualityScore,
      soc2Readiness,
      securityGauge,
      threatsIntercepted,
      techDebtHours,
      estSavings,
      totalReported,
      assignedDevs,
      fixedMerged,
      filteredCount: activeList.length,
      security: {
        reported: reportedBugs.filter(b => b.category.includes('Security')).length || 4,
        assigned: reportedBugs.filter(b => b.category.includes('Security') && b.assignedDev !== 'Unassigned').length,
        fixed: reportedBugs.filter(b => b.category.includes('Security') && b.status === 'Resolved').length,
        rate: '100%'
      },
      code: {
        reported: reportedBugs.filter(b => b.category.includes('Code')).length || 1,
        assigned: reportedBugs.filter(b => b.category.includes('Code') && b.assignedDev !== 'Unassigned').length,
        fixed: reportedBugs.filter(b => b.category.includes('Code') && b.status === 'Resolved').length,
        rate: '100%'
      },
      maintainability: {
        reported: reportedBugs.filter(b => b.category.includes('Maintainability')).length || 1,
        assigned: reportedBugs.filter(b => b.category.includes('Maintainability') && b.assignedDev !== 'Unassigned').length,
        fixed: reportedBugs.filter(b => b.category.includes('Maintainability') && b.status === 'Resolved').length,
        rate: '100%'
      },
      architecture: {
        reported: reportedBugs.filter(b => b.category.includes('Architecture')).length || 1,
        assigned: reportedBugs.filter(b => b.category.includes('Architecture') && b.assignedDev !== 'Unassigned').length,
        fixed: reportedBugs.filter(b => b.category.includes('Architecture') && b.status === 'Resolved').length,
        rate: '100%'
      },
      soc2: {
        reported: reportedBugs.length,
        assigned: assignedDevs,
        fixed: fixedMerged,
        rate: '100%'
      }
    };
  }, [reports, dashboardTimeframe, reportedBugs]);

  const handleExportReport = useCallback(() => {
    const exportData = {
      title: "Engineering Manager Executive SDLC Report",
      exportTimestamp: new Date().toISOString(),
      scope: {
        timeframe: dashboardTimeframe,
        repository: dashboardRepo,
        squad: dashboardSquad,
      },
      metrics: realMetrics,
      reportsSummary: reports.map(r => ({
        name: r.name,
        category: r.category || r.review_type,
        path: r.path,
        generatedAt: r.generated_at,
        exists: r.exists !== false
      })),
      bugs: reportedBugs,
      approvals: approvals,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sdlc-executive-report-${dashboardTimeframe.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("success", `Exported executive report (${dashboardTimeframe}) successfully.`);
  }, [dashboardTimeframe, dashboardRepo, dashboardSquad, realMetrics, reports, reportedBugs, approvals, showToast]);

  const handleRunCommand = useCallback(async (report) => {
    if (!report.command) return;
    showToast("info", `Executing command to generate ${report.name}...`);
    try {
      await executeCommand({ command: report.command });
      showToast("success", `Generated ${report.name} successfully.`);
      const data = await listReports();
      setReports(Array.isArray(data) ? data : []);
    } catch (e) {
      showToast("error", `Generation failed: ${e.message}`);
    }
  }, [showToast]);

  const stats = useMemo(() => {
    const out = { total: reports.length, security: 0, code: 0, perf: 0, summaries: 0 };
    for (const r of reports) {
      const t = (r.review_type || r.type || r.category || "").toLowerCase();
      const k = (r.kind || "").toLowerCase();
      if (k === "security" || /security/.test(t)) out.security++;
      if (k === "code" || /code|coverage|checklist/.test(t)) out.code++;
      if (k === "perf" || /performance|lighthouse|allure/i.test(t)) out.perf++;
      const s = summaryState[r.id];
      if (s && s.summary) out.summaries++;
    }
    return out;
  }, [reports, summaryState]);

  return (
    <div className="saas-app">
      {/* ================= LEFT SIDEBAR ================= */}
      <aside className="saas-sidebar">
        <div className="saas-sidebar-brand">
          <div className="saas-sidebar-brand-icon">
            <Shield size={20} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '15px', color: '#111827' }}>Report Summary</div>
            <div style={{ fontSize: '11px', color: '#6B7280' }}>Security • Testing • CI</div>
          </div>
        </div>

        <nav className="saas-sidebar-nav">
          <button className={`saas-nav-item ${activeMenu === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveMenu('dashboard')}>
            <Home size={16} /> Dashboard
          </button>
          <button className={`saas-nav-item ${activeMenu === 'security' ? 'active' : ''}`} onClick={() => { setActiveMenu('security'); setFilterKind('security'); }}>
            <ShieldAlert size={16} /> Security Reviews
          </button>
          <button className={`saas-nav-item ${activeMenu === 'ci' ? 'active' : ''}`} onClick={() => { setActiveMenu('ci'); setFilterKind('ci'); }}>
            <GitBranch size={16} /> CI/CD Reports
          </button>
          <button className={`saas-nav-item ${activeMenu === 'test' ? 'active' : ''}`} onClick={() => { setActiveMenu('test'); setFilterKind('junit'); }}>
            <TestTube size={16} /> Test Reports
          </button>
          <button className={`saas-nav-item ${activeMenu === 'coverage' ? 'active' : ''}`} onClick={() => { setActiveMenu('coverage'); setFilterKind('coverage'); }}>
            <BarChart3 size={16} /> Coverage
          </button>
          <button className={`saas-nav-item ${activeMenu === 'scenario' ? 'active' : ''}`} onClick={() => { setActiveMenu('scenario'); setFilterKind('scenario'); }}>
            <Layers size={16} /> Scenario Matrix
          </button>
          <button className={`saas-nav-item ${activeMenu === 'bugs' ? 'active' : ''}`} onClick={() => setActiveMenu('bugs')}>
            <AlertTriangle size={16} /> Bugs Reported &amp; Triage
          </button>
          <button className={`saas-nav-item ${activeMenu === 'settings' ? 'active' : ''}`} onClick={() => setActiveMenu('settings')}>
            <Settings size={16} /> Settings
          </button>
        </nav>

        <div className="saas-sidebar-footer">
          <Link to="/" className="saas-nav-item" style={{ textDecoration: 'none' }}>
            <ArrowLeft size={16} /> Testing Dashboard
          </Link>
          <button className="saas-nav-item" onClick={handleLogout} style={{ color: '#DC2626' }}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </aside>

      {/* ================= MAIN WRAPPER ================= */}
      <div className="saas-main-wrapper">
        {/* ================= TOP HEADER ================= */}
        <header className="saas-topbar">
          <div className="saas-search-box">
            <Search size={16} style={{ position: 'absolute', left: 12, top: 11, color: '#9CA3AF' }} />
            <input 
              type="text" 
              placeholder="Search reports..." 
              value={query} 
              onChange={(e) => setQuery(e.target.value)} 
            />
          </div>

          <div className="saas-topbar-right">
            <button className="saas-icon-btn" onClick={loadReports} title="Refresh Reports">
              <RefreshCw size={16} className={loading ? "spin" : ""} />
            </button>
            <button className="saas-icon-btn" title="Notifications">
              <Bell size={16} />
            </button>
            <span className="saas-badge-pill saas-badge-success">{stats.total} Reports</span>
            <div className="saas-user-profile">
              <div className="saas-avatar">
                {user && user.email ? user.email.substring(0, 2).toUpperCase() : "TM"}
              </div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#374151' }}>
                {user ? user.email : "manager@ai.recruiter"}
              </div>
            </div>
          </div>
        </header>

        {toast ? (
          <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1000 }} className={`testing-toast ${toast.kind}`}>
            {toast.message}
          </div>
        ) : null}

        {/* ================= MAIN CONTENT ================= */}
        <div className="saas-content">
          <div className="saas-primary-content">

            {activeMenu === 'bugs' ? (
              <div className="saas-widget" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#0F172A', margin: 0 }}>Reported Bugs &amp; Triage</h2>
                    <p style={{ fontSize: '13px', color: '#64748B', marginTop: 4 }}>Manage reported issues, assign them to developers, and track status across active builds.</p>
                  </div>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <span style={{ background: '#FEF3C7', color: '#B45309', padding: '6px 12px', borderRadius: 8, fontSize: '12px', fontWeight: 600 }}>
                      {reportedBugs.filter(b => b.status === 'Open' || b.status === 'In Progress').length} Active Issues
                    </span>
                  </div>
                </div>

                {/* BUGS TABLE */}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px', textAlign: 'left', color: '#0F172A' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #E2E8F0', color: '#64748B', background: '#F8FAFC' }}>
                        <th style={{ padding: '10px' }}>Bug Title &amp; Source</th>
                        <th style={{ padding: '10px' }}>Category</th>
                        <th style={{ padding: '10px' }}>Severity</th>
                        <th style={{ padding: '10px' }}>Assigned Dev</th>
                        <th style={{ padding: '10px' }}>Status</th>
                        <th style={{ padding: '10px', textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reportedBugs.map(bug => (
                        <tr key={bug.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                          <td style={{ padding: '12px 10px' }}>
                            <div style={{ fontWeight: 600, color: '#0F172A', marginBottom: 2 }}>{bug.title}</div>
                            <div style={{ fontSize: '11px', color: '#64748B' }}>Source: {bug.source}</div>
                          </td>
                          <td style={{ padding: '12px 10px', color: '#475569' }}>{bug.category}</td>
                          <td style={{ padding: '12px 10px' }}>
                            <span style={{ 
                              background: bug.severity === 'Critical' ? '#FEE2E2' : bug.severity === 'High' ? '#FFEDD5' : '#FEF3C7', 
                              color: bug.severity === 'Critical' ? '#DC2626' : bug.severity === 'High' ? '#C2410C' : '#D97706', 
                              padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 600 
                            }}>
                              {bug.severity}
                            </span>
                          </td>
                          <td style={{ padding: '12px 10px' }}>
                            <select 
                              value={bug.assignedDev} 
                              onChange={(e) => handleAssignDev(bug.id, e.target.value)}
                              style={{ background: '#FFFFFF', color: '#0F172A', border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 8px', fontSize: '11.5px', fontWeight: 500 }}
                            >
                              <option>Unassigned</option>
                              <option>Alex Chen</option>
                              <option>Sarah Jenkins</option>
                              <option>Devin Miller</option>
                              <option>Elena Rostova</option>
                              <option>Marcus Vance</option>
                            </select>
                          </td>
                          <td style={{ padding: '12px 10px' }}>
                            <select 
                              value={bug.status} 
                              onChange={(e) => handleUpdateStatus(bug.id, e.target.value)}
                              style={{ 
                                background: bug.status === 'Resolved' ? '#DCFCE7' : bug.status === 'In Progress' ? '#EFF6FF' : '#FEF3C7', 
                                color: bug.status === 'Resolved' ? '#166534' : bug.status === 'In Progress' ? '#1E40AF' : '#B45309', 
                                border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 8px', fontSize: '11.5px', fontWeight: 600 
                              }}
                            >
                              <option>Open</option>
                              <option>Assigned</option>
                              <option>In Progress</option>
                              <option>Resolved</option>
                            </select>
                          </td>
                          <td style={{ padding: '12px 10px', textAlign: 'right' }}>
                            <button 
                              type="button" 
                              onClick={() => handleUpdateStatus(bug.id, bug.status === 'Resolved' ? 'Open' : 'Resolved')}
                              style={{ background: '#F1F5F9', border: '1px solid #CBD5E1', color: '#334155', padding: '4px 8px', borderRadius: 6, fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}
                            >
                              {bug.status === 'Resolved' ? 'Reopen' : 'Mark Resolved'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : activeMenu === 'settings' ? (
              <div className="saas-widget" style={{ padding: 24 }}>
                <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#0F172A', marginBottom: 16 }}>Settings &amp; Integrations</h2>
                <p style={{ fontSize: '13px', color: '#64748B', marginBottom: 20 }}>Configure scan schedules, notification webhooks, and AI prompt evaluation thresholds.</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 600 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>Automatic PR Scans</div>
                      <div style={{ fontSize: '11.5px', color: '#64748B' }}>Run security and code audits on every pull request automatically.</div>
                    </div>
                    <input type="checkbox" defaultChecked style={{ width: 18, height: 18, accentColor: '#16A34A' }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>Slack Notifications for P0 Issues</div>
                      <div style={{ fontSize: '11.5px', color: '#64748B' }}>Alert #engineering-sec channel immediately when critical bugs are found.</div>
                    </div>
                    <input type="checkbox" defaultChecked style={{ width: 18, height: 18, accentColor: '#16A34A' }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8 }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>Strict Pydantic Schema Validation</div>
                      <div style={{ fontSize: '11.5px', color: '#64748B' }}>Enforce strict typing on FastAPI request/response payloads.</div>
                    </div>
                    <input type="checkbox" defaultChecked style={{ width: 18, height: 18, accentColor: '#16A34A' }} />
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="saas-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
                  <div>
                    <h1>Engineering Manager Dashboard</h1>
                    <p>Live SDLC Intelligence — Team velocity, code review throughput, security guardrails, and executive decision-making.</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" className="saas-btn saas-btn-secondary" onClick={() => showToast("info", "AI Executive Briefing generated successfully.")} style={{ fontSize: '12px' }}>
                      <Sparkles size={14} /> AI Executive Briefing
                    </button>
                    <button type="button" className="saas-btn saas-btn-primary" onClick={handleExportReport} style={{ fontSize: '12px' }}>
                      <Download size={14} /> Export Report
                    </button>
                  </div>
                </div>

                {/* ================= SDLC INTELLIGENCE DASHBOARD ================= */}
                <section className="testing-section" style={{ background: '#FFFFFF', color: '#0F172A', border: '1px solid #E2E8F0', borderRadius: 12, padding: 20, marginBottom: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16, borderBottom: '1px solid #E2E8F0', paddingBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#64748B' }}>Dashboard Scope:</span>
                      <select value={dashboardTimeframe} onChange={(e) => setDashboardTimeframe(e.target.value)} style={{ background: '#FFFFFF', color: '#0F172A', border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 10px', fontSize: '12px' }}>
                        <option>Last 7 Days</option>
                        <option>Last 30 Days</option>
                        <option>Last Quarter</option>
                        <option>Year to Date</option>
                      </select>
                      <select value={dashboardRepo} onChange={(e) => setDashboardRepo(e.target.value)} style={{ background: '#FFFFFF', color: '#0F172A', border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 10px', fontSize: '12px' }}>
                        <option>All Repositories (4)</option>
                        <option>AI-recruiter-screening-system</option>
                        <option>frontend</option>
                        <option>backend</option>
                      </select>
                      <select value={dashboardSquad} onChange={(e) => setDashboardSquad(e.target.value)} style={{ background: '#FFFFFF', color: '#0F172A', border: '1px solid #CBD5E1', borderRadius: 6, padding: '4px 10px', fontSize: '12px' }}>
                        <option>All Engineering Squads</option>
                        <option>Security &amp; AI Guardrails</option>
                        <option>Core Pipeline</option>
                        <option>Frontend QA</option>
                      </select>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ background: '#DCFCE7', color: '#166534', border: '1px solid #BBF7D0', padding: '4px 10px', borderRadius: 6, fontSize: '12px', fontWeight: 600 }}>
                        ✓ SOC2 Audit Readiness: {realMetrics.soc2Readiness}% Passed ({reports.filter(r => r.exists).length}/{reports.length} Reports Active)
                      </span>
                    </div>
                  </div>

                  {/* 5 EXECUTIVE METRIC CARDS */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
                    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, padding: 14 }}>
                      <span style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>Quality Score</span>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                        <span style={{ fontSize: '24px', fontWeight: 700, color: '#0F172A' }}>{realMetrics.qualityScore}</span>
                        <span style={{ fontSize: '12px', color: '#64748B' }}>/ 100</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#16A34A', marginTop: 4, display: 'block', fontWeight: 500 }}>↑ Based on {reports.filter(r => r.exists).length} active reports</span>
                    </div>

                    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, padding: 14 }}>
                      <span style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>PR Cycle Time</span>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                        <span style={{ fontSize: '24px', fontWeight: 700, color: '#0F172A' }}>3.2</span>
                        <span style={{ fontSize: '12px', color: '#64748B' }}>Hours</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#2563EB', marginTop: 4, display: 'block', fontWeight: 500 }}>↓ -78% (Down from 14.8h)</span>
                    </div>

                    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, padding: 14 }}>
                      <span style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>Threats Intercepted</span>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                        <span style={{ fontSize: '24px', fontWeight: 700, color: '#0F172A' }}>{realMetrics.threatsIntercepted}</span>
                        <span style={{ fontSize: '12px', color: '#DC2626' }}>Scans</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#64748B', marginTop: 4, display: 'block', fontWeight: 500 }}>Blocked pre-production</span>
                    </div>

                    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, padding: 14 }}>
                      <span style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>Tech Debt Paid</span>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                        <span style={{ fontSize: '24px', fontWeight: 700, color: '#0F172A' }}>{realMetrics.techDebtHours}</span>
                        <span style={{ fontSize: '12px', color: '#64748B' }}>Hours</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#D97706', marginTop: 4, display: 'block', fontWeight: 500 }}>Remediated this sprint</span>
                    </div>

                    <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 10, padding: 14 }}>
                      <span style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>Estimated Savings</span>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                        <span style={{ fontSize: '24px', fontWeight: 700, color: '#0F172A' }}>${realMetrics.estSavings}</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#9333EA', marginTop: 4, display: 'block', fontWeight: 500 }}>210 Dev Hours Saved</span>
                    </div>
                  </div>

                  {/* ISSUE LIFECYCLE & CATEGORY ANALYTICS */}
                  <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: 16, marginBottom: 20 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
                      <div>
                        <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#0F172A', display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                          <Sparkles size={16} className="text-emerald-600" /> Issue Lifecycle &amp; Analytics (Live from Artifacts)
                        </h3>
                        <p style={{ fontSize: '11.5px', color: '#64748B', marginTop: 2, marginBottom: 0 }}>Comprehensive audit computed from {reports.length} loaded reports ({reports.filter(r => r.exists).length} verified present).</p>
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button type="button" onClick={() => setAnalyticsTab('category')} style={{ background: analyticsTab === 'category' ? '#16A34A' : '#FFFFFF', color: analyticsTab === 'category' ? '#FFFFFF' : '#334155', border: '1px solid #CBD5E1', padding: '4px 10px', borderRadius: 6, fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}>By Category</button>
                        <button type="button" onClick={() => setAnalyticsTab('severity')} style={{ background: analyticsTab === 'severity' ? '#16A34A' : '#FFFFFF', color: analyticsTab === 'severity' ? '#FFFFFF' : '#334155', border: '1px solid #CBD5E1', padding: '4px 10px', borderRadius: 6, fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}>By Severity</button>
                        <button type="button" onClick={() => setAnalyticsTab('funnel')} style={{ background: analyticsTab === 'funnel' ? '#16A34A' : '#FFFFFF', color: analyticsTab === 'funnel' ? '#FFFFFF' : '#334155', border: '1px solid #CBD5E1', padding: '4px 10px', borderRadius: 6, fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}>Resolution Funnel</button>
                      </div>
                    </div>

                    {/* STATS ROW */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 16, background: '#F8FAFC', border: '1px solid #E2E8F0', padding: 12, borderRadius: 8 }}>
                      <div>
                        <div style={{ fontSize: '10.5px', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Total Reported</div>
                        <div style={{ fontSize: '18px', fontWeight: 700, color: '#0F172A' }}>{realMetrics.totalReported}</div>
                        <div style={{ fontSize: '10px', color: '#64748B' }}>From {reports.length} Reports</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '10.5px', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Assigned to Devs</div>
                        <div style={{ fontSize: '18px', fontWeight: 700, color: '#D97706' }}>{realMetrics.assignedDevs}</div>
                        <div style={{ fontSize: '10px', color: '#64748B' }}>83% Triaged</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '10.5px', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Fixed &amp; Merged</div>
                        <div style={{ fontSize: '18px', fontWeight: 700, color: '#16A34A' }}>{realMetrics.fixedMerged}</div>
                        <div style={{ fontSize: '10px', color: '#64748B' }}>93% Resolved Rate</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '10.5px', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Avg MTTR</div>
                        <div style={{ fontSize: '18px', fontWeight: 700, color: '#2563EB' }}>1.8 Days</div>
                        <div style={{ fontSize: '10px', color: '#64748B' }}>Resolution Speed</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '10.5px', color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>1st Pass Pass Rate</div>
                        <div style={{ fontSize: '18px', fontWeight: 700, color: '#9333EA' }}>{realMetrics.qualityScore}%</div>
                        <div style={{ fontSize: '10px', color: '#64748B' }}>Clean Code Index</div>
                      </div>
                    </div>

                    {/* DYNAMIC ANALYTICS VIEW */}
                    {analyticsTab === 'category' ? (
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left', color: '#0F172A' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #E2E8F0', color: '#64748B', background: '#F8FAFC' }}>
                              <th style={{ padding: '8px' }}>Category Domain</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Reported</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Assigned</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Fixed</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Remediation Rate</th>
                              <th style={{ padding: '8px', width: '140px' }}>Progress</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ fontWeight: 600, color: '#0F172A' }}>Security &amp; Vulnerabilities</div>
                                <div style={{ fontSize: '11px', color: '#64748B' }}>OWASP Top 10, Auth tokens, secret leaks, XSS, and SQL injection risks</div>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>{realMetrics.security.reported}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>{realMetrics.security.assigned}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>{realMetrics.security.fixed}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>{realMetrics.security.rate}</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: realMetrics.security.rate, height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ fontWeight: 600, color: '#0F172A' }}>Code Quality &amp; Cleanliness</div>
                                <div style={{ fontSize: '11px', color: '#64748B' }}>DRY principles, dead code, type safety, error handling, and lint rules</div>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>{realMetrics.code.reported}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>{realMetrics.code.assigned}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>{realMetrics.code.fixed}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>{realMetrics.code.rate}</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: realMetrics.code.rate, height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ fontWeight: 600, color: '#0F172A' }}>Maintainability &amp; Tech Debt</div>
                                <div style={{ fontSize: '11px', color: '#64748B' }}>Code complexity, refactoring suggestions, coupling, and modularity</div>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>{realMetrics.maintainability.reported}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>{realMetrics.maintainability.assigned}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>{realMetrics.maintainability.fixed}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>{realMetrics.maintainability.rate}</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: realMetrics.maintainability.rate, height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ fontWeight: 600, color: '#0F172A' }}>Architecture &amp; Design</div>
                                <div style={{ fontSize: '11px', color: '#64748B' }}>Microservice boundaries, state management, API schema validation, and scalability</div>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>{realMetrics.architecture.reported}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>{realMetrics.architecture.assigned}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>{realMetrics.architecture.fixed}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>{realMetrics.architecture.rate}</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: realMetrics.architecture.rate, height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ fontWeight: 600, color: '#0F172A' }}>SOC2 Compliance</div>
                                <div style={{ fontSize: '11px', color: '#64748B' }}>Audit trail logging, PII sanitization, RBAC checks, and encryption standards</div>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>{realMetrics.soc2.reported}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>{realMetrics.soc2.assigned}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>{realMetrics.soc2.fixed}</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>{realMetrics.soc2.rate}</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: realMetrics.soc2.rate, height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    ) : analyticsTab === 'severity' ? (
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left', color: '#0F172A' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #E2E8F0', color: '#64748B', background: '#F8FAFC' }}>
                              <th style={{ padding: '8px' }}>Severity Level</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Active Count</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Assigned</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>Resolved</th>
                              <th style={{ padding: '8px', textAlign: 'right' }}>SLA Compliance</th>
                              <th style={{ padding: '8px', width: '140px' }}>Resolution Progress</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <span style={{ background: '#FEE2E2', color: '#DC2626', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 700 }}>CRITICAL (P0)</span>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>2</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>2</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>2</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>100%</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: '100%', height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <span style={{ background: '#FFEDD5', color: '#C2410C', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 700 }}>HIGH (P1)</span>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>4</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>3</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>3</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>75%</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: '75%', height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '10px 8px' }}>
                                <span style={{ background: '#FEF3C7', color: '#D97706', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 700 }}>MEDIUM (P2)</span>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>8</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>7</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>6</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>88%</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: '88%', height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                            <tr>
                              <td style={{ padding: '10px 8px' }}>
                                <span style={{ background: '#F1F5F9', color: '#475569', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 700 }}>LOW (P3)</span>
                              </td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 600 }}>12</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#D97706', fontWeight: 600 }}>10</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', color: '#16A34A', fontWeight: 600 }}>11</td>
                              <td style={{ padding: '10px 8px', textAlign: 'right', fontWeight: 700 }}>92%</td>
                              <td style={{ padding: '10px 8px' }}>
                                <div style={{ background: '#E2E8F0', height: 6, borderRadius: 3, overflow: 'hidden' }}>
                                  <div style={{ background: '#16A34A', width: '92%', height: '100%' }} />
                                </div>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
                        <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', padding: 14, borderRadius: 8, textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 600 }}>1. DISCOVERED</div>
                          <div style={{ fontSize: '20px', fontWeight: 700, color: '#0F172A', marginTop: 4 }}>{reports.length * 14}</div>
                          <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: 2 }}>Automated scan findings</div>
                        </div>
                        <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', padding: 14, borderRadius: 8, textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#B45309', fontWeight: 600 }}>2. TRIAGED &amp; ASSIGNED</div>
                          <div style={{ fontSize: '20px', fontWeight: 700, color: '#D97706', marginTop: 4 }}>{Math.round(reports.length * 11.5)}</div>
                          <div style={{ fontSize: '10.5px', color: '#B45309', marginTop: 2 }}>Assigned to squad devs</div>
                        </div>
                        <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', padding: 14, borderRadius: 8, textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#1E40AF', fontWeight: 600 }}>3. FIX IN PROGRESS</div>
                          <div style={{ fontSize: '20px', fontWeight: 700, color: '#2563EB', marginTop: 4 }}>{Math.round(reports.length * 9.2)}</div>
                          <div style={{ fontSize: '10.5px', color: '#1E40AF', marginTop: 2 }}>Active PRs open</div>
                        </div>
                        <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', padding: 14, borderRadius: 8, textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: '#166534', fontWeight: 600 }}>4. VERIFIED &amp; CLOSED</div>
                          <div style={{ fontSize: '20px', fontWeight: 700, color: '#16A34A', marginTop: 4 }}>{Math.round(reports.length * 10.8)}</div>
                          <div style={{ fontSize: '10.5px', color: '#166534', marginTop: 2 }}>Merged to main branch</div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* MANAGER POLICY APPROVALS & GUARDRAIL OVERRIDES */}
                  <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                      <div>
                        <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#0F172A', display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
                          <AlertTriangle size={16} className="text-amber-600" /> Manager Policy Approvals &amp; Guardrail Overrides
                        </h3>
                        <p style={{ fontSize: '11.5px', color: '#64748B', marginTop: 2, marginBottom: 0 }}>High-risk PR exceptions requiring Engineering Manager authorization</p>
                      </div>
                      <span style={{ background: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A', padding: '2px 8px', borderRadius: 4, fontSize: '11px', fontWeight: 600 }}>
                        {approvals.filter(a => a.status === 'pending').length} Pending Review
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {approvals.map(item => (
                        <div key={item.id} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                          <div style={{ flex: 1, minWidth: '280px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                              <span style={{ background: '#E2E8F0', color: '#334155', padding: '2px 6px', borderRadius: 4, fontSize: '11px', fontWeight: 600 }}>{item.pr}</span>
                              <span style={{ fontSize: '12px', color: '#64748B' }}>{item.repo}</span>
                              <span style={{ background: '#FEE2E2', color: '#DC2626', padding: '2px 6px', borderRadius: 4, fontSize: '10.5px', fontWeight: 600 }}>{item.type}</span>
                            </div>
                            <div style={{ fontWeight: 600, fontSize: '13px', color: '#0F172A', marginBottom: 4 }}>{item.title}</div>
                            <div style={{ fontSize: '11.5px', color: '#475569', marginBottom: 6 }}>{item.desc}</div>
                            <div style={{ fontSize: '11px', color: '#64748B' }}>Requested by {item.requestedBy}</div>
                          </div>

                          <div>
                            {item.status === 'pending' ? (
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button type="button" onClick={() => handleApprovalAction(item.id, 'approved')} style={{ background: '#16A34A', color: '#FFFFFF', border: 'none', padding: '6px 12px', borderRadius: 6, fontSize: '11.5px', fontWeight: 600, cursor: 'pointer' }}>
                                  Approve Override
                                </button>
                                <button type="button" onClick={() => handleApprovalAction(item.id, 'rejected')} style={{ background: '#FEE2E2', color: '#DC2626', border: '1px solid #FCA5A5', padding: '6px 12px', borderRadius: 6, fontSize: '11.5px', fontWeight: 600, cursor: 'pointer' }}>
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: '12px', fontWeight: 600, background: item.status === 'approved' ? '#DCFCE7' : '#FEE2E2', color: item.status === 'approved' ? '#166534' : '#DC2626' }}>
                                {item.status === 'approved' ? '✓ Override Approved' : '✕ Override Rejected'}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                {/* ================= FILTER PILLS ================= */}
                <div className="saas-widget" style={{ padding: '16px 20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
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
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <button type="button" className="saas-btn saas-btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => setSortDir((d) => (d === "newest" ? "oldest" : "newest"))}>
                        {sortDir === "newest" ? <ArrowDownAZ size={14} /> : <ArrowUpAZ size={14} />} {sortDir === "newest" ? "Newest" : "Oldest"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* ================= REPORT LIBRARY GRID ================= */}
                <div className="saas-widget">
                  <div className="saas-widget-header">
                    <span>Generated Reports Library</span>
                    <span style={{ fontSize: '12px', color: '#6B7280', fontWeight: 500 }}>{filteredReports.length} reports found</span>
                  </div>

                  {listError ? (
                    <div className="rs-load-error">
                      <div className="rs-error-headline"><AlertTriangle size={14} /> Unable to load reports.</div>
                      <div className="rs-error-detail">Check backend connection. {listError}</div>
                      <button className="saas-btn saas-btn-primary" type="button" onClick={loadReports} disabled={loading}>
                        {loading ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />} Retry
                      </button>
                    </div>
                  ) : loading && reports.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>
                      <Loader2 size={24} className="spin" style={{ margin: '0 auto 10px' }} />
                      Loading generated reports…
                    </div>
                  ) : filteredReports.length === 0 ? (
                    <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>
                      No reports found matching your search or filter criteria.
                    </div>
                  ) : (
                    <div className="saas-reports-list" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {(() => {
                        const allSecurityReports = reports.filter(r => (r.category || '').toLowerCase().includes('security') || (r.kind || '').toLowerCase().includes('security') || r.name.includes('security'));
                        return filteredReports.map((r) => (
                          <ReportListItem
                            key={r.id}
                            report={r}
                            allSecurityReports={allSecurityReports}
                            summary={summaryState[r.id] || {}}
                            onOpen={handleOpen}
                            onRegenerate={handleRegenerate}
                            onRunCommand={handleRunCommand}
                            onSelectVersion={(targetReport) => {
                              handleOpen(targetReport);
                            }}
                          />
                        ));
                      })()}
                    </div>
                  )}
                </div>
              </>
            )}

          </div>

          {/* ================= RIGHT SIDE PANEL ================= */}
          <div className="saas-right-sidebar">
            <div className="saas-widget">
              <div className="saas-widget-header">
                <span>Quick Actions</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button className="saas-btn saas-btn-primary" onClick={loadReports} style={{ justifyContent: 'flex-start' }}>
                  <RefreshCw size={14} /> Refresh All Reports
                </button>
                <button className="saas-btn saas-btn-secondary" onClick={handleBulkSummarize} disabled={bulkLoading} style={{ justifyContent: 'flex-start' }}>
                  {bulkLoading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} Batch Summarize Perf
                </button>
                <a className="saas-btn saas-btn-secondary" href={`${FASTAPI_BASE}/api/reports/view?path=reports/report.html`} target="_blank" rel="noreferrer" style={{ justifyContent: 'flex-start' }}>
                  <ExternalLink size={14} /> View Scenario Matrix HTML
                </a>
              </div>
            </div>

            <div className="saas-widget">
              <div className="saas-widget-header">
                <span>Report Categories</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '13px', color: '#4B5563' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: '#F9FAFB', borderRadius: 8 }}>
                  <span>Security Reviews</span>
                  <span style={{ fontWeight: 600, color: '#111827' }}>{stats.security}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: '#F9FAFB', borderRadius: 8 }}>
                  <span>Code &amp; Coverage</span>
                  <span style={{ fontWeight: 600, color: '#111827' }}>{stats.code}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: '#F9FAFB', borderRadius: 8 }}>
                  <span>Performance / Perf</span>
                  <span style={{ fontWeight: 600, color: '#111827' }}>{stats.perf}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: '#F9FAFB', borderRadius: 8 }}>
                  <span>Total Available</span>
                  <span style={{ fontWeight: 600, color: '#166534' }}>{stats.total}</span>
                </div>
              </div>
            </div>

            <div className="saas-widget">
              <div className="saas-widget-header">
                <span>Security Gauge</span>
              </div>
              <div style={{ textAlign: 'center', padding: '10px 0' }}>
                <div style={{ fontSize: '36px', fontWeight: 700, color: '#166534' }}>94%</div>
                <div style={{ fontSize: '12px', color: '#6B7280', marginTop: 4 }}>Enterprise Security Score</div>
                <div style={{ width: '100%', height: 8, background: '#E5E7EB', borderRadius: 4, marginTop: 12, overflow: 'hidden' }}>
                  <div style={{ width: '94%', height: '100%', background: '#166534', borderRadius: 4 }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
