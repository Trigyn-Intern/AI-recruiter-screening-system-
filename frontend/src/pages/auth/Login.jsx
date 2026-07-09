import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import request, {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  storeSession,
} from "../../api/client";
import "./auth.css";

// The testing dashboard runs on a separate Vite app (different port,
// no shared bundle). After a manager logs in here we redirect the
// browser to that app and hand the JWT over via the query string.
const TESTING_APP_URL =
  import.meta.env.VITE_TESTING_APP_URL || "http://localhost:5174/";

function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  async function handleLogin(e) {
    e.preventDefault();
    setError("");

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await request("/api/auth/login", {
        method: "POST",
        body: { email: trimmedEmail, password },
      });

      if (!data || !data.token) {
        throw new Error("Login response was missing a token.");
      }

      storeSession(data.token, data.user);
      localStorage.setItem(AUTH_TOKEN_KEY, data.token);
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(data.user || {}));

      const role = (data.user && data.user.role) || "recruiter";
      if (role === "manager") {
        window.location.href = `http://localhost:5174/?token=${encodeURIComponent(data.token)}`;
        return;
      }
      navigate("/dashboard");

      if (data.user && data.user.role === "manager") {
        const target = new URL(TESTING_APP_URL);
        target.searchParams.set("token", data.token);
        if (data.user && data.user.id) {
          target.searchParams.set("uid", data.user.id);
        }
        window.location.assign(target.toString());
        return;
      }

      navigate("/dashboard");
    } catch (requestError) {
      setError(requestError.message || "Invalid email or password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="glass-card">
        <h1>Welcome back</h1>
        <p className="subtitle">Log in to continue your journey</p>

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </div>

          <div className="form-group">
            <div className="password-box">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {error && <p className="login-error">{error}</p>}

          <div className="forgot-link-container">
            <a href="#forgot" className="forgot-link">
              Forgot password?
            </a>
          </div>

          <button type="submit" className="main-btn" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="spin" size={18} /> : null}
            {isSubmitting ? "Signing in..." : "Login"}
          </button>

          <p className="login-hint">
            Need an account? <Link to="/signup">Create one</Link>
          </p>
        </form>

        <div className="auth-footer">
          Don't have an account? <Link to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  );
}

export default Login;
