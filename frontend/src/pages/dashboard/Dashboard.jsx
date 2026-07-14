import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import App from "../../App";
import request, {
  clearSession,
  getStoredToken,
  getStoredUser,
} from "../../api/client";
import "./dashboard.css";
import ReportsPanel from "./ReportsPanel";

function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(getStoredUser());

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      navigate("/", { replace: true });
      return;
    }

    let cancelled = false;
    request("/api/auth/me", { token })
      .then((data) => {
        if (!cancelled && data && data.user) {
          setUser(data.user);
          localStorage.setItem("recruiter.user", JSON.stringify(data.user));
        }
      })
      .catch(() => {
        if (cancelled) return;
        clearSession();
        navigate("/", { replace: true });
      });

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function handleLogout() {
    clearSession();
    navigate("/", { replace: true });
  }

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div className="dashboard-brand">
          <div className="dashboard-brand-mark">R</div>
          <div>
            <h1>Resume Analyzer</h1>
            <p>React frontend with FastAPI analysis backend.</p>
          </div>
        </div>
        <div className="dashboard-user">
          <span>Signed in as</span>
          <strong>{user ? (user.name || user.email) : "Recruiter"}</strong>
          <button
            className="logout-btn"
            type="button"
            onClick={handleLogout}
          >
            <LogOut size={14} />
            Logout
          </button>
        </div>
      </header>
      <App />
      <ReportsPanel />
    </div>
  );
}

export default Dashboard;
