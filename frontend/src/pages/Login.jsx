import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
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
    <div className="auth-page auth-page--product">
      <div className="auth-card-shell">
        <div className="auth-intro">
          <div className="page-kicker">Reward Todo</div>
          <h1>登录</h1>
          <p className="auth-copy">
            继续你的任务和奖励工作台。
          </p>
          <div className="auth-intro-list">
            <div className="auth-intro-item">今天任务、奖励余额、项目安排在同一个入口继续。</div>
            <div className="auth-intro-item">登录后会回到你刚才想访问的页面，不会打断当前流程。</div>
          </div>
        </div>
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-form-head">
            <h2>欢迎回来</h2>
            <p>使用你的账号继续管理每日任务、奖励和工作区。</p>
          </div>
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
          <div className="auth-link-row">
            <span>没有账号？</span>
            <Link to="/signup">创建账号</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
