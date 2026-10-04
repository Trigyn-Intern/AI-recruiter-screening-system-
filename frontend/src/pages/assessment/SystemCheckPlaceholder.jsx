import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Brain,
  ShieldCheck,
  CheckCircle2,
  Camera,
  Mic,
  Wifi,
  Monitor,
  ArrowLeft,
  Sparkles
} from "lucide-react";
import "./assessment.css";

function SystemCheckPlaceholder() {
  const navigate = useNavigate();

  return (
    <div className="assessment-page-wrapper">
      {/* Header */}
      <header className="assessment-header">
        <div className="assessment-header-content">
          <div className="assessment-brand">
            <div className="assessment-brand-icon">
              <Brain size={22} />
            </div>
            <div className="assessment-brand-text">
              <h1>AI Recruiter</h1>
              <p>Assessment Portal</p>
            </div>
          </div>

          <div className="assessment-header-actions">
            <span className="assessment-badge">
              <ShieldCheck size={14} />
              Step 2 of 3
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="assessment-container">
        <div className="system-check-card">
          <div className="system-check-badge">
            <Sparkles size={16} />
            Phase 2 Module Placeholder
          </div>

          <h2>System Check Page</h2>
          <p style={{ color: "var(--text-medium)", maxWidth: "560px", margin: "0 auto 24px auto" }}>
            You have successfully acknowledged the instructions on the Assessment Landing Page.
          </p>

          {/* Stepper indicator */}
          <div className="stepper-container">
            <div className="stepper-step completed">
              <span className="step-num">✓</span>
              <span>1. Overview</span>
            </div>
            <div className="stepper-divider" />
            <div className="stepper-step active">
              <span className="step-num">2</span>
              <span>2. System Check</span>
            </div>
            <div className="stepper-divider" />
            <div className="stepper-step pending">
              <span className="step-num">3</span>
              <span>3. Start Test</span>
            </div>
          </div>

          {/* Check Item Previews */}
          <div className="check-preview-box">
            <div className="check-item">
              <Camera className="check-item-icon" size={18} />
              <span className="check-item-text">Webcam Check</span>
            </div>
            <div className="check-item">
              <Mic className="check-item-icon" size={18} />
              <span className="check-item-text">Microphone Audio</span>
            </div>
            <div className="check-item">
              <Wifi className="check-item-icon" size={18} />
              <span className="check-item-text">Network Connection</span>
            </div>
            <div className="check-item">
              <Monitor className="check-item-icon" size={18} />
              <span className="check-item-text">Browser Specs</span>
            </div>
          </div>

          <div style={{ marginTop: "32px", display: "flex", justifyContent: "center", gap: "12px" }}>
            <button
              type="button"
              className="help-button"
              onClick={() => navigate("/assessment/start")}
            >
              <ArrowLeft size={16} />
              Back to Assessment Overview
            </button>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="assessment-footer">
        © {new Date().getFullYear()} AI Recruiter Screening System. All rights reserved.
      </footer>
    </div>
  );
}

export default SystemCheckPlaceholder;
