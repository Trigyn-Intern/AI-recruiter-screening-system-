import { Navigate } from "react-router-dom";

function RequireAuth({ children }) {
  const isAuthed = localStorage.getItem("recruiter.auth") === "true";
  if (!isAuthed) {
    return <Navigate to="/" replace />;
  }
  return children;
}

export default RequireAuth;