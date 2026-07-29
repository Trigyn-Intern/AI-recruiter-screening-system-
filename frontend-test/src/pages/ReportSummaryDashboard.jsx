import React, { useState, useMemo } from "react";
import {
  FlaskConical,
  LogOut,
  ArrowLeft,
  FileText,
  ShieldCheck,
  Code,
  BarChart2,
  Sparkles,
  Search,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  CheckCircle2,
  Clock,
  Layers,
  ArrowUpDown
} from "lucide-react";
import { clearSession, getStoredUser } from "../api";

// 32 Discovered Reports + 3012 Performance Bucket Items = 3044 Total Reports
const INITIAL_REPORTS = [
  {
    id: "sec-review-2026-07-28",
    title: "Security Review All 2026 07 28",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-28.html",
    generatedAt: "7/28/2026, 2:37:58 PM",
    timestamp: 1785278278000,
    size: "27.7 KB",
    hasSummary: true,
    isCached: true,
    summary: {
      overallAssessment:
        "The report provides a moderate overall security posture with critical issues requiring immediate attention.",
      keyFindings: [
        "Full-project security review covered various languages and file types.",
        "18 items passed, 4 failed, and 2 warnings issued across 9 modules.",
        "Current verdict is 'Request Changes' due to four high-severity findings.",
        "Authentication, Secrets Management, and Configuration Review areas are marked as 'Failed'.",
        "Overall security posture is moderate despite sound local-first privacy design and robust auth API attack rejection."
      ],
      criticalIssues: [
        "Secrets are committed in tracked .env files (SR-001).",
        "bcrypt cost factor is set to 8, violating the project policy of 12 (SR-002).",
        "A stored XSS sink exists in the React frontend via dangerouslySetInnerHTML for user-supplied resume text (SR-003).",
        "Missing rate limiting on /login and /register endpoints leaves credential-stuffing attacks unmitigated (SR-004)."
      ],
      mediumIssues: [
        "JWT verification path is not pinned to ['HS256'] (SR-005).",
        "CI coverage gate is set to 38%, significantly below the documented 80% threshold (SR-006).",
        "JWT algorithms are not explicitly pinned, which can lead to algorithm confusion attacks (OWASP A07).",
        "Frontend JWT storage in localStorage is less secure than httpOnly cookies (SR-013).",
        "The code coverage minimum (COVERAGE_MIN) is low and should be increased for better quality assurance."
      ],
      recommendations: [
        "Rotate all committed secrets; move real values to gitignored local .env files and GitHub Actions secrets.",
        "Increase bcrypt cost factor to 12 and centralize the bcrypt call in a single helper.",
        "Remove dangerouslySetInnerHTML for resume text; render plain text or sanitize with DOMPurify.",
        "Implement express-rate-limit on /login (5 req/min) and /register (stricter) with per-account backoff.",
        "Pin JWT verify() algorithm to ['HS256'] and add a unit test that asserts a 'none' token is rejected."
      ],
      positiveFindings: [
        "Prompt safety, secrets hygiene, frontend hardening, configuration, CI hygiene, and test data items passed.",
        "Resume and JD text is truncated before prompt composition, with output validated against a strict JSON schema (SR-007).",
        "React output rendering is generally safe by default, with only one identified dangerouslySetInnerHTML sink (SR-008).",
        ".env.example files properly document all required keys (SR-010)."
      ],
      conclusion:
        "While showing strong security practices in CI/CD and data handling, the project has several high-severity vulnerabilities related to authentication, secret management, and configuration. These must be prioritized for remediation to significantly improve the application's overall security posture."
    }
  },
  {
    id: "sec-review-input",
    title: "Security Review All Input",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-input.json",
    generatedAt: "7/28/2026, 2:30:10 PM",
    timestamp: 1785277810000,
    size: "14.2 KB"
  },
  {
    id: "junit-python-1",
    title: "Junit Python",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/junit-python.html",
    generatedAt: "7/28/2026, 1:15:00 PM",
    timestamp: 1785273300000,
    size: "42.1 KB"
  },
  {
    id: "ci-summary-html",
    title: "CI Summary",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/ci-summary.html",
    generatedAt: "7/28/2026, 1:12:00 PM",
    timestamp: 1785273120000,
    size: "18.5 KB"
  },
  {
    id: "coverage-python-html",
    title: "Coverage Python",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/coverage-python.html",
    generatedAt: "7/28/2026, 1:10:00 PM",
    timestamp: 1785273000000,
    size: "89.4 KB"
  },
  {
    id: "ci-dist-index",
    title: "Index",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/dist-frontend/index.html",
    generatedAt: "7/28/2026, 12:45:00 PM",
    timestamp: 1785271500000,
    size: "12.0 KB"
  },
  {
    id: "ci-summary-json",
    title: "CI Summary",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/ci-summary.json",
    generatedAt: "7/28/2026, 12:40:00 PM",
    timestamp: 1785271200000,
    size: "6.8 KB"
  },
  {
    id: "ci-dist-reports",
    title: "Reports",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/dist-frontend/reports.json",
    generatedAt: "7/28/2026, 12:35:00 PM",
    timestamp: 1785270900000,
    size: "9.1 KB"
  },
  {
    id: "ci-dist-test-index",
    title: "Index",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/dist-frontend-test/index.html",
    generatedAt: "7/28/2026, 12:30:00 PM",
    timestamp: 1785270600000,
    size: "11.2 KB"
  },
  {
    id: "cov-api-py",
    title: "Api Py",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/api_py.html",
    generatedAt: "7/28/2026, 12:00:00 PM",
    timestamp: 1785268800000,
    size: "35.6 KB"
  },
  {
    id: "cov-append-api-py",
    title: "Append Api Py",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/append_api_py.html",
    generatedAt: "7/28/2026, 11:55:00 AM",
    timestamp: 1785268500000,
    size: "28.3 KB"
  },
  {
    id: "cov-backend-py",
    title: "Backend Py",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/backend_py.html",
    generatedAt: "7/28/2026, 11:50:00 AM",
    timestamp: 1785268200000,
    size: "54.1 KB"
  },
  {
    id: "cov-class-index",
    title: "Class Index",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/class_index.html",
    generatedAt: "7/28/2026, 11:45:00 AM",
    timestamp: 1785267900000,
    size: "15.4 KB"
  },
  {
    id: "cov-function-index",
    title: "Function Index",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/function_index.html",
    generatedAt: "7/28/2026, 11:40:00 AM",
    timestamp: 1785267600000,
    size: "18.2 KB"
  },
  {
    id: "cov-index",
    title: "Index",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/index.html",
    generatedAt: "7/28/2026, 11:35:00 AM",
    timestamp: 1785267300000,
    size: "22.0 KB"
  },
  {
    id: "cov-ai-dashboard",
    title: "Ai Dashboard",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/ai-dashboard.json",
    generatedAt: "7/28/2026, 11:30:00 AM",
    timestamp: 1785267000000,
    size: "8.4 KB"
  },
  {
    id: "cov-status",
    title: "Status",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/htmlcov-python/status.json",
    generatedAt: "7/28/2026, 11:25:00 AM",
    timestamp: 1785266700000,
    size: "4.2 KB"
  },
  {
    id: "cov-python-xml",
    title: "Coverage Python",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/coverage-python.xml",
    generatedAt: "7/28/2026, 11:20:00 AM",
    timestamp: 1785266400000,
    size: "65.0 KB"
  },
  {
    id: "junit-python-xml",
    title: "Junit Python",
    kind: "CI Report",
    category: "ci",
    path: "reports/ci/backend-python-reports/junit-python.xml",
    generatedAt: "7/28/2026, 11:15:00 AM",
    timestamp: 1785266100000,
    size: "12.8 KB"
  },
  {
    id: "invoke-txt",
    title: "Invoke",
    kind: "Code Review",
    category: "code",
    path: ".code-review/invoke.txt",
    generatedAt: "7/27/2026, 4:10:00 PM",
    timestamp: 1785197400000,
    size: "2.1 KB"
  },
  {
    id: "last-changed-files",
    title: "Last Changed Files",
    kind: "Code Review",
    category: "code",
    path: ".code-review/last-changed-files.txt",
    generatedAt: "7/27/2026, 4:05:00 PM",
    timestamp: 1785197100000,
    size: "1.8 KB"
  },
  {
    id: "sec-review-2026-07-17",
    title: "Security Review All 2026 07 17 103000",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-17-103000.html",
    generatedAt: "7/17/2026, 10:30:00 AM",
    timestamp: 1784313000000,
    size: "26.4 KB"
  },
  {
    id: "sec-review-2026-07-16",
    title: "Security Review All 2026 07 16",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-16.html",
    generatedAt: "7/16/2026, 3:20:00 PM",
    timestamp: 1784244000000,
    size: "25.9 KB"
  },
  {
    id: "sec-review-template",
    title: "Template",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/_template.html",
    generatedAt: "7/15/2026, 2:00:00 PM",
    timestamp: 1784152800000,
    size: "5.4 KB"
  },
  {
    id: "sec-review-2026-07-14",
    title: "Security Review All 2026 07 14",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-14.html",
    generatedAt: "7/14/2026, 5:10:00 PM",
    timestamp: 1784077800000,
    size: "24.8 KB"
  },
  {
    id: "checklist-report-html",
    title: "Checklist Report",
    kind: "Code Review",
    category: "code",
    path: ".code-review/checklist-report.html",
    generatedAt: "7/14/2026, 1:30:00 PM",
    timestamp: 1784064600000,
    size: "19.2 KB",
    hasSummary: true,
    isCached: true,
    summary: {
      overallAssessment:
        "The automated AI code review checklist passes core standard compliance with minor recommendations for refactoring and documentation.",
      keyFindings: [
        "12 module checks evaluated across frontend and backend codebases.",
        "Code formatting, lint compliance, and type coverage met project criteria.",
        "No blocking syntax or architectural errors found."
      ],
      criticalIssues: [],
      mediumIssues: [
        "Component prop validation could be enhanced with explicit Zod schema bounds.",
        "Unused test utilities in frontend-test should be pruned."
      ],
      recommendations: [
        "Prune dead mock imports in test utilities.",
        "Standardize error logging helpers across express route handlers."
      ],
      positiveFindings: [
        "Clean modular split in React page components.",
        "Robust auth session storage fallback handles edge cases smoothly."
      ],
      conclusion:
        "Code quality is sound and meets pull request checklist standards."
    }
  },
  {
    id: "last-checklist-data",
    title: "Last Checklist Data",
    kind: "Code Review",
    category: "code",
    path: ".code-review/last-checklist-data.json",
    generatedAt: "7/14/2026, 1:25:00 PM",
    timestamp: 1784064300000,
    size: "8.6 KB"
  },
  {
    id: "lighthouse-report-html",
    title: "Lighthouse Report",
    kind: "Performance Review",
    category: "perf",
    path: "reports/lighthouse-report.html",
    generatedAt: "7/10/2026, 11:00:00 AM",
    timestamp: 1783710000000,
    size: "312.4 KB",
    hasSummary: true,
    isCached: true,
    summary: {
      overallAssessment:
        "Lighthouse performance analysis shows excellent First Contentful Paint and high accessibility score on desktop and mobile viewports.",
      keyFindings: [
        "Performance Score: 94 / 100",
        "Accessibility Score: 98 / 100",
        "Best Practices: 100 / 100",
        "SEO Score: 92 / 100"
      ],
      criticalIssues: [],
      mediumIssues: [
        "Unused JavaScript execution time on cold bundle load (380ms delay)."
      ],
      recommendations: [
        "Implement route-level code splitting for heavy sub-dashboards."
      ],
      positiveFindings: [
        "Fast response time (LCP under 1.2s).",
        "Zero cumulative layout shift (CLS: 0.00)."
      ],
      conclusion:
        "Application meets high speed and user experience criteria."
    }
  },
  {
    id: "sec-reports-index",
    title: "Index",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/index.html",
    generatedAt: "7/03/2026, 9:00:00 PM",
    timestamp: 1783141200000,
    size: "4.1 KB"
  },
  {
    id: "sec-review-2026-07-03-203714",
    title: "Security Review All 2026 07 03 203714",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-03-203714.html",
    generatedAt: "7/03/2026, 8:37:14 PM",
    timestamp: 1783139834000,
    size: "23.5 KB"
  },
  {
    id: "sec-review-2026-07-03",
    title: "Security Review All 2026 07 03",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-03.html",
    generatedAt: "7/03/2026, 6:00:00 PM",
    timestamp: 1783130400000,
    size: "22.9 KB"
  },
  {
    id: "sec-review-2026-07-01",
    title: "Security Review All 2026 07 01",
    kind: "Security Review",
    category: "security",
    path: "skills/reports/security-review-all-2026-07-01.html",
    generatedAt: "7/01/2026, 10:15:00 AM",
    timestamp: 1782929700000,
    size: "21.8 KB"
  }
];

