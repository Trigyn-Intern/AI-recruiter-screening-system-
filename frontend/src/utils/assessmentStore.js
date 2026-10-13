// Centralized local storage helper for candidate assessment records & lifecycle management

const RECRUITER_RECORDS_KEY = "recruiter.assessment_records";

export function getRawAssessmentRecords() {
  try {
    const saved = localStorage.getItem(RECRUITER_RECORDS_KEY);
    return saved ? JSON.parse(saved) : {};
  } catch (err) {
    console.error("Failed to parse raw assessment records:", err);
    return {};
  }
}

export function saveRawAssessmentRecords(records) {
  try {
    localStorage.setItem(RECRUITER_RECORDS_KEY, JSON.stringify(records));
    // Dispatch storage event locally so open tabs/components can re-sync immediately
    window.dispatchEvent(new Event("storage"));
  } catch (err) {
    console.error("Failed to save raw assessment records:", err);
  }
}

/**
 * Generate a unique assessment record key based on candidateId and shortlistId or candidateId + role.
 */
export function getAssessmentKey(candidateId, shortlistId = "", role = "") {
  if (!candidateId) return "";
  if (shortlistId && shortlistId !== "demo" && shortlistId !== "active_session") {
    return `asm_${candidateId}_${shortlistId}`;
  }
  const cleanRole = String(role).trim().toLowerCase().replace(/[^a-z0-9]/g, "_");
  return `asm_${candidateId}_${cleanRole || "default"}`;
}

/**
 * Find or resolve assessment record by assessmentId or candidateId + role.
 */
export function findAssessmentRecord({ assessmentId, candidateId, role }) {
  const records = getRawAssessmentRecords();
  
  if (assessmentId && records[assessmentId]) {
    return { key: assessmentId, record: records[assessmentId] };
  }

  // Search by key matching or candidateId + role matching
  for (const [key, rec] of Object.entries(records)) {
    if (rec.assessmentId === assessmentId || key === assessmentId) {
      return { key, record: rec };
    }
    if (
      candidateId &&
      (rec.candidateId === candidateId || key.includes(candidateId)) &&
      (!role || String(rec.jobRole).toLowerCase() === String(role).toLowerCase())
    ) {
      return { key, record: rec };
    }
  }

  // Soft fallback by candidateId match alone
  if (candidateId) {
    for (const [key, rec] of Object.entries(records)) {
      if (rec.candidateId === candidateId || key.includes(candidateId)) {
        return { key, record: rec };
      }
    }
  }

  return { key: null, record: null };
}

/**
 * Create or update an assessment record in localStorage.
 */
export function createOrUpdateAssessment(candKey, candidateData) {
  const records = getRawAssessmentRecords();
  const existing = records[candKey] || {};

  const assessmentId = existing.assessmentId || candKey;

  const updatedRecord = {
    ...existing,
    assessmentId,
    key: candKey,
    candidateId: candidateData.resume_id || candidateData.candidateId || existing.candidateId,
    candidateName: candidateData.candidate_name || candidateData.candidateName || existing.candidateName,
    jobRole: candidateData.job_role || candidateData.jobRole || existing.jobRole || "Engineer",
    shortlistId: candidateData.shortlist_id || existing.shortlistId || "default",
    status: existing.status || "Ready to Share",
    generatedLink: existing.generatedLink || null,
    duration: "45 Mins",
    questionCount: "15 Questions",
    createdAt: existing.createdAt || new Date().toISOString(),
    linkGeneratedAt: existing.linkGeneratedAt || null,
    startedAt: existing.startedAt || null,
    completedAt: existing.completedAt || null,
  };

  records[candKey] = updatedRecord;
  saveRawAssessmentRecords(records);
  return updatedRecord;
}

/**
 * Transition assessment record status (e.g., to "In Progress" or "Completed").
 */
export function transitionAssessmentStatus({ assessmentId, candidateId, role }, newStatus) {
  let { key, record } = findAssessmentRecord({ assessmentId, candidateId, role });
  const targetKey = key || assessmentId || candidateId || "default";

  const records = getRawAssessmentRecords();
  const existing = record || records[targetKey] || {};
  const now = new Date().toISOString();

  const updatedRecord = {
    ...existing,
    assessmentId: existing.assessmentId || assessmentId || targetKey,
    candidateId: candidateId || existing.candidateId || candidateId,
    jobRole: role || existing.jobRole || "Engineer",
    status: newStatus,
    startedAt: newStatus === "In Progress" && !existing.startedAt ? now : (existing.startedAt || (newStatus === "Completed" ? now : null)),
    completedAt: newStatus === "Completed" ? now : existing.completedAt,
  };

  records[targetKey] = updatedRecord;
  saveRawAssessmentRecords(records);
  return updatedRecord;
}
