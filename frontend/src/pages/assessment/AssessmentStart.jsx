import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Brain,
  Clock,
  HelpCircle,
  BarChart2,
  CheckSquare,
  AlertTriangle,
  Camera,
  RotateCcw,
  ShieldCheck,
  ArrowRight,
  Info,
  X,
  Briefcase,
  FileText
} from "lucide-react";
import "./assessment.css";

import { useSearchParams } from "react-router-dom";
import { findAssessmentRecord } from "../../utils/assessmentStore";

function AssessmentStart() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [acknowledged, setAcknowledged] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);

  const assessmentId = searchParams.get("assessmentId") || "";
  const candidateId = searchParams.get("candidateId") || "";
  const queryRole = searchParams.get("role") || "";

  const { record } = findAssessmentRecord({ assessmentId, candidateId, role: queryRole });
  const jobRole = record?.jobRole || queryRole || "AI/ML Engineer";

  const assessmentData = {
    title: `${jobRole} Technical Assessment`,
    jobRole: jobRole,
    duration: record?.duration || "45 Mins",
    questionCount: record?.questionCount || "15 Questions",
    difficulty: "Intermediate - Advanced",
    description:
      `This technical assessment evaluates your problem-solving capabilities, core programming skills, and key domain knowledge required for the ${jobRole} role.`
  };

  const rules = [
    {
      id: 1,
      icon: Clock,
      title: "Complete within the given time",
      detail: "The 45-minute countdown starts as soon as you launch the assessment. Keep track of your time."
    },
    {
      id: 2,
      icon: AlertTriangle,
      title: "Do not leave the assessment window",
      detail: "Avoid switching browser tabs, minimizing the screen, or leaving the active assessment view unnecessarily."
    },
    {
      id: 3,
      icon: Camera,
      title: "Camera & microphone availability",
      detail: "Ensure your camera and microphone are connected and accessible if required in subsequent steps."
    },
    {
      id: 4,
      icon: RotateCcw,
      title: "One-time submission",
      detail: "Once submitted, the assessment cannot be restarted or re-attempted. Review your answers before submitting."
    }
  ];

  const handleProceed = () => {
    if (acknowledged) {
      const q = new URLSearchParams({
        ...(assessmentId ? { assessmentId } : {}),
        ...(candidateId ? { candidateId } : {}),
        ...(jobRole ? { role: jobRole } : {})
      }).toString();
      navigate(`/assessment/system-check?${q}`);
    }
  };

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
              Online Assessment
            </span>
            <button
              type="button"
              className="help-button"
              onClick={() => setShowHelpModal(true)}
              aria-label="Help and information"
            >
              <HelpCircle size={16} />
              Need Help?
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="assessment-container">
        <div className="assessment-hero">
          <span className="assessment-hero-tag">Candidate Onboarding</span>
          <h2>Candidate Assessment Overview</h2>
          <p>Please review the details and guidelines carefully before beginning.</p>
        </div>

        {/* Assessment Overview Card */}
        <div className="assessment-card">
          <div className="assessment-card-header">
            <div className="assessment-title-row">
              <h3>{assessmentData.title}</h3>
              <span className="difficulty-tag">{assessmentData.difficulty}</span>
            </div>

            <div className="assessment-role-badge">
              <Briefcase size={14} />
              <span>Target Role: {assessmentData.jobRole}</span>
            </div>

            <p className="assessment-description">{assessmentData.description}</p>
          </div>

          {/* Meta Information Bar */}
          <div className="assessment-meta-grid">
            <div className="meta-item">
              <div className="meta-icon">
                <Clock size={18} />
              </div>
              <div className="meta-info">
                <span className="meta-label">Duration</span>
                <span className="meta-value">{assessmentData.duration}</span>
              </div>
            </div>

            <div className="meta-item">
              <div className="meta-icon">
                <FileText size={18} />
              </div>
              <div className="meta-info">
                <span className="meta-label">Questions</span>
                <span className="meta-value">{assessmentData.questionCount}</span>
              </div>
            </div>

            <div className="meta-item">
              <div className="meta-icon">
                <BarChart2 size={18} />
              </div>
              <div className="meta-info">
                <span className="meta-label">Difficulty</span>
                <span className="meta-value">{assessmentData.difficulty}</span>
              </div>
            </div>
          </div>

          {/* Rules & Instructions Section */}
          <div className="assessment-card-body">
            <h4 className="rules-section-title">
              <Info size={18} color="#D96B27" />
              Assessment Instructions & Rules
            </h4>

            <ul className="rules-list">
              {rules.map((rule) => {
                const IconComp = rule.icon;
                return (
                  <li key={rule.id} className="rule-item">
                    <IconComp className="rule-bullet-icon" size={18} />
                    <div className="rule-text">
                      <strong>{rule.title}: </strong>
                      {rule.detail}
                    </div>
                  </li>
                );
              })}
            </ul>

            {/* Candidate Acknowledgement */}
            <div className="acknowledgement-box">
              <input
                type="checkbox"
                id="agree-instructions"
                className="acknowledgement-checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
              />
              <div>
                <label htmlFor="agree-instructions" className="acknowledgement-label">
                  I have read and understood the instructions.
                </label>
                <div className="acknowledgement-subtext">
                  By checking this box, you confirm that you are ready to begin the assessment under the stated guidelines.
                </div>
              </div>
            </div>

            {/* Action Section */}
            <div className="action-area">
              <button
                type="button"
                className="proceed-btn"
                disabled={!acknowledged}
                onClick={handleProceed}
              >
                <span>Proceed to System Check</span>
                <ArrowRight size={18} />
              </button>
              {!acknowledged && (
                <p className="btn-disabled-hint">
                  Please acknowledge the instructions above to continue.
                </p>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Help Modal */}
      {showHelpModal && (
        <div className="help-modal-overlay" onClick={() => setShowHelpModal(false)}>
          <div className="help-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="help-modal-header">
              <h4>Assessment Help & Support</h4>
              <button
                type="button"
                className="close-modal-btn"
                onClick={() => setShowHelpModal(false)}
                aria-label="Close modal"
              >
                <X size={18} />
              </button>
            </div>
            <div className="help-modal-body">
              <h5>Technical Requirements</h5>
              <p>
                Ensure you are using a modern browser (Chrome, Firefox, Edge, or Safari) with standard permissions enabled for audio/video input if prompted.
              </p>
              <h5>Internet & Power Stability</h5>
              <p>
                Connect to a stable Wi-Fi or wired network. Close non-essential background applications before proceeding.
              </p>
              <h5>Need Candidate Support?</h5>
              <p>
                If you encounter technical issues during your session, contact our talent support team at <strong>support@airecruiter.com</strong> with your candidate registration ID.
              </p>
            </div>
            <div className="help-modal-footer">
              <button
                type="button"
                className="help-button"
                onClick={() => setShowHelpModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="assessment-footer">
        © {new Date().getFullYear()} AI Recruiter Screening System. All rights reserved.
      </footer>
    </div>
  );
}

export default AssessmentStart;
