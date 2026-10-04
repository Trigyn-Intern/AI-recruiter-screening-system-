import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Brain,
  Clock,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Circle,
  BookOpen,
  BarChart2,
  AlertTriangle,
  Flag,
  Send,
  X,
  Loader2,
  ShieldCheck,
  Camera
} from "lucide-react";
import "./assessmentTest.css";

import { findAssessmentRecord, transitionAssessmentStatus } from "../../utils/assessmentStore";

const API_BASE_URL = "http://127.0.0.1:8000";
const TOTAL_SECONDS = 45 * 60; // 45 minutes

// ─── Lazy-load MediaPipe face detection via CDN (shared with SystemCheckPage) ──
let mediapipeLoadPromise = null;

function loadMediaPipeCDN() {
  if (mediapipeLoadPromise) return mediapipeLoadPromise;

  mediapipeLoadPromise = new Promise((resolve, reject) => {
    if (window.FaceDetection) {
      resolve(window.FaceDetection);
      return;
    }
    const script = document.createElement("script");
    script.src =
      "https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4.1646425229/face_detection.js";
    script.crossOrigin = "anonymous";
    script.onload = () => {
      setTimeout(() => {
        if (window.FaceDetection) {
          resolve(window.FaceDetection);
        } else {
          reject(new Error("FaceDetection constructor not available after load"));
        }
      }, 1000);
    };
    script.onerror = () => {
      mediapipeLoadPromise = null; // allow retry
      reject(new Error("Failed to load MediaPipe CDN script"));
    };
    document.head.appendChild(script);
  });

  return mediapipeLoadPromise;
}

// Face event cooldown: minimum seconds between same-type face events
const FACE_EVENT_COOLDOWN_MS = 10000;

function difficultyColor(level) {
  if (!level) return "";
  const l = level.toLowerCase();
  if (l === "easy") return "at-diff-easy";
  if (l === "hard") return "at-diff-hard";
  return "at-diff-medium";
}

