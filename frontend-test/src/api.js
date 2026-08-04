const AUTH_API_BASE = import.meta.env.VITE_API_URL || "";
const FASTAPI_BASE = import.meta.env.VITE_FASTAPI_URL || "";

const AUTH_TOKEN_KEY = "testing.token";
const AUTH_USER_KEY  = "testing.user";

export function storeSession(token, user) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  if (user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export function getStoredToken() { return localStorage.getItem(AUTH_TOKEN_KEY); }
export function getStoredUser() {
  const raw = localStorage.getItem(AUTH_USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

async function request(base, path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${base}${path}`, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    const msg = (data && (data.message || data.detail)) || `Request failed (${response.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export function authApi(path, opts = {}) {
  return request(AUTH_API_BASE, path, { ...opts, token: getStoredToken() });
}

export function analysisApi(path, opts = {}) {
  return request(FASTAPI_BASE, path, { ...opts, token: getStoredToken() });
}

export async function executeCommand(payload) {
  const response = await fetch("/api/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.error) || `Command failed (${response.status})`);
  }
  return data;
}

export async function getReportMetadata(reports) {
  const response = await fetch("/api/reports", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reports || []),
  });
  const data = await response.json().catch(() => []);
  if (!response.ok) throw new Error((data && data.error) || `Report scan failed (${response.status})`);
  return Array.isArray(data) ? data : [];
}

export async function listReports() {
  const response = await fetch(`${FASTAPI_BASE}/api/reports`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data && data.detail) || `Report list failed (${response.status})`);
  return Array.isArray(data) ? data : Array.isArray(data.reports) ? data.reports : [];
}

export async function getReportSummary(reportId, { refresh = false } = {}) {
  const qs = refresh ? "?refresh=true" : "";
  const response = await fetch(`${FASTAPI_BASE}/api/reports/${encodeURIComponent(reportId)}/summary${qs}`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data && data.detail) || `Summary failed (${response.status})`);
  return data;
}

export async function listReportSummaries() {
  const response = await fetch(`${FASTAPI_BASE}/api/report-summary`);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data && data.detail) || `Report list failed (${response.status})`);
  return Array.isArray(data.reports) ? data.reports : [];
}

export { AUTH_API_BASE, FASTAPI_BASE };
