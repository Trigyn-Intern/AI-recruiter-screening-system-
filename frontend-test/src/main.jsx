import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import TestingDashboard from "./pages/TestingDashboard";
import ReportSummary from "./pages/ReportSummary";
import "./styles.css";

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) { console.error("Dashboard crashed:", err, info); }
  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: 24, color: "#fff", fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
          <h2 style={{ color: "#f87171" }}>Dashboard crashed</h2>
          <pre>{String(this.state.err && this.state.err.stack || this.state.err)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

function AppRoot() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TestingDashboard />} />
          <Route path="/report-summary" element={<ReportSummary />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

createRoot(document.getElementById("root")).render(<AppRoot />);