import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import "./auth.css";

const DEFAULT_EMAIL = "admin@gmail.com";
const DEFAULT_PASSWORD = "admin123";

function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();
    setError("");

    const okEmail = email.trim().toLowerCase() === DEFAULT_EMAIL;
    const okPassword = password === DEFAULT_PASSWORD;

    if (!okEmail || !okPassword) {
      setError("Invalid email or password.");
      return;
    }

    localStorage.setItem("recruiter.auth", "true");
    navigate("/dashboard");
  };

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

          <button type="submit" className="main-btn">
            Login
          </button>

          <p className="login-hint">
            Use <code>admin@gmail.com</code> / <code>admin123</code>
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