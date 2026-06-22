import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const TOTAL_STEPS = 2;

export default function SignupPage() {
  const { register, loading, user } = useAuth();
  const [step, setStep] = useState(1);
  const [completed, setCompleted] = useState(false);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [createDefaultWorkspace, setCreateDefaultWorkspace] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <div className="loading-card auth-loading">加载中...</div>;
  }

  if (user && !completed) {
    return <Navigate replace to="/today" />;
  }

  function handleContinue(event) {
    event.preventDefault();
    if (
      !username.trim() ||
      !displayName.trim() ||
      !email.trim() ||
      !password ||
      !confirmPassword
    ) {
      setError("请完整填写注册信息");
      return;
    }

    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setError("");
    setStep(2);
  }

  async function handleRegister(event) {
    event.preventDefault();
    if (submitting) {
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      await register({
        username: username.trim(),
        display_name: displayName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirmPassword,
        create_default_workspace: createDefaultWorkspace,
      });
      setCompleted(true);
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
          {completed ? (
            <div>
              <h2>账号已创建</h2>
              <p>注册已提交成功，正在进入你的工作台。</p>
            </div>
          ) : step === 1 ? (
            <form onSubmit={handleContinue}>
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
                显示名称
                <input
                  autoComplete="name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              </label>
              <label>
                邮箱
                <input
                  autoComplete="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
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
                继续
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              {error ? <div className="error-banner">{error}</div> : null}
              <label>
                <input
                  checked={createDefaultWorkspace}
                  onChange={(event) =>
                    setCreateDefaultWorkspace(event.target.checked)
                  }
                  type="checkbox"
                />
                创建默认工作区
              </label>
              <p>建议为新账号自动创建一个默认工作区，便于后续继续扩展任务与奖励数据。</p>
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting ? "创建中..." : "创建账号"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
