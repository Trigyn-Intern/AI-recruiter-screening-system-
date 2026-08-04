import { Navigate } from "react-router-dom";
import { getStoredToken } from "../api/client";

function RequireAuth({ children }) {
  const token = getStoredToken();
  if (!token) {
    return <Navigate to="/" replace />;
  }
  return children;
}

export default RequireAuth;