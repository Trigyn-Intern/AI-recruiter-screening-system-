import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import TestingDashboard from "./pages/TestingDashboard";
import "./styles.css";

function AppRoot() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<TestingDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<AppRoot />);
