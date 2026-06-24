import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import App from "../../App";
import "./dashboard.css";

function Dashboard() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem("recruiter.auth");
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
          <strong>admin@gmail.com</strong>
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
    </div>
  );
}

export default Dashboard;