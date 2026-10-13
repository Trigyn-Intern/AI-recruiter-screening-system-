import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/auth/Login";
import Signup from "./pages/auth/Signup";
import Dashboard from "./pages/dashboard/Dashboard";
import RequireAuth from "./pages/RequireAuth";
import AssessmentStart from "./pages/assessment/AssessmentStart";
import SystemCheckPage from "./pages/assessment/SystemCheckPage";
import AssessmentTestPage from "./pages/assessment/AssessmentTestPage";
import "./styles.css";

// Phase 3 submitted confirmation — placeholder until scoring is implemented
function AssessmentSubmittedPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#FAF7F2",
        fontFamily: "Outfit, Inter, system-ui, sans-serif",
        gap: "16px",
        padding: "32px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "16px",
          background: "linear-gradient(135deg, #16A34A, #166534)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 4,
          boxShadow: "0 6px 18px rgba(22,163,74,0.28)",
        }}
      >
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      </div>
      <h2 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: "#2A241F" }}>
        Assessment Submitted!
      </h2>
      <p style={{ margin: 0, fontSize: 15, color: "#5C5248", maxWidth: 500, lineHeight: 1.6 }}>
        Thank you for completing the assessment. Your responses have been recorded.
        The recruiter team will review your submission and be in touch shortly.
      </p>
      <p style={{ margin: 0, fontSize: 13, color: "#8A7E73" }}>
        You may now close this window.
      </p>
    </div>
  );
}

function AppRoot() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route path="/assessment" element={<AssessmentStart />} />
        <Route path="/assessment/start" element={<AssessmentStart />} />
        {/* Phase 2: System check */}
        <Route path="/assessment/system-check" element={<SystemCheckPage />} />
        {/* Phase 3: Full-width assessment test layout */}
        <Route path="/assessment/test" element={<AssessmentTestPage />} />
        {/* Phase 3: Post-submission confirmation */}
        <Route path="/assessment/submitted" element={<AssessmentSubmittedPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<AppRoot />);
