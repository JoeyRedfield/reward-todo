import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { loading, user } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="loading-card">加载中...</div>;
  }

  if (!user) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate replace to={`/login?redirect=${redirect}`} />;
  }

  return <Outlet />;
}
