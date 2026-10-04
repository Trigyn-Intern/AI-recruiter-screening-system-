import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Brain,
  ShieldCheck,
  Camera,
  Mic,
  Wifi,
  Monitor,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
  ArrowLeft,
  User,
  AlertTriangle,
  RefreshCw
} from "lucide-react";
import "./assessment.css";
import "./systemCheck.css";

// Status constants
const STATUS = {
  IDLE: "idle",
  CHECKING: "checking",
  PASS: "pass",
  FAIL: "fail"
};

// Browser compatibility check
function getBrowserInfo() {
  const ua = navigator.userAgent;
  let name = "Unknown";
  let version = "";

  if (/Edg\//.test(ua)) {
    name = "Microsoft Edge";
    version = ua.match(/Edg\/([\d.]+)/)?.[1] || "";
  } else if (/Chrome\//.test(ua) && !/Chromium\//.test(ua)) {
    name = "Google Chrome";
    version = ua.match(/Chrome\/([\d.]+)/)?.[1] || "";
  } else if (/Firefox\//.test(ua)) {
    name = "Mozilla Firefox";
    version = ua.match(/Firefox\/([\d.]+)/)?.[1] || "";
  } else if (/Safari\//.test(ua) && !/Chrome\//.test(ua)) {
    name = "Safari";
    version = ua.match(/Version\/([\d.]+)/)?.[1] || "";
  } else if (/Chromium\//.test(ua)) {
    name = "Chromium";
    version = ua.match(/Chromium\/([\d.]+)/)?.[1] || "";
  }

  const majorVersion = parseInt(version.split(".")[0], 10) || 0;
  const supported =
    (name === "Google Chrome" && majorVersion >= 90) ||
    (name === "Mozilla Firefox" && majorVersion >= 88) ||
    (name === "Microsoft Edge" && majorVersion >= 90) ||
    (name === "Safari" && majorVersion >= 14) ||
    (name === "Chromium" && majorVersion >= 90);

  return { name, version: version.split(".")[0], supported };
}

// Lazy-load MediaPipe face detection via CDN script tag
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

import { useSearchParams } from "react-router-dom";
import { transitionAssessmentStatus } from "../../utils/assessmentStore";

function SystemCheckPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const assessmentId = searchParams.get("assessmentId") || "";
  const candidateId = searchParams.get("candidateId") || "";
  const role = searchParams.get("role") || "";

  const handleStartAssessment = () => {
    transitionAssessmentStatus({ assessmentId, candidateId, role }, "In Progress");
    const q = new URLSearchParams({
      ...(assessmentId ? { assessmentId } : {}),
      ...(candidateId ? { candidateId } : {}),
      ...(role ? { role } : {})
    }).toString();
    navigate(`/assessment/test?${q}`);
  };

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const faceDetectorRef = useRef(null);
  const detectionIntervalRef = useRef(null);

  const [camStatus, setCamStatus] = useState(STATUS.IDLE);
  const [camMessage, setCamMessage] = useState("Click 'Run System Checks' to start");
  const [faceStatus, setFaceStatus] = useState(STATUS.IDLE);
  const [faceMessage, setFaceMessage] = useState("Waiting for camera...");
  const [micStatus, setMicStatus] = useState(STATUS.IDLE);
  const [micMessage, setMicMessage] = useState("Waiting...");
  const [netStatus, setNetStatus] = useState(STATUS.IDLE);
  const [netMessage, setNetMessage] = useState("Waiting...");
  const [browserStatus, setBrowserStatus] = useState(STATUS.IDLE);
  const [browserMessage, setBrowserMessage] = useState("Waiting...");
  const [browserName, setBrowserName] = useState("");
  const [checksStarted, setChecksStarted] = useState(false);
  const [allChecksRan, setAllChecksRan] = useState(false);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopMediaStreams();
      if (detectionIntervalRef.current) clearInterval(detectionIntervalRef.current);
    };
  }, []);

  function stopMediaStreams() {
    if (detectionIntervalRef.current) {
      clearInterval(detectionIntervalRef.current);
      detectionIntervalRef.current = null;
    }
    if (faceDetectorRef.current) {
      try { faceDetectorRef.current.close(); } catch (_) {}
      faceDetectorRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  // Canvas-based face heuristic fallback
  function startCanvasFallback() {
    detectionIntervalRef.current = setInterval(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || !streamRef.current) return;
      if (video.readyState < 2) return;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      let sum = 0;
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 0; i < data.length; i += 16) {
        sum += (data[i] + data[i + 1] + data[i + 2]) / 3;
      }
      const avgBrightness = sum / (data.length / 16);
      if (avgBrightness > 8) {
        setFaceStatus(STATUS.PASS);
        setFaceMessage("Camera stream active — ensure your face is clearly visible");
      }
    }, 1500);
  }

  const startFaceDetection = useCallback(async () => {
    setFaceStatus(STATUS.CHECKING);
    setFaceMessage("Loading face detection model...");

    try {
      const FaceDetection = await loadMediaPipeCDN();
      const detector = new FaceDetection({
        locateFile: (file) =>
          `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4.1646425229/${file}`
      });
      detector.setOptions({ model: "short", minDetectionConfidence: 0.5 });

      let latestCount = 0;
      detector.onResults((results) => {
        latestCount = (results.detections || []).length;
      });

      faceDetectorRef.current = detector;

      // Wait for video to be ready
      await new Promise((res) => setTimeout(res, 600));

      detectionIntervalRef.current = setInterval(async () => {
        if (!videoRef.current || !streamRef.current) return;
        if (videoRef.current.readyState < 2) return;
        try {
          await detector.send({ image: videoRef.current });
          if (latestCount > 0) {
            setFaceStatus(STATUS.PASS);
            setFaceMessage("Face detected — you are visible");
          } else {
            setFaceStatus(STATUS.FAIL);
            setFaceMessage("No face detected — please position yourself in the camera frame");
          }
        } catch (_) {
          // Transient frame error, retry next tick
        }
      }, 900);
    } catch (err) {
      console.warn("MediaPipe unavailable, using canvas fallback:", err.message);
      setFaceStatus(STATUS.FAIL);
      setFaceMessage("Face detection model unavailable — please ensure you are visible in the camera");
      startCanvasFallback();
    }
  }, []);

  const runCameraCheck = useCallback(async () => {
    setCamStatus(STATUS.CHECKING);
    setCamMessage("Requesting camera permission...");
    setFaceStatus(STATUS.CHECKING);
    setFaceMessage("Waiting for camera...");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await new Promise((res, rej) => {
          const vid = videoRef.current;
          vid.onloadedmetadata = res;
          vid.onerror = rej;
          setTimeout(res, 3000); // safety timeout
        });
        videoRef.current.play().catch(() => {});
      }

      setCamStatus(STATUS.PASS);
      setCamMessage("Camera connected and ready");

      // Start face detection after camera is live
      startFaceDetection();
    } catch (err) {
      const denied = err.name === "NotAllowedError" || err.name === "PermissionDeniedError";
      setCamStatus(STATUS.FAIL);
      setCamMessage(
        denied
          ? "Camera permission denied — please allow camera access in browser settings"
          : "Camera not found or not accessible on this device"
      );
      setFaceStatus(STATUS.FAIL);
      setFaceMessage("Cannot run face detection without camera access");
    }
  }, [startFaceDetection]);

  const runMicCheck = useCallback(async () => {
    setMicStatus(STATUS.CHECKING);
    setMicMessage("Requesting microphone permission...");

    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      micStream.getTracks().forEach((t) => t.stop());
      setMicStatus(STATUS.PASS);
      setMicMessage("Microphone connected and available");
    } catch (err) {
      const denied = err.name === "NotAllowedError" || err.name === "PermissionDeniedError";
      setMicStatus(STATUS.FAIL);
      setMicMessage(
        denied
          ? "Microphone permission denied — please allow microphone access in browser settings"
          : "Microphone not found or not accessible on this device"
      );
    }
  }, []);

  const runNetworkCheck = useCallback(() => {
    setNetStatus(STATUS.CHECKING);
    setNetMessage("Checking network connection...");
    setTimeout(() => {
      const online = navigator.onLine;
      setNetStatus(online ? STATUS.PASS : STATUS.FAIL);
      setNetMessage(online ? "Network available" : "No network connection detected");
    }, 500);
  }, []);

  const runBrowserCheck = useCallback(() => {
    setBrowserStatus(STATUS.CHECKING);
    setBrowserMessage("Checking browser compatibility...");
    setTimeout(() => {
      const info = getBrowserInfo();
      setBrowserName(`${info.name} ${info.version}`);
      setBrowserStatus(info.supported ? STATUS.PASS : STATUS.FAIL);
      setBrowserMessage(
        info.supported
          ? `${info.name} ${info.version} — browser is supported`
          : `${info.name} may have limited support — we recommend Chrome, Edge, or Firefox`
      );
    }, 400);
  }, []);

  const runAllChecks = useCallback(async () => {
    setChecksStarted(true);
    setAllChecksRan(false);
    stopMediaStreams();

    // Reset
    setCamStatus(STATUS.IDLE);
    setFaceStatus(STATUS.IDLE);
    setMicStatus(STATUS.IDLE);
    setNetStatus(STATUS.IDLE);
    setBrowserStatus(STATUS.IDLE);
    setCamMessage("Requesting camera permission...");
    setFaceMessage("Waiting for camera...");
    setMicMessage("Waiting...");
    setNetMessage("Waiting...");
    setBrowserMessage("Waiting...");

    // Run concurrent non-camera checks immediately
    runNetworkCheck();
    runBrowserCheck();

    // Camera + mic sequentially (camera first since face detection depends on it)
    await runCameraCheck();
    await runMicCheck();

    setAllChecksRan(true);
  }, [runCameraCheck, runMicCheck, runNetworkCheck, runBrowserCheck]);

  const requiredPassed =
    camStatus === STATUS.PASS &&
    micStatus === STATUS.PASS &&
    netStatus === STATUS.PASS &&
    browserStatus === STATUS.PASS;

  const isRunning =
    camStatus === STATUS.CHECKING ||
    micStatus === STATUS.CHECKING;

  function StatusIcon({ status, size = 20 }) {
    if (status === STATUS.CHECKING) return <Loader2 size={size} className="spin sc-icon-checking" />;
    if (status === STATUS.PASS) return <CheckCircle2 size={size} className="sc-icon-pass" />;
    if (status === STATUS.FAIL) return <XCircle size={size} className="sc-icon-fail" />;
    return <span className="sc-icon-idle" style={{ width: size, height: size, display: "inline-block" }} />;
  }

  function rowClass(status) {
    if (status === STATUS.PASS) return "sc-check-row pass";
    if (status === STATUS.FAIL) return "sc-check-row fail";
    if (status === STATUS.CHECKING) return "sc-check-row checking";
    return "sc-check-row";
  }

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
              Step 2 of 3 — System Check
            </span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="assessment-container">
        {/* Hero */}
        <div className="assessment-hero">
          <span className="assessment-hero-tag">Device Readiness</span>
          <h2>System Check</h2>
          <p>Let's make sure your device is ready before starting the assessment.</p>
        </div>

        {/* Stepper */}
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

        {/* Webcam + Face Detection Card */}
        <div className="assessment-card sc-card">
          <div className="assessment-card-header sc-card-header">
            <div className="sc-section-title">
              <Camera size={18} />
              <span>Webcam &amp; Face Detection</span>
            </div>
            <p className="sc-section-hint">
              Your camera is required for assessment monitoring. Camera access will
              only be used during this assessment session and no frames are recorded or stored.
            </p>
          </div>

          <div className="sc-camera-body">
            {/* Live preview */}
            <div className="sc-video-wrapper">
              <video
                ref={videoRef}
                className="sc-video"
                muted
                playsInline
                autoPlay
              />
              <canvas
                ref={canvasRef}
                className="sc-canvas-hidden"
                width={160}
                height={120}
              />
              {/* Overlay states when no live feed */}
              {camStatus !== STATUS.PASS && (
                <div className={`sc-video-overlay${camStatus === STATUS.FAIL ? " sc-video-error" : ""}`}>
                  {camStatus === STATUS.CHECKING ? (
                    <>
                      <Loader2 size={30} className="spin sc-placeholder-icon" />
                      <p>Connecting camera...</p>
                    </>
                  ) : camStatus === STATUS.FAIL ? (
                    <>
                      <XCircle size={32} className="sc-icon-fail" />
                      <p>Camera unavailable</p>
                    </>
                  ) : (
                    <>
                      <Camera size={36} className="sc-placeholder-icon" />
                      <p>Camera preview will appear here</p>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Camera + Face rows */}
            <div className="sc-checks-panel">
              <div className={rowClass(camStatus)}>
                <StatusIcon status={camStatus} />
                <div className="sc-check-info">
                  <span className="sc-check-label">
                    <Camera size={14} /> Camera
                  </span>
                  <span className="sc-check-msg">{camMessage}</span>
                </div>
              </div>

              <div className={rowClass(faceStatus)}>
                <StatusIcon status={faceStatus} />
                <div className="sc-check-info">
                  <span className="sc-check-label">
                    <User size={14} /> Face Detection
                  </span>
                  <span className="sc-check-msg">{faceMessage}</span>
                </div>
              </div>

              <div className="sc-privacy-note">
                <AlertTriangle size={12} />
                <span>
                  No video is recorded. Face detection runs locally in your browser.
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Device Checks Card */}
        <div className="assessment-card sc-card">
          <div className="assessment-card-header sc-card-header">
            <div className="sc-section-title">
              <Monitor size={18} />
              <span>Device &amp; Network Checks</span>
            </div>
          </div>

          <div className="sc-device-checks">
            <div className={rowClass(micStatus)}>
              <StatusIcon status={micStatus} />
              <div className="sc-check-info">
                <span className="sc-check-label"><Mic size={14} /> Microphone</span>
                <span className="sc-check-msg">{micMessage}</span>
              </div>
            </div>

            <div className={rowClass(netStatus)}>
              <StatusIcon status={netStatus} />
              <div className="sc-check-info">
                <span className="sc-check-label"><Wifi size={14} /> Network</span>
                <span className="sc-check-msg">{netMessage}</span>
              </div>
            </div>

            <div className={rowClass(browserStatus)}>
              <StatusIcon status={browserStatus} />
              <div className="sc-check-info">
                <span className="sc-check-label">
                  <Monitor size={14} /> Browser
                  {browserName && <span className="sc-browser-badge">{browserName}</span>}
                </span>
                <span className="sc-check-msg">{browserMessage}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Readiness Summary */}
        <div className={`sc-readiness-bar ${requiredPassed ? "ready" : allChecksRan ? "not-ready" : "neutral"}`}>
          {requiredPassed ? (
            <>
              <CheckCircle2 size={22} className="sc-readiness-icon" />
              <div className="sc-readiness-text">
                <strong>System Check Complete</strong>
                <span>All required checks passed. You are ready to begin.</span>
              </div>
            </>
          ) : allChecksRan ? (
            <>
              <XCircle size={22} className="sc-readiness-icon" />
              <div className="sc-readiness-text">
                <strong>Please complete the required checks</strong>
                <span>Resolve the issues flagged above, then re-run the checks.</span>
              </div>
            </>
          ) : (
            <>
              <ShieldCheck size={22} className="sc-readiness-icon" />
              <div className="sc-readiness-text">
                <strong>System check not started</strong>
                <span>Click "Run System Checks" to verify your device is ready.</span>
              </div>
            </>
          )}
        </div>

        {/* Action Buttons */}
        <div className="sc-action-row">
          <button
            type="button"
            className="help-button"
            onClick={() => navigate("/assessment/start")}
          >
            <ArrowLeft size={16} />
            Back to Overview
          </button>

          <div className="sc-right-actions">
            <button
              type="button"
              className="sc-rerun-btn"
              onClick={runAllChecks}
              disabled={isRunning}
            >
              {isRunning ? (
                <Loader2 size={15} className="spin" />
              ) : (
                <RefreshCw size={15} />
              )}
              {checksStarted ? "Re-run Checks" : "Run System Checks"}
            </button>

            <button
              type="button"
              className="proceed-btn"
              disabled={!requiredPassed}
              onClick={handleStartAssessment}
            >
              <span>Start Assessment</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>

        {!checksStarted && (
          <p className="btn-disabled-hint" style={{ textAlign: "center" }}>
            Click "Run System Checks" to begin verifying your device.
          </p>
        )}
        {checksStarted && !requiredPassed && allChecksRan && (
          <p className="btn-disabled-hint" style={{ textAlign: "center" }}>
            Resolve the failed checks above, then click "Re-run Checks" before continuing.
          </p>
        )}
      </main>

      {/* Footer */}
      <footer className="assessment-footer">
        © {new Date().getFullYear()} AI Recruiter Screening System. All rights reserved.
      </footer>
    </div>
  );
}

export default SystemCheckPage;
