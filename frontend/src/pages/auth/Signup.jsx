import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import request from "../../api/client";
import "./auth.css";

function Signup() {
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  async function handleSignup(e) {
    e.preventDefault();
    setError("");

    const trimmedName = name.trim();
    const normalizedEmail = email.trim().toLowerCase();

    if (!trimmedName) {
      setError("Name is required.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await request("/api/auth/signup", {
        method: "POST",
        body: {
          name: trimmedName,
          email: normalizedEmail,
          password,
          confirmPassword,
        },
      });

      navigate("/", {
        state: { signupNotice: "Account created. Please sign in." },
      });
    } catch (requestError) {
      setError(requestError.message || "Could not create the account.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="glass-card">
        <h1>Create account</h1>
        <p className="subtitle">Start your journey with Solance</p>

        <form onSubmit={handleSignup}>
          <div className="form-group">
            <input
              type="text"
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
            />
          </div>

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
                autoComplete="new-password"
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

          <div className="form-group">
            <input
              type="password"
              placeholder="Confirm Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="main-btn" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="spin" size={18} /> : null}
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/">Login</Link>
        </div>
      </div>
    </div>
  );
}

export default Signup;
