import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

function resolveRedirectPath(rawRedirect) {
  if (
    !rawRedirect ||
    !rawRedirect.startsWith("/") ||
    rawRedirect.startsWith("//")
  ) {
    return "/today";
  }
  return rawRedirect;
}

export default function LoginPage() {
  const { login, loading, sessionExpired, clearSessionExpired, user } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const redirectPath = resolveRedirectPath(searchParams.get("redirect"));

  if (loading) {
    return <div className="loading-card auth-loading">加载中...</div>;
  }

  if (!loading && user) {
    return <Navigate replace to={redirectPath} />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    clearSessionExpired();

    try {
      await login({ username, password });
      navigate(redirectPath, { replace: true });
    } catch (submitError) {
      setError(submitError.message || "用户名或密码错误");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="page-kicker">Login</div>
        <h1>登录</h1>
        <p className="auth-copy">使用你的 Reward Todo 账户继续访问任务与奖励数据。</p>
        {sessionExpired ? (
          <div className="error-banner">登录已失效，请重新登录</div>
        ) : null}
        {error ? <div className="error-banner">{error}</div> : null}
        <label>
          用户名
          <input
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <label>
          密码
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button className="primary-button" disabled={submitting} type="submit">
          {submitting ? "登录中..." : "登录"}
        </button>
      </form>
    </div>
  );
}
