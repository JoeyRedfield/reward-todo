import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const TOTAL_STEPS = 2;

export default function SignupPage() {
  const { register, loading, user } = useAuth();
  const [step, setStep] = useState(1);
  const [completed, setCompleted] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <div className="loading-card auth-loading">加载中...</div>;
  }

  if (user && !completed) {
    return <Navigate replace to="/today" />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) {
      return;
    }

    if (!username.trim() || !password) {
      setError("请填写用户名和密码");
      return;
    }

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      await register({ username: username.trim(), password });
      setCompleted(true);
      setStep(2);
    } catch (submitError) {
      setError(submitError.message || "创建账号失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card-shell">
        <div className="auth-intro">
          <div className="page-kicker">New Account</div>
          <h1>创建账号</h1>
          <p className="auth-copy">
            先完成最小注册流程，后续资料完善和视觉细化由后续任务继续扩展。
          </p>
        </div>
        <div className="auth-card">
          <p>步骤 {step} / {TOTAL_STEPS}</p>
          {step === 1 ? (
            <form onSubmit={handleSubmit}>
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
                  autoComplete="new-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <label>
                确认密码
                <input
                  autoComplete="new-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                />
              </label>
              <button
                className="primary-button"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "提交中..." : "继续"}
              </button>
            </form>
          ) : (
            <div>
              <h2>账号已创建</h2>
              <p>基础注册已完成，后续步骤可在此页继续扩展。</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
