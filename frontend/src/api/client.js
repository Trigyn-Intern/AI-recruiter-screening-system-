const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:4000";

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      (data && data.message) || `Request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return data;
}

export const AUTH_TOKEN_KEY = "recruiter.token";
export const AUTH_USER_KEY = "recruiter.user";

export function storeSession(token, user) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  if (user) {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  }
}

export function clearSession() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export function getStoredToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(AUTH_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export default request;