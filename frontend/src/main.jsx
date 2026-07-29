import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/auth/Login";
import Signup from "./pages/auth/Signup";
import Dashboard from "./pages/dashboard/Dashboard";
import RequireAuth from "./pages/RequireAuth";
import TestingDashboard from "../../frontend-test/src/pages/TestingDashboard";
import ReportSummaryDashboard from "../../frontend-test/src/pages/ReportSummaryDashboard";
import "./styles.css";
import "../../frontend-test/src/styles.css";

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
        <Route path="/testing-dashboard" element={<TestingDashboard />} />
        <Route path="/test" element={<TestingDashboard />} />
        <Route path="/testing" element={<TestingDashboard />} />
        <Route path="/report-summary" element={<ReportSummaryDashboard />} />
        <Route path="/reports-summary" element={<ReportSummaryDashboard />} />
        <Route path="/report-summary-dashboard" element={<ReportSummaryDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<AppRoot />);
