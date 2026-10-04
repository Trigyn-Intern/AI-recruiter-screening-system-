import React, { useState, useEffect, useMemo } from "react";
import {
  Search,
  CheckCircle2,
  XCircle,
  Copy,
  ExternalLink,
  PlusCircle,
  Clock,
  HelpCircle,
  Briefcase,
  Award,
  Loader2,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  Check,
  Users,
  X,
  FileText,
  BarChart2,
  AlertTriangle,
  RotateCcw,
  Trash2
} from "lucide-react";
import "./assessmentManagement.css";
import { findAssessmentRecord } from "../../utils/assessmentStore";

const API_BASE_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "recruiter.assessment_records";

// Helper function to format candidate name cleanly
function cleanCandidateName(rawName) {
  if (!rawName) return "Candidate";
  let name = String(rawName);
  name = name.replace(/\.(pdf|docx?|txt)$/i, "");
  if (name.includes("_") || name.toLowerCase().includes("resume")) {
    name = name.replace(/_Resume.*$/i, "").replace(/_/g, " ");
  }
  return name.trim() || rawName;
}

function AssessmentManagementPage({ result }) {
  const [shortlists, setShortlists] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [copiedId, setCopiedId] = useState(null);
  const [viewingResult, setViewingResult] = useState(null);
  const [removedKeys, setRemovedKeys] = useState(() => {
    try {
      const saved = localStorage.getItem("recruiter.assessment_removed_candidates");
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [records, setRecords] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const userJson = localStorage.getItem("recruiter.user");
  const user = userJson ? JSON.parse(userJson) : null;
  const userId = user?.id || user?.email || "demo_user";

  // Load shortlists from API
  const loadShortlists = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/shortlists?user_id=${encodeURIComponent(userId)}`
      );
      if (response.ok) {
        const data = await response.json();
        setShortlists(data.shortlists || []);
      }
    } catch (err) {
      console.error("Failed to load shortlists for assessment page:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadShortlists();
  }, []);

  // Handle individual candidate removal from Assessment Management view & localStorage
  const handleRemoveCandidate = (candKey, candidateName, resumeId) => {
    const targetResumeId = resumeId || candKey;
    const confirmed = window.confirm(
      `Remove ${candidateName || "this candidate"} from assessments?`
    );
    if (!confirmed) return;

    // 1. Remove selected candidate record from localStorage assessment records
    const updatedRecords = { ...records };
    delete updatedRecords[candKey];
    delete updatedRecords[targetResumeId];
    setRecords(updatedRecords);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedRecords));
    } catch (err) {
      console.error("Failed to update assessment records in localStorage:", err);
    }

    // 2. Add targetResumeId to recruiter.assessment_removed_candidates in localStorage
    try {
      const savedRemoved = localStorage.getItem("recruiter.assessment_removed_candidates");
      const removedArr = savedRemoved ? JSON.parse(savedRemoved) : [];
      if (!removedArr.includes(String(targetResumeId))) {
        removedArr.push(String(targetResumeId));
        localStorage.setItem("recruiter.assessment_removed_candidates", JSON.stringify(removedArr));
      }
    } catch (err) {
      console.error("Failed to update removed assessment candidates in localStorage:", err);
    }

    // 3. Add candidate key/resumeId to removedKeys set so card disappears immediately
    setRemovedKeys((prev) => {
      const next = new Set(prev);
      next.add(String(candKey));
      next.add(String(targetResumeId));
      return next;
    });
  };

  // Save records to localStorage on change
  const updateRecords = (newRecords) => {
    setRecords(newRecords);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newRecords));
    } catch (err) {
      console.error("Failed to persist assessment records:", err);
    }
  };

  // Consolidate shortlisted candidates into assessment candidates list (deduplicated by stable resume_id)
  const candidateList = useMemo(() => {
    const list = [];
    const seenResumeIds = new Set();

    // Helper to add candidate if not removed and not already seen
    const processCandidate = (cand, jobRole, shortlistId) => {
      const rId = String(cand.resume_id || cand.candidateId || cand.key || "").trim();
      if (!rId) return;

      // Filter out explicitly removed candidates
      if (removedKeys.has(rId)) return;

      // STABLE DEDUPLICATION BY RESUME_ID
      if (seenResumeIds.has(rId)) return;
      seenResumeIds.add(rId);

      list.push({
        key: rId,
        resume_id: rId,
        candidate_name: cleanCandidateName(
          cand.candidate_name || cand.resume_name || cand.candidateName || rId
        ),
        job_role: jobRole || cand.job_role || cand.jobRole || "Not Specified",
        match_score: cand.match_score || cand.score || 0,
        fit: cand.match_position || cand.fit || "Good Fit",
        shortlist_id: shortlistId || cand.shortlist_id || cand.shortlistId || "default",
        shortlist_status: "Shortlisted"
      });
    };

    // A. Add candidates from backend shortlists (fetched from /api/shortlists)
    if (shortlists && shortlists.length > 0) {
      shortlists.forEach((sl) => {
        const jd = sl.job_description || {};
        const jdTitle =
          jd.job_title ||
          jd.title ||
          jd.role ||
          jd.position ||
          jd.job_role ||
          "Not Specified";
        const candidates = sl.candidates || sl.shortlisted_candidates || [];
        candidates.forEach((cand) => processCandidate(cand, jdTitle, sl.shortlist_id));
      });
    }

    // B. Add candidates from localStorage assessment records (records)
    if (records) {
      Object.entries(records).forEach(([recKey, rec]) => {
        const rId = String(rec.candidateId || rec.resume_id || recKey).trim();
        if (rId && !seenResumeIds.has(rId) && !removedKeys.has(rId)) {
          processCandidate(
            {
              resume_id: rId,
              candidate_name: rec.candidateName || rec.candidate_name || rId,
              match_score: rec.match_score || 85,
              fit: rec.fit || "Good Fit",
            },
            rec.jobRole || rec.job_role || "Not Specified",
            rec.shortlistId || rec.shortlist_id || "default"
          );
        }
      });
    }

    return list;
  }, [shortlists, records, removedKeys]);

  // Listen for storage events (e.g., candidate starts or completes test in another tab)
  useEffect(() => {
    const handleStorageChange = () => {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          setRecords(JSON.parse(saved));
        }
      } catch (err) {
        console.error("Error re-syncing assessment records:", err);
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

// Helper to check if a value is a non-empty, valid assessment ID
function isValidId(val) {
  if (!val) return false;
  const str = String(val).trim().toLowerCase();
  return str !== "" && str !== "undefined" && str !== "null";
}

// Helper to resolve exact assessment ID matching backend question & attempt storage
function resolveAssessmentId(cand, record) {
  if (record && isValidId(record.assessmentId)) {
    return record.assessmentId;
  }
  if (record && isValidId(record.key)) {
    return record.key;
  }
  if (cand && isValidId(cand.resume_id)) {
    return cand.resume_id;
  }
  if (cand && isValidId(cand.key)) {
    return cand.key;
  }
  if (record && isValidId(record.candidateId)) {
    return record.candidateId;
  }
  return "";
}

  // Handle Link Generation for Assessment
  const handleGenerateLink = (candKey, cand) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const assessmentId = resolveAssessmentId(cand, records[candKey]);
    const generatedUrl = `${origin}/assessment/start?assessmentId=${encodeURIComponent(assessmentId)}&candidateId=${encodeURIComponent(cand.resume_id)}&role=${encodeURIComponent(cand.job_role)}`;

    const nextRecords = {
      ...records,
      [candKey]: {
        ...(records[candKey] || {}),
        assessmentId,
        candidateId: cand.resume_id,
        candidateName: cand.candidate_name,
        jobRole: cand.job_role,
        shortlistId: cand.shortlist_id,
        status: "Ready to Share",
        generatedLink: generatedUrl,
        duration: "45 Mins",
        questionCount: "15 Questions",
        createdAt: records[candKey]?.createdAt || new Date().toISOString(),
        linkGeneratedAt: new Date().toISOString()
      }
    };
    updateRecords(nextRecords);
  };

  // Handle Copy Link
  const handleCopyLink = (candKey, linkText) => {
    navigator.clipboard.writeText(linkText);
    setCopiedId(candKey);
    setTimeout(() => {
      setCopiedId(null);
    }, 2500);
  };

  // Handle Manual Status Change
  const handleStatusChange = (candKey, newStatus) => {
    const nextRecords = {
      ...records,
      [candKey]: {
        ...(records[candKey] || {}),
        status: newStatus
      }
    };
    updateRecords(nextRecords);
  };

  // Handle Score / Result View
  const handleViewResults = async (candKey, cand) => {
    const record = getCandidateRecord(cand);
    const assessmentId = resolveAssessmentId(cand, record);

    console.log("[RESULT VIEWER] candidate resume_id:", cand?.resume_id || candKey);
    console.log("[RESULT VIEWER] shortlist_id:", cand?.shortlist_id || record?.shortlistId);
    console.log("[RESULT VIEWER] assessment record:", record);
    console.log("[RESULT VIEWER] resolved assessment_id:", assessmentId);

    setViewingResult({
      candKey,
      candidateName: cand.candidate_name,
      jobRole: cand.job_role,
      status: record.status || "Completed",
      submittedAt: record.submittedAt || null,
      loading: true,
      error: null,
      data: null
    });

    try {
      const res = await fetch(`${API_BASE_URL}/api/assessment/score/${encodeURIComponent(assessmentId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to fetch assessment score (HTTP ${res.status}).`);
      }

      const data = await res.json();
      setViewingResult((prev) => ({
        ...prev,
        loading: false,
        data: data
      }));
    } catch (err) {
      setViewingResult((prev) => ({
        ...prev,
        loading: false,
        error: err.message || "Could not fetch score results."
      }));
    }
  };

  // Helper to resolve record for a candidate cleanly
  const getCandidateRecord = (cand) => {
    const { record } = findAssessmentRecord({
      assessmentId: cand.key,
      candidateId: cand.resume_id,
      role: cand.job_role,
    });
    return record || records[cand.key] || {};
  };

  // Filtered Candidate List
  const filteredCandidates = candidateList.filter((cand) => {
    const record = getCandidateRecord(cand);
    const status = record.status || "Not Created";

    const matchesSearch =
      cand.candidate_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cand.job_role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      cand.resume_id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "Ready to Share"
        ? status === "Ready to Share" || status === "Created" || status === "Link Generated"
        : status === statusFilter);

    return matchesSearch && matchesStatus;
  });

  // Calculate Overview Stats derived STRICTLY from currently active candidates
  const activeRecords = candidateList.map((cand) => getCandidateRecord(cand));

  const totalCount = candidateList.length;
  const createdCount = activeRecords.filter(
    (r) => r.status === "Ready to Share" || r.status === "Created" || r.status === "Link Generated" || r.status === "In Progress" || r.status === "Completed"
  ).length;
  const linksCount = activeRecords.filter(
    (r) => r.status === "Ready to Share" || r.status === "Link Generated" || r.status === "In Progress" || r.status === "Completed"
  ).length;
  const completedCount = activeRecords.filter(
    (r) => r.status === "Completed"
  ).length;

  return (
    <div className="assessment-mgmt-container">
      {/* 1. Page Header */}
      <div className="assessment-mgmt-header">
        <div className="header-text-block">
          <h2>Assessments</h2>
          <p>Manage online assessments for your shortlisted candidates.</p>
        </div>
        <div className="header-badge-pill">
          <ShieldCheck size={16} />
          <span>Recruiter Assessment Hub</span>
        </div>
      </div>

      {/* 2. Summary Statistics Cards */}
      <div className="assessment-stats-grid">
        <div className="assessment-stat-card">
          <div className="stat-icon-wrapper purple">
            <Users size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-value">{totalCount}</span>
            <span className="stat-label">Eligible Candidates</span>
          </div>
        </div>

        <div className="assessment-stat-card">
          <div className="stat-icon-wrapper blue">
            <PlusCircle size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-value">{createdCount}</span>
            <span className="stat-label">Assessments Created</span>
          </div>
        </div>

        <div className="assessment-stat-card">
          <div className="stat-icon-wrapper amber">
            <Sparkles size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-value">{linksCount}</span>
            <span className="stat-label">Links Generated</span>
          </div>
        </div>

        <div className="assessment-stat-card">
          <div className="stat-icon-wrapper green">
            <CheckCircle2 size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-value">{completedCount}</span>
            <span className="stat-label">Completed</span>
          </div>
        </div>
      </div>

      {/* 3. Search & Filter Bar */}
      <div className="assessment-controls-bar">
        <div className="search-input-group">
          <Search size={16} color="#9CA3AF" />
          <input
            type="text"
            placeholder="Search candidate name or role..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-select-group">
          <label htmlFor="status-filter">Assessment Status:</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="Not Created">Not Created</option>
            <option value="Ready to Share">Ready to Share</option>
            <option value="In Progress">In Progress</option>
            <option value="Completed">Completed</option>
          </select>
          <button
            type="button"
            className="refresh-btn"
            onClick={loadShortlists}
            title="Refresh candidates"
          >
            <RefreshCw size={14} className={isLoading ? "spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 4. Candidate Assessment List (Structured Card Layout) */}
      {isLoading ? (
        <div className="loading-state" style={{ padding: "48px", textAlign: "center" }}>
          <Loader2 className="spin" size={28} />
          <p style={{ marginTop: "12px", color: "#6B7280" }}>Loading candidate assessment records...</p>
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="empty-state-mgmt">
          <Award size={44} color="#9CA3AF" />
          <h4>No Candidate Assessments Found</h4>
          <p>No shortlisted candidate matches the search query or selected filter criteria.</p>
        </div>
      ) : (
        <div className="candidate-assessments-list">
          {filteredCandidates.map((cand) => {
            const record = getCandidateRecord(cand);
            const rawStatus = record.status || "Not Created";
            // Map legacy status strings to simple "Ready to Share"
            const status =
              rawStatus === "Created" || rawStatus === "Link Generated"
                ? "Ready to Share"
                : rawStatus;
            const generatedLink = record.generatedLink || "";

            return (
              <div key={cand.key} className="candidate-mgmt-card">
                {/* 1. CANDIDATE SECTION */}
                <div className="card-section">
                  <div className="cand-header-row">
                    <span className="card-section-label">CANDIDATE</span>
                    <button
                      type="button"
                      className="btn-remove-candidate"
                      onClick={() => handleRemoveCandidate(cand.key, cand.candidate_name)}
                      title="Remove candidate from assessments view"
                    >
                      <Trash2 size={13} />
                      <span>Remove Candidate</span>
                    </button>
                  </div>
                  <h3 className="cand-name-large">{cand.candidate_name}</h3>
                  <div className="cand-id-row">
                    <span className="cand-id-text">Candidate ID: {cand.resume_id}</span>
                    <span className="shortlisted-status-tag">
                      <Check size={12} /> Shortlisted
                    </span>
                  </div>
                </div>

                <div className="card-divider" />

                {/* 2. SELECTED ROLE SECTION */}
                <div className="card-section">
                  <span className="card-section-label">SELECTED ROLE</span>
                  <div className="selected-role-pill">
                    <Briefcase size={16} />
                    <span>{cand.job_role}</span>
                  </div>
                </div>

                <div className="card-divider" />

                {/* 3. ASSESSMENT DETAILS SECTION */}
                <div className="card-section">
                  <span className="card-section-label">ASSESSMENT DETAILS</span>
                  <div className="details-row">
                    <span className="detail-spec-item">
                      <Clock size={15} color="#6B7280" /> Duration: 45 Minutes
                    </span>
                    <span className="detail-spec-item">
                      <HelpCircle size={15} color="#6B7280" /> Questions: 15
                    </span>
                    <span className="detail-spec-item">
                      <Award size={15} color="#6B7280" /> Difficulty: Intermediate / Advanced
                    </span>
                  </div>
                </div>

                <div className="card-divider" />

                {/* 4. ASSESSMENT STATUS SECTION & PRIMARY ACTION */}
                <div className="card-section">
                  <span className="card-section-label">ASSESSMENT STATUS</span>
                  <div className="status-action-row">
                    {status === "Not Created" ? (
                      <>
                        <span className="status-badge-large not-created">
                          <Clock size={14} /> Not Created
                        </span>

                        <button
                          type="button"
                          className="btn-primary-action"
                          onClick={() => handleGenerateLink(cand.key, cand)}
                        >
                          <Sparkles size={16} />
                          <span>Generate Candidate Link</span>
                        </button>
                      </>
                    ) : (
                      <>
                        <span className={`status-badge-large ${status === "Completed" ? "completed" : status === "In Progress" ? "in-progress" : "ready"}`}>
                          <CheckCircle2 size={14} /> {status}
                        </span>

                        <select
                          value={status}
                          onChange={(e) => handleStatusChange(cand.key, e.target.value)}
                          className="status-dropdown-select"
                        >
                          <option value="Ready to Share">Ready to Share</option>
                          <option value="In Progress">In Progress</option>
                          <option value="Completed">Completed</option>
                        </select>

                        {status === "Completed" && (
                          <button
                            type="button"
                            className="btn-view-results"
                            onClick={() => handleViewResults(cand.key, cand)}
                          >
                            <Award size={15} />
                            <span>View Results</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* 5. CANDIDATE ASSESSMENT LINK SECTION (Shown when link exists) */}
                {generatedLink && (
                  <div className="link-box-section">
                    <div className="link-box-header">
                      <Sparkles size={15} />
                      <span>CANDIDATE ASSESSMENT LINK</span>
                    </div>

                    <div className="link-box-controls">
                      <input
                        type="text"
                        className="link-url-input"
                        readOnly
                        value={generatedLink}
                      />

                      <div className="link-action-btns">
                        {/* ONLY ONE Copy Link button here */}
                        <button
                          type="button"
                          className={`btn-copy-link ${copiedId === cand.key ? "copied" : ""}`}
                          onClick={() => handleCopyLink(cand.key, generatedLink)}
                        >
                          {copiedId === cand.key ? (
                            <>
                              <CheckCircle2 size={14} /> Copied!
                            </>
                          ) : (
                            <>
                              <Copy size={14} /> Copy Link
                            </>
                          )}
                        </button>

                        <a
                          href={generatedLink}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-preview-link"
                        >
                          <ExternalLink size={14} />
                          <span>Preview Assessment</span>
                        </a>
                      </div>
                    </div>

                    <p className="link-hint-text">
                      Copy this link and share it with the shortlisted candidate.
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Assessment Score / Result Viewer Modal */}
      {viewingResult && (
        <AssessmentResultModal
          viewingResult={viewingResult}
          onClose={() => setViewingResult(null)}
          onRetry={() =>
            handleViewResults(viewingResult.candKey, {
              candidate_name: viewingResult.candidateName,
              job_role: viewingResult.jobRole
            })
          }
        />
      )}
    </div>
  );
}

// ─── ASSESSMENT RESULT MODAL COMPONENT (PHASE 2 SIMPLE SUMMARY) ───────────────
function AssessmentResultModal({ viewingResult, onClose, onRetry }) {
  if (!viewingResult) return null;

  const { candidateName, jobRole, status, loading, error, data } = viewingResult;

  return (
    <div className="arm-modal-overlay" onClick={onClose}>
      <div className="arm-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="arm-modal-header">
          <div className="arm-modal-header-text">
            <div className="arm-modal-badge">
              <Award size={14} />
              <span>ASSESSMENT RESULT</span>
            </div>
            <h3>{candidateName}</h3>
            <p>{jobRole}</p>
          </div>
          <button className="arm-modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="arm-modal-body">
          {loading ? (
            <div className="arm-loading-state">
              <Loader2 size={32} className="spin" />
              <p>Loading Results...</p>
            </div>
          ) : error ? (
            <div className="arm-error-state">
              <AlertTriangle size={36} color="#DC2626" />
              <h4>Unable to Load Results</h4>
              <p>{error}</p>
              {onRetry && (
                <button type="button" className="arm-retry-btn" onClick={onRetry}>
                  <RotateCcw size={14} /> Retry
                </button>
              )}
            </div>
          ) : data ? (
            <div className="arm-summary-card">
              <div className="arm-summary-row">
                <div className="arm-summary-item">
                  <span className="arm-summary-label">Candidate</span>
                  <span className="arm-summary-value">{candidateName}</span>
                </div>
                <div className="arm-summary-item">
                  <span className="arm-summary-label">Role</span>
                  <span className="arm-summary-value">{jobRole}</span>
                </div>
                <div className="arm-summary-item">
                  <span className="arm-summary-label">Status</span>
                  <span className="arm-status-pill completed">
                    <CheckCircle2 size={13} /> {status}
                  </span>
                </div>
              </div>

              <div className="arm-score-banner">
                <div className="arm-score-main">
                  <span className="arm-score-lbl">Total Score</span>
                  <span className="arm-score-num">
                    {data.total_score} <span className="arm-score-max">/ {data.max_score}</span>
                  </span>
                </div>
                <div className="arm-score-pct-badge">
                  <span className="pct-num">{data.percentage}%</span>
                  <span className="pct-lbl">Overall Percentage</span>
                </div>
              </div>

              {/* Phase 3: Skill-wise Performance */}
              <div className="arm-skills-section">
                <h4 className="arm-section-title">
                  <BarChart2 size={16} /> Skill-wise Performance
                </h4>
                {data.skill_scores && data.skill_scores.length > 0 ? (
                  <div className="arm-skills-grid">
                    {data.skill_scores.map((s, idx) => (
                      <div key={idx} className="arm-skill-card">
                        <div className="arm-skill-header">
                          <span className="arm-skill-name">{s.skill}</span>
                          <span className="arm-skill-score">
                            {s.score} / {s.max_score} ({s.percentage}%)
                          </span>
                        </div>
                        <div className="arm-skill-track">
                          <div
                            className="arm-skill-fill"
                            style={{
                              width: `${Math.min(100, Math.max(0, s.percentage))}%`,
                              backgroundColor:
                                s.percentage >= 70 ? "#059669" : s.percentage >= 40 ? "#D97706" : "#DC2626"
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="arm-empty-skills">No skill-wise performance data available.</p>
                )}
              </div>

              {/* Phase 4: Question-wise Results */}
              <div className="arm-question-section">
                <h4 className="arm-section-title">
                  <FileText size={16} /> Question-wise Results
                </h4>
                {data.question_results && data.question_results.length > 0 ? (
                  <div className="arm-question-list">
                    {data.question_results.map((q, idx) => {
                      const qNum = q.question_number || idx + 1;
                      const rawType = (q.question_type || "").toLowerCase();
                      const typeLabel =
                        rawType === "mcq"
                          ? "MCQ"
                          : rawType === "short_answer"
                          ? "Short Answer"
                          : q.question_type || "Question";

                      const hasAns = Boolean(q.candidate_answer && String(q.candidate_answer).trim());
                      const candAns = hasAns ? String(q.candidate_answer).trim() : "Not answered";
                      const scoreVal = typeof q.score === "number" ? q.score : 0;
                      const maxScoreVal = typeof q.max_score === "number" ? q.max_score : 1;

                      const pointsMet = Array.isArray(q.evaluation_points_met) ? q.evaluation_points_met : [];
                      const pointsMissed = Array.isArray(q.evaluation_points_missed) ? q.evaluation_points_missed : [];
                      const reasonText = q.reason ? String(q.reason).trim() : "";
                      const hasEval = pointsMet.length > 0 || pointsMissed.length > 0 || Boolean(reasonText);

                      return (
                        <div key={q.question_id || idx} className="arm-question-card">
                          <div className="arm-question-header">
                            <div className="arm-question-meta">
                              <span className="arm-q-badge num">Q{qNum}</span>
                              <span className="arm-q-badge type">{typeLabel}</span>
                              {q.skill && <span className="arm-q-badge skill">{q.skill}</span>}
                            </div>
                            <div className="arm-question-score">
                              Score: <span className="arm-score-highlight">{scoreVal} / {maxScoreVal}</span>
                            </div>
                          </div>

                          <div className="arm-question-answer">
                            <span className="arm-answer-label">Candidate Answer:</span>
                            <div className={`arm-answer-text ${!hasAns ? "unanswered" : ""}`}>
                              {candAns}
                            </div>
                          </div>

                          {/* Short-Answer Evaluation Details */}
                          {hasEval && (
                            <div className="arm-question-evaluation">
                              <div className="arm-eval-title">Evaluation</div>

                              {pointsMet.length > 0 && (
                                <div className="arm-eval-group met">
                                  <span className="arm-eval-subtitle met">Points Met:</span>
                                  <ul className="arm-eval-list met">
                                    {pointsMet.map((pt, pIdx) => (
                                      <li key={pIdx}>{pt}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {pointsMissed.length > 0 && (
                                <div className="arm-eval-group missed">
                                  <span className="arm-eval-subtitle missed">Points Missed:</span>
                                  <ul className="arm-eval-list missed">
                                    {pointsMissed.map((pt, pIdx) => (
                                      <li key={pIdx}>{pt}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {reasonText && (
                                <div className="arm-eval-group reason">
                                  <span className="arm-eval-subtitle">Reason:</span>
                                  <p className="arm-eval-reason-text">{reasonText}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="arm-empty-questions">No question-wise results available.</p>
                )}
              </div>
            </div>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="arm-modal-footer">
          <button type="button" className="arm-close-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default AssessmentManagementPage;