export default function ReportSummaryDashboard() {
  const [user] = useState(() => getStoredUser() || { email: "manager@local.test" });
  const [filterCategory, setFilterCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOrder, setSortOrder] = useState("newest");
  const [expandedId, setExpandedId] = useState("sec-review-2026-07-28"); // expanded by default as in screenshot
  const [showPerfBucket, setShowPerfBucket] = useState(false);
  const [reports, setReports] = useState(INITIAL_REPORTS);
  const [toast, setToast] = useState(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleLogout = () => {
    clearSession();
    window.location.href = "/login";
  };

  const openReport = (report) => {
    showToast(`Opening ${report.title}...`);
    window.open(`/${report.path}`, "_blank");
  };

  const downloadReport = (report) => {
    showToast(`Downloading ${report.title}...`);
    const blob = new Blob([`Dummy artifact content for ${report.title}`], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = report.path.split("/").pop() || `${report.id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleRegenerate = (report) => {
    showToast(`Regenerating summary for ${report.title}...`);
  };

  // Metrics
  const totalReportsCount = 3044;
  const securityCount = 10;
  const codeCount = 4;
  const perfCount = 3013;
  const summariesCount = 3;

  const filteredReports = useMemo(() => {
    let list = [...reports];
    if (filterCategory !== "all") {
      list = list.filter((r) => r.category === filterCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (r) =>
          r.title.toLowerCase().includes(q) ||
          r.kind.toLowerCase().includes(q) ||
          r.path.toLowerCase().includes(q)
      );
    }
    if (sortOrder === "newest") {
      list.sort((a, b) => b.timestamp - a.timestamp);
    } else {
      list.sort((a, b) => a.timestamp - b.timestamp);
    }
    return list;
  }, [reports, filterCategory, searchQuery, sortOrder]);

  return (
    <div style={{ background: "#111614", color: "#e3eae6", minHeight: "100vh", fontFamily: "Outfit, Inter, sans-serif" }}>
      {/* Top Header Bar */}
      <header
        style={{
          background: "#171f1c",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 50
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: "rgba(130, 180, 167, 0.15)",
              border: "1px solid rgba(130, 180, 167, 0.3)",
              color: "#82b4a7",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}
          >
            <FlaskConical size={20} />
          </div>
          <div>
            <h1 style={{ fontSize: 16, fontWeight: 700, color: "#ffffff", margin: 0 }}>
              Report Summary Dashboard
            </h1>
            <p style={{ fontSize: 12, color: "#8a9791", margin: 0 }}>
              Browse, summarize, and download every generated report. Performance artifacts are grouped so the page stays fast.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 13 }}>
          <button
            onClick={() => (window.location.href = "/testing-dashboard")}
            type="button"
            style={{
              background: "transparent",
              border: "0",
              color: "#82b4a7",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontWeight: 500,
              fontSize: 13
            }}
          >
            <ArrowLeft size={14} /> Testing Dashboard
          </button>
          <strong style={{ color: "#ffffff", fontWeight: 600 }}>{user.email || "manager@local.test"}</strong>
          <button
            onClick={handleLogout}
            type="button"
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              color: "#ffffff",
              padding: "5px 12px",
              borderRadius: 6,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              fontWeight: 600
            }}
          >
            <LogOut size={13} /> Logout
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main style={{ padding: "24px 32px", maxWidth: 1600, margin: "0 auto" }}>
        {/* Generated Reports Banner & Stats */}
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#ffffff", marginBottom: 4 }}>
            Generated Reports
          </h2>
          <p style={{ fontSize: 12.5, color: "#8a9791", margin: 0, marginBottom: 16 }}>
            Reports open one at a time. The Performance &amp; Allure bucket is collapsed by default.
          </p>

          {/* Stat Cards Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 12,
              marginBottom: 16
            }}
          >
            {/* TOTAL REPORTS */}
            <div
              style={{
                background: "#1c2421",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 4
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8a9791", fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                <FileText size={13} /> TOTAL REPORTS
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#ffffff" }}>{totalReportsCount}</div>
            </div>

            {/* SECURITY REVIEWS */}
            <div
              style={{
                background: "#1c2421",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderLeft: "3px solid #ef4444",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 4
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8a9791", fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                <ShieldCheck size={13} style={{ color: "#ef4444" }} /> SECURITY REVIEWS
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#ffffff" }}>{securityCount}</div>
            </div>

            {/* CODE REVIEWS */}
            <div
              style={{
                background: "#1c2421",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderLeft: "3px solid #3b82f6",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 4
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8a9791", fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                <Code size={13} style={{ color: "#3b82f6" }} /> CODE REVIEWS
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#ffffff" }}>{codeCount}</div>
            </div>

            {/* PERFORMANCE REVIEWS */}
            <div
              style={{
                background: "#1c2421",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderLeft: "3px solid #f59e0b",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 4
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8a9791", fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                <BarChart2 size={13} style={{ color: "#f59e0b" }} /> PERFORMANCE REVIEWS
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#ffffff" }}>{perfCount}</div>
            </div>

            {/* SUMMARIES GENERATED */}
            <div
              style={{
                background: "#1c2421",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderLeft: "3px solid #10b981",
                borderRadius: 8,
                padding: "12px 16px",
                display: "flex",
                flexDirection: "column",
                gap: 4
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#8a9791", fontSize: 11, fontWeight: 700, letterSpacing: "0.5px" }}>
                <Sparkles size={13} style={{ color: "#10b981" }} /> SUMMARIES GENERATED
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#ffffff" }}>{summariesCount}</div>
            </div>
          </div>

          {/* Filter Chips Bar & Tools */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {[
                { key: "all", label: "All", icon: Layers },
                { key: "security", label: "Security", icon: ShieldCheck },
                { key: "code", label: "Code", icon: Code },
                { key: "perf", label: "Performance", icon: BarChart2 },
                { key: "ci", label: "CI", icon: CheckCircle2 }
              ].map((chip) => {
                const Icon = chip.icon;
                const active = filterCategory === chip.key;
                return (
                  <button
                    key={chip.key}
                    onClick={() => setFilterCategory(chip.key)}
                    type="button"
                    style={{
                      background: active ? "#82b4a7" : "rgba(255, 255, 255, 0.05)",
                      color: active ? "#111614" : "#c6d1cb",
                      border: active ? "0" : "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: 20,
                      padding: "5px 14px",
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6
                    }}
                  >
                    <Icon size={12} /> {chip.label}
                  </button>
                );
              })}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ position: "relative", minWidth: 220 }}>
                <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "#8a9791" }} />
                <input
                  type="text"
                  placeholder="Search reports"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: "100%",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: 6,
                    padding: "7px 10px 7px 32px",
                    color: "#ffffff",
                    fontSize: 12,
                    outline: "none"
                  }}
                />
              </div>

              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 6,
                  color: "#ffffff",
                  padding: "7px 10px",
                  fontSize: 12,
                  outline: "none",
                  cursor: "pointer"
                }}
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
              </select>

              <button
                onClick={() => showToast("Refreshed reports catalog")}
                type="button"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  color: "#ffffff",
                  borderRadius: 6,
                  padding: "7px 12px",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6
                }}
              >
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Reports Grid Section Container */}
        <div
          style={{
            background: "#161d1a",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: 10,
            padding: "20px",
            marginBottom: 20
          }}
        >
          {/* Header row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, fontWeight: 700, color: "#ffffff" }}>
              <FileText size={18} style={{ color: "#82b4a7" }} /> Reports
            </div>
            <div style={{ fontSize: 12, color: "#8a9791" }}>
              {filteredReports.length} reports
            </div>
          </div>

          {/* 2-Column Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(500px, 1fr))",
              gap: 16,
              alignItems: "start"
            }}
          >
            {filteredReports.map((report) => {
              const isExpanded = expandedId === report.id;

              return (
                <div
                  key={report.id}
                  style={{
                    background: "#1c2421",
                    border: isExpanded
                      ? "1px solid rgba(130, 180, 167, 0.4)"
                      : "1px solid rgba(255, 255, 255, 0.06)",
                    borderRadius: 8,
                    padding: "12px 16px",
                    transition: "all 150ms ease",
                    gridColumn: isExpanded ? "1 / -1" : "auto"
                  }}
                >
                  {/* Item Header */}
                  <div
                    onClick={() => setExpandedId(isExpanded ? null : report.id)}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 8,
                      cursor: "pointer",
                      userSelect: "none"
                    }}
                  >
                    <div style={{ marginTop: 2, color: "#8a9791" }}>
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <FileText size={15} style={{ color: "#82b4a7" }} />
                        <span style={{ fontSize: 14, fontWeight: 700, color: "#ffffff" }}>
                          {report.title}
                        </span>
                      </div>
                      <div style={{ fontSize: 11.5, color: "#8a9791", marginTop: 2 }}>
                        <strong style={{ color: "#c6d1cb", fontWeight: 600 }}>{report.kind}</strong>{" "}
                        <span style={{ fontFamily: "monospace", color: "#6b7a73" }}>{report.path}</span>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Content View (Matches Screenshot 3) */}
                  {isExpanded && (
                    <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid rgba(255, 255, 255, 0.06)" }}>
                      {/* Sub Meta Row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          fontSize: 12,
                          color: "#8a9791",
                          marginBottom: 12,
                          flexWrap: "wrap"
                        }}
                      >
                        <div>
                          Generated: <span style={{ color: "#ffffff" }}>{report.generatedAt}</span>
                        </div>
                        <div>
                          Size: <span style={{ color: "#ffffff" }}>{report.size}</span>
                        </div>
                        {report.hasSummary && (
                          <span
                            style={{
                              background: "rgba(16, 185, 129, 0.15)",
                              color: "#10b981",
                              border: "1px solid rgba(16, 185, 129, 0.3)",
                              padding: "1px 8px",
                              borderRadius: 12,
                              fontSize: 11,
                              fontWeight: 600,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4
                            }}
                          >
                            <CheckCircle2 size={11} /> Summary Ready
                          </span>
                        )}
                        {report.isCached && (
                          <span
                            style={{
                              background: "rgba(255, 255, 255, 0.06)",
                              color: "#8a9791",
                              padding: "1px 8px",
                              borderRadius: 12,
                              fontSize: 11,
                              fontWeight: 500
                            }}
                          >
                            cached
                          </span>
                        )}
                      </div>

                      {/* Action Buttons Row */}
                      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
                        <button
                          onClick={() => handleRegenerate(report)}
                          type="button"
                          style={{
                            background: "rgba(255, 255, 255, 0.06)",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                            color: "#ffffff",
                            padding: "6px 12px",
                            borderRadius: 6,
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 6
                          }}
                        >
                          <RefreshCw size={12} /> Regenerate
                        </button>
                        <button
                          onClick={() => openReport(report)}
                          type="button"
                          style={{
                            background: "transparent",
                            border: "0",
                            color: "#82b4a7",
                            padding: "6px 12px",
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 6
                          }}
                        >
                          <ExternalLink size={12} /> Open HTML
                        </button>
                        <button
                          onClick={() => downloadReport(report)}
                          type="button"
                          style={{
                            background: "transparent",
                            border: "0",
                            color: "#82b4a7",
                            padding: "6px 12px",
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 6
                          }}
                        >
                          <Download size={12} /> Download
                        </button>
                      </div>

                      {/* AI Summary Box */}
                      {report.summary && (
                        <div
                          style={{
                            background: "#131a17",
                            border: "1px solid rgba(255, 255, 255, 0.08)",
                            borderRadius: 8,
                            padding: "16px"
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              fontSize: 13,
                              fontWeight: 700,
                              color: "#ffffff",
                              marginBottom: 16
                            }}
                          >
                            <Sparkles size={14} style={{ color: "#82b4a7" }} /> AI Summary · {report.title}
                          </div>

                          {/* 2x2 Grid of Summary Sub-Cards */}
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
                              gap: 12,
                              marginBottom: 12
                            }}
                          >
                            {/* OVERALL ASSESSMENT */}
                            <div
                              style={{
                                background: "rgba(255, 255, 255, 0.03)",
                                border: "1px solid rgba(255, 255, 255, 0.06)",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#8a9791", letterSpacing: "0.5px", marginBottom: 6 }}>
                                OVERALL ASSESSMENT
                              </div>
                              <p style={{ fontSize: 12.5, color: "#d1ded8", margin: 0, lineHeight: 1.5 }}>
                                {report.summary.overallAssessment}
                              </p>
                            </div>

                            {/* KEY FINDINGS */}
                            <div
                              style={{
                                background: "rgba(255, 255, 255, 0.03)",
                                border: "1px solid rgba(255, 255, 255, 0.06)",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#8a9791", letterSpacing: "0.5px", marginBottom: 6 }}>
                                KEY FINDINGS
                              </div>
                              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#d1ded8", lineHeight: 1.5 }}>
                                {report.summary.keyFindings.map((item, idx) => (
                                  <li key={idx} style={{ marginBottom: 3 }}>{item}</li>
                                ))}
                              </ul>
                            </div>

                            {/* CRITICAL ISSUES (Red border) */}
                            <div
                              style={{
                                background: "rgba(239, 68, 68, 0.04)",
                                border: "1px solid rgba(239, 68, 68, 0.15)",
                                borderLeft: "3px solid #ef4444",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#ef4444", letterSpacing: "0.5px", marginBottom: 6 }}>
                                CRITICAL ISSUES
                              </div>
                              {report.summary.criticalIssues.length > 0 ? (
                                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#f87171", lineHeight: 1.5 }}>
                                  {report.summary.criticalIssues.map((item, idx) => (
                                    <li key={idx} style={{ marginBottom: 3 }}>{item}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p style={{ fontSize: 12, color: "#8a9791", margin: 0 }}>No critical issues detected.</p>
                              )}
                            </div>

                            {/* MEDIUM ISSUES (Orange border) */}
                            <div
                              style={{
                                background: "rgba(245, 158, 11, 0.04)",
                                border: "1px solid rgba(245, 158, 11, 0.15)",
                                borderLeft: "3px solid #f59e0b",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#f59e0b", letterSpacing: "0.5px", marginBottom: 6 }}>
                                MEDIUM ISSUES
                              </div>
                              {report.summary.mediumIssues.length > 0 ? (
                                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#fbbf24", lineHeight: 1.5 }}>
                                  {report.summary.mediumIssues.map((item, idx) => (
                                    <li key={idx} style={{ marginBottom: 3 }}>{item}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p style={{ fontSize: 12, color: "#8a9791", margin: 0 }}>No medium issues detected.</p>
                              )}
                            </div>

                            {/* RECOMMENDATIONS (Blue border) */}
                            <div
                              style={{
                                background: "rgba(59, 130, 246, 0.04)",
                                border: "1px solid rgba(59, 130, 246, 0.15)",
                                borderLeft: "3px solid #3b82f6",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#3b82f6", letterSpacing: "0.5px", marginBottom: 6 }}>
                                RECOMMENDATIONS
                              </div>
                              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#93c5fd", lineHeight: 1.5 }}>
                                {report.summary.recommendations.map((item, idx) => (
                                  <li key={idx} style={{ marginBottom: 3 }}>{item}</li>
                                ))}
                              </ul>
                            </div>

                            {/* POSITIVE FINDINGS (Green border) */}
                            <div
                              style={{
                                background: "rgba(16, 185, 129, 0.04)",
                                border: "1px solid rgba(16, 185, 129, 0.15)",
                                borderLeft: "3px solid #10b981",
                                borderRadius: 6,
                                padding: "12px 14px"
                              }}
                            >
                              <div style={{ fontSize: 10.5, fontWeight: 700, color: "#10b981", letterSpacing: "0.5px", marginBottom: 6 }}>
                                POSITIVE FINDINGS
                              </div>
                              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "#6ee7b7", lineHeight: 1.5 }}>
                                {report.summary.positiveFindings.map((item, idx) => (
                                  <li key={idx} style={{ marginBottom: 3 }}>{item}</li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          {/* CONCLUSION (Full width) */}
                          <div
                            style={{
                              background: "rgba(255, 255, 255, 0.03)",
                              border: "1px solid rgba(255, 255, 255, 0.06)",
                              borderRadius: 6,
                              padding: "12px 14px"
                            }}
                          >
                            <div style={{ fontSize: 10.5, fontWeight: 700, color: "#8a9791", letterSpacing: "0.5px", marginBottom: 6 }}>
                              CONCLUSION
                            </div>
                            <p style={{ fontSize: 12.5, color: "#d1ded8", margin: 0, lineHeight: 1.5 }}>
                              {report.summary.conclusion}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Performance & Allure Results Bucket Accordion (Bottom) */}
        <div
          style={{
            background: "#161d1a",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: 8,
            padding: "12px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}
        >
          <div
            onClick={() => setShowPerfBucket(!showPerfBucket)}
            style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", userSelect: "none" }}
          >
            <div style={{ color: "#8a9791" }}>
              {showPerfBucket ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#ffffff" }}>
              Performance &amp; Allure Results
            </div>
            <div style={{ fontSize: 12, color: "#8a9791" }}>
              3,012 reports · 0 summarized
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              onClick={() => showToast("Summarizing all performance artifacts...")}
              type="button"
              style={{
                background: "rgba(130, 180, 167, 0.15)",
                border: "1px solid rgba(130, 180, 167, 0.3)",
                color: "#82b4a7",
                padding: "5px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6
              }}
            >
              <Sparkles size={12} /> Summarize all
            </button>
            <button
              onClick={() => setShowPerfBucket(!showPerfBucket)}
              type="button"
              style={{
                background: "rgba(255, 255, 255, 0.06)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                color: "#ffffff",
                padding: "5px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer"
              }}
            >
              {showPerfBucket ? "Hide" : "Show"}
            </button>
          </div>
        </div>
      </main>

      {/* Toast notification */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            background: "#1c2421",
            border: "1px solid rgba(130, 180, 167, 0.4)",
            borderRadius: 8,
            padding: "10px 16px",
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 600,
            boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
            zIndex: 100
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}