function formatTime(secs) {
  const m = Math.floor(secs / 60).toString().padStart(2, "0");
  const s = (secs % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// ─── Submit confirmation modal ────────────────────────────────────────────────
function SubmitModal({ answered, total, onConfirm, onCancel, isSubmitting, submitError }) {
  const unanswered = total - answered;
  return (
    <div className="at-modal-overlay" onClick={onCancel}>
      <div className="at-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="at-modal-header">
          <div className="at-modal-title-row">
            <Send size={20} className="at-modal-icon" />
            <h3>Submit Assessment</h3>
          </div>
          <button className="at-modal-close" onClick={onCancel} aria-label="Cancel" disabled={isSubmitting}>
            <X size={18} />
          </button>
        </div>
        <div className="at-modal-body">
          <div className="at-modal-stats">
            <div className="at-modal-stat answered">
              <CheckCircle2 size={18} />
              <div>
                <span className="at-modal-stat-val">{answered}</span>
                <span className="at-modal-stat-lbl">Answered</span>
              </div>
            </div>
            <div className="at-modal-stat unanswered">
              <Circle size={18} />
              <div>
                <span className="at-modal-stat-val">{unanswered}</span>
                <span className="at-modal-stat-lbl">Unanswered</span>
              </div>
            </div>
          </div>
          {submitError && (
            <div className="at-modal-warning" style={{ background: "#FEE2E2", borderColor: "#FCA5A5", color: "#991B1B", marginBottom: 12 }}>
              <AlertTriangle size={14} color="#DC2626" />
              <span>{submitError}</span>
            </div>
          )}
          {unanswered > 0 && !submitError && (
            <div className="at-modal-warning">
              <AlertTriangle size={14} />
              <span>
                You have <strong>{unanswered} unanswered question{unanswered !== 1 ? "s" : ""}</strong>.
                Unanswered questions will be marked as not attempted. You cannot return once submitted.
              </span>
            </div>
          )}
          <p className="at-modal-confirm-text">
            Are you sure you want to submit your assessment? This action cannot be undone.
          </p>
        </div>
        <div className="at-modal-footer">
          <button className="at-modal-cancel-btn" onClick={onCancel} disabled={isSubmitting}>
            Review Answers
          </button>
          <button className="at-modal-submit-btn" onClick={onConfirm} disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 size={14} className="at-spinner" style={{ animation: "spin 1s linear infinite" }} /> Submitting...
              </>
            ) : (
              <>
                <Send size={14} /> Confirm Submission
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
function AssessmentTestPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const assessmentId = searchParams.get("assessmentId") || "";
  const candidateId = searchParams.get("candidateId") || "";
  const queryRole = searchParams.get("role") || "";

  const { record } = findAssessmentRecord({ assessmentId, candidateId, role: queryRole });
  const [assessmentData, setAssessmentData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState({}); // { questionId: value (option string for MCQ, text string for short_answer) }
  const [flagged, setFlagged] = useState(new Set());
  const [secondsLeft, setSecondsLeft] = useState(TOTAL_SECONDS);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [showQuestionPanel, setShowQuestionPanel] = useState(false);
  const timerRef = useRef(null);

  // Load questions from backend endpoint
  useEffect(() => {
    async function fetchQuestions() {
      setLoading(true);
      setError(null);
      try {
        let targetId = assessmentId;
        if (!targetId && candidateId) {
          targetId = candidateId;
        }

        if (!targetId) {
          setError("No assessment ID or candidate ID provided in URL parameters.");
          setLoading(false);
          return;
        }

        const res = await fetch(`${API_BASE_URL}/api/assessment/questions/${encodeURIComponent(targetId)}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.questions && data.questions.length > 0) {
            setAssessmentData(data);
          } else {
            setError("No questions found for this assessment ID.");
          }
        } else {
          // If direct GET fails, try generating/retrieving endpoint as fallback
          const genRes = await fetch(`${API_BASE_URL}/api/assessment/generate-questions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              assessment_id: targetId,
              candidate_id: candidateId || targetId,
              job_role: queryRole || record?.jobRole || "Engineer"
            })
          });
          if (genRes.ok) {
            const genData = await genRes.json();
            if (genData && genData.questions && genData.questions.length > 0) {
              setAssessmentData(genData);
            } else {
              setError("Failed to load questions for this assessment.");
            }
          } else {
            const errData = await genRes.json().catch(() => ({}));
            setError(errData.detail || "Assessment questions not found or server error.");
          }
        }
      } catch (err) {
        setError(`Failed to connect to backend server: ${err.message}`);
      } finally {
        setLoading(false);
      }
    }

    fetchQuestions();
  }, [assessmentId, candidateId, queryRole, record?.jobRole]);

  const role = assessmentData?.job_role || record?.jobRole || queryRole || "Candidate";
  const questions = assessmentData?.questions || [];
  const total = questions.length;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const performSubmission = useCallback(async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/assessment/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assessment_id: assessmentId || candidateId,
          candidate_id: candidateId || assessmentId,
          role: role,
          answers: answers
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Server rejected submission attempt.");
      }

      setSubmitted(true);
      clearInterval(timerRef.current);
      setShowSubmitModal(false);
      transitionAssessmentStatus({ assessmentId, candidateId, role }, "Completed");
      navigate("/assessment/submitted");
    } catch (err) {
      setSubmitError(err.message || "Failed to submit assessment. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }, [navigate, assessmentId, candidateId, role, answers]);

  const handleAutoSubmit = useCallback(() => {
    performSubmission();
  }, [performSubmission]);

  // Helper function to send observable behavior events to backend
  const logBehaviorEvents = useCallback(async (eventsList) => {
    if (!assessmentId && !candidateId) return;
    try {
      await fetch(`${API_BASE_URL}/api/assessment/behavior-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assessment_id: assessmentId || candidateId,
          candidate_id: candidateId || assessmentId,
          events: eventsList
        })
      });
    } catch (_) {
      // Non-blocking background log
    }
  }, [assessmentId, candidateId]);

  // ─── Camera & Face Detection Monitoring ──────────────────────────────────────
  const cameraVideoRef = useRef(null);
  const cameraCanvasRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const faceDetectorRef = useRef(null);
  const faceIntervalRef = useRef(null);
  const lastFaceEventRef = useRef({ type: null, timestamp: 0 }); // cooldown tracker
  const [cameraActive, setCameraActive] = useState(false);

  const cleanupCamera = useCallback(() => {
    if (faceIntervalRef.current) {
      clearInterval(faceIntervalRef.current);
      faceIntervalRef.current = null;
    }
    if (faceDetectorRef.current) {
      try { faceDetectorRef.current.close(); } catch (_) { }
      faceDetectorRef.current = null;
    }
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((t) => t.stop());
      cameraStreamRef.current = null;
    }
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  // Initialize camera & face detection when assessment is active
  useEffect(() => {
    if (submitted || loading || error || total === 0) return;

    let cancelled = false;

    async function initCameraMonitoring() {
      // Step 1: acquire camera stream
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: "user" },
          audio: false
        });

        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        cameraStreamRef.current = stream;

        if (cameraVideoRef.current) {
          cameraVideoRef.current.srcObject = stream;
          await new Promise((res) => {
            const vid = cameraVideoRef.current;
            if (!vid) { res(); return; }
            vid.onloadedmetadata = res;
            setTimeout(res, 3000);
          });
          if (cameraVideoRef.current) cameraVideoRef.current.play().catch(() => { });
        }

        setCameraActive(true);
        logBehaviorEvents([{ type: "camera_started", timestamp: new Date().toISOString() }]);
      } catch (err) {
        if (cancelled) return;
        const eventType = err.name === "NotAllowedError" || err.name === "PermissionDeniedError"
          ? "camera_permission_denied"
          : "camera_error";
        logBehaviorEvents([{
          type: eventType,
          timestamp: new Date().toISOString(),
          detail: err.message || "Camera unavailable"
        }]);
        return; // cannot proceed without camera
      }

      // Step 2: initialize MediaPipe face detection
      try {
        const FaceDetection = await loadMediaPipeCDN();
        if (cancelled) return;

        const detector = new FaceDetection({
          locateFile: (file) =>
            `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4.1646425229/${file}`
        });
        detector.setOptions({ model: "short", minDetectionConfidence: 0.5 });

        let latestFaceCount = 0;
        detector.onResults((results) => {
          latestFaceCount = (results.detections || []).length;
        });

        faceDetectorRef.current = detector;

        // Wait for video to stabilize
        await new Promise((res) => setTimeout(res, 800));
        if (cancelled) return;

        // Tracking state for the 5-second rule
        const stateRef = {
          current: "unknown",
          absenceStartTime: null
        };

        const evaluateFaceState = (isDetected, sourceName) => {
          const now = Date.now();
          if (isDetected) {
            stateRef.absenceStartTime = null; // reset timer immediately
            if (stateRef.current !== "face_present") {
              stateRef.current = "face_present";
              logBehaviorEvents([{
                type: "face_present",
                timestamp: new Date(now).toISOString(),
                details: sourceName
              }]);
            }
          } else {
            if (stateRef.absenceStartTime === null) {
              stateRef.absenceStartTime = now;
            } else if (now - stateRef.absenceStartTime >= 5000) {
              if (stateRef.current !== "face_absent") {
                stateRef.current = "face_absent";
                logBehaviorEvents([{
                  type: "face_absent",
                  timestamp: new Date(now).toISOString(),
                  duration_seconds: (now - stateRef.absenceStartTime) / 1000,
                  details: sourceName
                }]);
              }
            }
          }
        };

        // Step 3: run detection loop every 1 second
        faceIntervalRef.current = setInterval(async () => {
          if (!cameraVideoRef.current || !cameraStreamRef.current) return;
          if (cameraVideoRef.current.readyState < 2) return;

          try {
            await detector.send({ image: cameraVideoRef.current });
            evaluateFaceState(latestFaceCount > 0, "mediapipe");
          } catch (_) {
            // Transient frame error, retry next tick
          }
        }, 1000);
      } catch (err) {
        // MediaPipe failed to load — fall back to canvas brightness heuristic
        if (cancelled) return;
        console.warn("MediaPipe unavailable for assessment monitoring, using canvas fallback:", err.message);

        const stateRef = {
          current: "unknown",
          absenceStartTime: null
        };

        faceIntervalRef.current = setInterval(() => {
          const video = cameraVideoRef.current;
          const canvas = cameraCanvasRef.current;
          if (!video || !canvas || !cameraStreamRef.current) return;
          if (video.readyState < 2) return;

          const ctx = canvas.getContext("2d");
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          let sum = 0;
          const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
          for (let i = 0; i < data.length; i += 16) {
            sum += (data[i] + data[i + 1] + data[i + 2]) / 3;
          }
          const avgBrightness = sum / (data.length / 16);

          const isDetected = avgBrightness > 8;
          const now = Date.now();
          if (isDetected) {
            stateRef.absenceStartTime = null; // reset timer immediately
            if (stateRef.current !== "face_present") {
              stateRef.current = "face_present";
              logBehaviorEvents([{
                type: "face_present",
                timestamp: new Date(now).toISOString(),
                details: "canvas_fallback"
              }]);
            }
          } else {
            if (stateRef.absenceStartTime === null) {
              stateRef.absenceStartTime = now;
            } else if (now - stateRef.absenceStartTime >= 5000) {
              if (stateRef.current !== "face_absent") {
                stateRef.current = "face_absent";
                logBehaviorEvents([{
                  type: "face_absent",
                  timestamp: new Date(now).toISOString(),
                  duration_seconds: (now - stateRef.absenceStartTime) / 1000,
                  details: "canvas_fallback"
                }]);
              }
            }
          }
        }, 1000);
      }
    }

    initCameraMonitoring();

    return () => {
      cancelled = true;
      cleanupCamera();
    };
  }, [submitted, loading, error, total, logBehaviorEvents, cleanupCamera]);

  // Stop camera when assessment is submitted
  useEffect(() => {
    if (submitted) {
      logBehaviorEvents([{ type: "camera_stopped", timestamp: new Date().toISOString(), reason: "assessment_submitted" }]);
      cleanupCamera();
    }
  }, [submitted, cleanupCamera, logBehaviorEvents]);

  // Page Visibility API Monitoring (tab_hidden / tab_visible)
  const tabHiddenTimeRef = useRef(null);
  useEffect(() => {
    if (submitted || loading || error || total === 0) return;

    function handleVisibilityChange() {
      const nowIso = new Date().toISOString();
      if (document.hidden) {
        tabHiddenTimeRef.current = Date.now();
        logBehaviorEvents([{ type: "tab_hidden", timestamp: nowIso }]);
      } else {
        let duration = undefined;
        if (tabHiddenTimeRef.current) {
          duration = (Date.now() - tabHiddenTimeRef.current) / 1000;
          tabHiddenTimeRef.current = null;
        }
        logBehaviorEvents([
          {
            type: "tab_visible",
            timestamp: nowIso,
            ...(duration !== undefined ? { duration_seconds: duration } : {})
          }
        ]);
      }
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [submitted, loading, error, total, logBehaviorEvents]);

  // Timer countdown
  useEffect(() => {
    if (submitted || loading || error || total === 0) return;
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(timerRef.current);
          handleAutoSubmit();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [submitted, loading, error, total, handleAutoSubmit]);

  if (loading) {
    return (
      <div className="at-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#FAF7F2" }}>
        <div style={{ textAlign: "center", color: "#5C5248" }}>
          <Loader2 size={36} className="at-spinner" style={{ animation: "spin 1s linear infinite", marginBottom: 12 }} />
          <h3 style={{ margin: "0 0 6px 0", fontSize: 18, color: "#2A241F" }}>Loading Assessment...</h3>
          <p style={{ margin: 0, fontSize: 14, color: "#8A7E73" }}>Fetching generated questions</p>
        </div>
      </div>
    );
  }

  if (error || total === 0) {
    return (
      <div className="at-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#FAF7F2" }}>
        <div style={{ textAlign: "center", maxWidth: 460, padding: 32, background: "#FFFFFF", borderRadius: 16, border: "1px solid #E8E2D9", boxShadow: "0 4px 16px rgba(0,0,0,0.06)" }}>
          <AlertTriangle size={40} color="#DC2626" style={{ marginBottom: 12 }} />
          <h3 style={{ margin: "0 0 8px 0", fontSize: 20, color: "#2A241F" }}>Unable to Load Assessment</h3>
          <p style={{ margin: "0 0 20px 0", fontSize: 14, color: "#5C5248", lineHeight: 1.5 }}>
            {error || "No valid questions are available for this assessment ID."}
          </p>
          <button
            onClick={() => navigate("/assessment")}
            style={{
              padding: "10px 20px",
              background: "#2A241F",
              color: "#FFFFFF",
              border: "none",
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            Return to Assessment Overview
          </button>
        </div>
      </div>
    );
  }

  const currentQ = questions[currentIdx];
  const answeredCount = Object.keys(answers).filter(k => answers[k] !== undefined && answers[k] !== "").length;
  const progressPct = Math.round((answeredCount / total) * 100);
  const isLastQuestion = currentIdx === total - 1;
  const timerWarning = secondsLeft <= 300; // last 5 mins
  const timerCritical = secondsLeft <= 60;

  function selectMCQAnswer(optText) {
    setAnswers((prev) => ({ ...prev, [currentQ.id]: optText }));
  }

  function handleShortAnswerChange(text) {
    setAnswers((prev) => ({ ...prev, [currentQ.id]: text }));
  }

  function toggleFlag() {
    setFlagged((prev) => {
      const next = new Set(prev);
      next.has(currentQ.id) ? next.delete(currentQ.id) : next.add(currentQ.id);
      return next;
    });
  }

  function goTo(idx) {
    if (idx >= 0 && idx < total) {
      setCurrentIdx(idx);
      setShowQuestionPanel(false);
    }
  }

  function confirmSubmit() {
    performSubmission();
  }

  function questionPanelClass(idx) {
    const q = questions[idx];
    const isAnswered = answers[q.id] !== undefined && answers[q.id] !== "";
    const isFlagged = flagged.has(q.id);
    const isCurrent = idx === currentIdx;
    let cls = "at-qgrid-btn";
    if (isCurrent) cls += " current";
    else if (isAnswered && isFlagged) cls += " answered-flagged";
    else if (isAnswered) cls += " answered";
    else if (isFlagged) cls += " flagged";
    return cls;
  }

  return (
    <div className="at-shell">
      {/* ── TOP HEADER ───────────────────────────────────────────────────── */}
      <header className="at-header">
        <div className="at-header-left">
          <div className="at-brand-icon">
            <Brain size={18} />
          </div>
          <div className="at-brand-text">
            <span className="at-brand-name">AI Recruiter</span>
            <span className="at-brand-role">{role}</span>
          </div>
        </div>

        <div className="at-header-center">
          {/* Progress bar */}
          <div className="at-header-progress">
            <div className="at-progress-label">
              Question {currentIdx + 1} / {total}
            </div>
            <div className="at-progress-track">
              <div
                className="at-progress-fill"
                style={{ width: `${((currentIdx + 1) / total) * 100}%` }}
              />
            </div>
            <div className="at-progress-answered">
              {answeredCount}/{total} answered
            </div>
          </div>
        </div>

        <div className="at-header-right">
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 20, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#166534", fontSize: 12, fontWeight: 600 }}>
            <ShieldCheck size={14} color="#16A34A" />
            <span>Assessment Monitoring Active</span>
          </div>

          <div className={`at-timer${timerWarning ? " warning" : ""}${timerCritical ? " critical" : ""}`}>
            <Clock size={15} />
            <span>{formatTime(secondsLeft)}</span>
          </div>

          <button
            className="at-qpanel-toggle"
            onClick={() => setShowQuestionPanel((v) => !v)}
            aria-label="Toggle question panel"
          >
            <BookOpen size={15} />
            <span>Questions</span>
          </button>
        </div>
      </header>

      {/* ── QUESTION GRID PANEL (slide-down) ─────────────────────────────── */}
      {showQuestionPanel && (
        <div className="at-qpanel">
          <div className="at-qpanel-inner">
            <div className="at-qpanel-header">
              <span>Jump to Question</span>
              <button className="at-qpanel-close" onClick={() => setShowQuestionPanel(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="at-qgrid">
              {questions.map((q, i) => (
                <button
                  key={q.id || i}
                  className={questionPanelClass(i)}
                  onClick={() => goTo(i)}
                  aria-label={`Question ${i + 1}`}
                >
                  {i + 1}
                  {flagged.has(q.id) && <span className="at-qgrid-flag">⚑</span>}
                </button>
              ))}
            </div>
            <div className="at-qpanel-legend">
              <span className="at-legend-item"><span className="at-legend-dot answered" />Answered</span>
              <span className="at-legend-item"><span className="at-legend-dot flagged" />Flagged</span>
              <span className="at-legend-item"><span className="at-legend-dot current" />Current</span>
              <span className="at-legend-item"><span className="at-legend-dot unanswered" />Not answered</span>
            </div>
          </div>
        </div>
      )}

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <div className="at-main">
        {/* LEFT: Question panel */}
        <section className="at-question-section">
          {/* Meta bar */}
          <div className="at-question-meta">
            <span className="at-meta-q-num">Q{currentIdx + 1}</span>
            <span className="at-meta-topic">
              <BookOpen size={13} />
              {currentQ.skill || "Technical Skill"}
            </span>
            <span className={`at-meta-diff ${difficultyColor(currentQ.difficulty)}`}>
              <BarChart2 size={13} />
              {currentQ.difficulty || "medium"}
            </span>
            <button
              className={`at-flag-btn${flagged.has(currentQ.id) ? " flagged" : ""}`}
              onClick={toggleFlag}
              title={flagged.has(currentQ.id) ? "Remove flag" : "Flag for review"}
            >
              <Flag size={14} />
              {flagged.has(currentQ.id) ? "Flagged" : "Flag"}
            </button>
          </div>

          {/* Question text */}
          <div className="at-question-body">
            <p className="at-question-text">{currentQ.question}</p>
          </div>

          {/* Answer input rendering: MCQ vs Short Answer */}
          {currentQ.type === "mcq" ? (
            <div className="at-options-list">
              {(currentQ.options || []).map((opt, i) => {
                const selected = answers[currentQ.id] === opt;
                return (
                  <button
                    key={i}
                    className={`at-option${selected ? " selected" : ""}`}
                    onClick={() => selectMCQAnswer(opt)}
                  >
                    <span className="at-option-letter">
                      {String.fromCharCode(65 + i)}
                    </span>
                    <span className="at-option-text">{opt}</span>
                    {selected && <CheckCircle2 size={18} className="at-option-check" />}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="at-short-answer-wrap" style={{ marginTop: 16 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#5C5248", marginBottom: 8 }}>
                Your Answer (Short Answer):
              </label>
              <textarea
                value={answers[currentQ.id] || ""}
                onChange={(e) => handleShortAnswerChange(e.target.value)}
                placeholder="Type your answer here in detail..."
                rows={6}
                style={{
                  width: "100%",
                  padding: 14,
                  fontSize: 14,
                  lineHeight: 1.5,
                  borderRadius: 10,
                  border: "1px solid #DED7CD",
                  backgroundColor: "#FFFFFF",
                  fontFamily: "inherit",
                  resize: "vertical",
                  boxSizing: "border-box",
                  outline: "none"
                }}
              />
            </div>
          )}

          {/* Navigation */}
          <div className="at-nav-row">
            <button
              className="at-nav-btn prev"
              onClick={() => goTo(currentIdx - 1)}
              disabled={currentIdx === 0}
            >
              <ChevronLeft size={18} />
              Previous
            </button>

            <div className="at-nav-center">
              {answers[currentQ.id] !== undefined && answers[currentQ.id] !== "" && (
                <span className="at-nav-answered-badge">
                  <CheckCircle2 size={13} /> Answered
                </span>
              )}
            </div>

            {isLastQuestion ? (
              <button
                className="at-nav-btn submit-btn"
                onClick={() => setShowSubmitModal(true)}
              >
                <Send size={16} />
                Submit Assessment
              </button>
            ) : (
              <button
                className="at-nav-btn next"
                onClick={() => goTo(currentIdx + 1)}
              >
                Next
                <ChevronRight size={18} />
              </button>
            )}
          </div>
        </section>

        {/* RIGHT: Status sidebar */}
        <aside className="at-sidebar">
          {/* Overall progress */}
          <div className="at-sidebar-card">
            <div className="at-sidebar-card-title">Progress</div>
            <div className="at-sidebar-progress-ring-wrap">
              {/* CSS ring chart */}
              <div
                className="at-ring"
                style={{ "--pct": `${progressPct}` }}
              >
                <span className="at-ring-label">{progressPct}%</span>
              </div>
            </div>
            <div className="at-sidebar-stats">
              <div className="at-sidebar-stat">
                <CheckCircle2 size={14} className="at-stat-icon answered" />
                <span>{answeredCount} answered</span>
              </div>
              <div className="at-sidebar-stat">
                <Circle size={14} className="at-stat-icon unanswered" />
                <span>{total - answeredCount} remaining</span>
              </div>
              {flagged.size > 0 && (
                <div className="at-sidebar-stat">
                  <Flag size={14} className="at-stat-icon flagged" />
                  <span>{flagged.size} flagged</span>
                </div>
              )}
            </div>
          </div>

          {/* Mini question map */}
          <div className="at-sidebar-card">
            <div className="at-sidebar-card-title">Question Map</div>
            <div className="at-qmap">
              {questions.map((q, i) => (
                <button
                  key={q.id || i}
                  className={questionPanelClass(i)}
                  onClick={() => goTo(i)}
                  title={`Question ${i + 1} — ${q.skill || "Technical Skill"}`}
                >
                  {i + 1}
                  {flagged.has(q.id) && <span className="at-qgrid-flag">⚑</span>}
                </button>
              ))}
            </div>
            <div className="at-qmap-legend">
              <span className="at-legend-item"><span className="at-legend-dot answered" />Done</span>
              <span className="at-legend-item"><span className="at-legend-dot flagged" />Flag</span>
              <span className="at-legend-item"><span className="at-legend-dot current" />Now</span>
            </div>
          </div>

          {/* Camera monitoring preview */}
          <div className="at-sidebar-card">
            <div className="at-sidebar-card-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Camera size={14} />
              <span>Monitoring</span>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: cameraActive ? "#16A34A" : "#9CA3AF",
                  display: "inline-block",
                  marginLeft: "auto",
                  boxShadow: cameraActive ? "0 0 6px rgba(22,163,106,0.5)" : "none"
                }}
                title={cameraActive ? "Camera active" : "Camera inactive"}
              />
            </div>
            <div style={{
              width: "100%",
              borderRadius: 8,
              overflow: "hidden",
              background: "#1A1A1A",
              position: "relative",
              aspectRatio: "4/3"
            }}>
              <video
                ref={cameraVideoRef}
                muted
                playsInline
                autoPlay
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transform: "scaleX(-1)",
                  display: cameraActive ? "block" : "none"
                }}
              />
              {!cameraActive && (
                <div style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#6B7280",
                  fontSize: 11,
                  gap: 4
                }}>
                  <Camera size={20} />
                  <span>Connecting...</span>
                </div>
              )}
            </div>
            {/* Hidden canvas for fallback brightness detection */}
            <canvas
              ref={cameraCanvasRef}
              width={160}
              height={120}
              style={{ display: "none" }}
            />
          </div>

          {/* Submit shortcut */}
          <button
            className="at-sidebar-submit-btn"
            onClick={() => setShowSubmitModal(true)}
          >
            <Send size={15} />
            Submit Assessment
          </button>
        </aside>
      </div>

      {/* ── SUBMIT MODAL ─────────────────────────────────────────────────── */}
      {showSubmitModal && (
        <SubmitModal
          answered={answeredCount}
          total={total}
          onConfirm={confirmSubmit}
          onCancel={() => setShowSubmitModal(false)}
          isSubmitting={isSubmitting}
          submitError={submitError}
        />
      )}
    </div>
  );
}

export default AssessmentTestPage;
