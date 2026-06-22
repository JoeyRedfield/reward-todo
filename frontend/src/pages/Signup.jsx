import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const TOTAL_STEPS = 3;

const STEP_LABELS = ["基础信息", "初始化工作台", "完成"];

export default function SignupPage() {
  const { register, loading, user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [createDefaultWorkspace, setCreateDefaultWorkspace] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [finishingSignup, setFinishingSignup] = useState(false);
  const [completedRegistration, setCompletedRegistration] = useState(null);

  if (loading) {
    return <div className="loading-card auth-loading">加载中...</div>;
  }

  if (user && !completedRegistration && !finishingSignup) {
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

  function handleBackToBasics() {
    setError("");
    setStep(1);
  }

  async function handleRegister(event) {
    event.preventDefault();
    if (submitting) {
      return;
    }

    setSubmitting(true);
    setError("");
    setFinishingSignup(true);

    try {
      await register({
        username: username.trim(),
        display_name: displayName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirmPassword,
        create_default_workspace: createDefaultWorkspace,
      });
      setCompletedRegistration({
        username: username.trim(),
        displayName: displayName.trim(),
        email: email.trim(),
        createDefaultWorkspace,
      });
      setStep(3);
    } catch (submitError) {
      setFinishingSignup(false);
      setError(submitError.message || "创建账号失败");
    } finally {
      setSubmitting(false);
    }
  }

  function handleEnterToday() {
    navigate("/today", { replace: true });
  }

  return (
    <div className="auth-page auth-page--product">
      <div className="auth-card-shell">
        <div className="auth-intro">
          <div className="page-kicker">Reward Todo</div>
          <h1>创建账号</h1>
          <p className="auth-copy">
            用 3 步完成基础注册、初始化工作台，然后进入今日面板开始使用。
          </p>
          <div className="auth-intro-list">
            <div className="auth-intro-item">只保留当前产品真正需要的注册字段，不增加额外资料负担。</div>
            <div className="auth-intro-item">如果勾选默认工作区，系统会为新账号准备最小可用的起始环境。</div>
          </div>
        </div>
        <div className="auth-card">
          <div className="auth-form-head">
            <h2>{STEP_LABELS[step - 1]}</h2>
            <p>第 {step} 步，共 {TOTAL_STEPS} 步</p>
          </div>
          <div className="auth-stepper" aria-label="注册步骤">
            {STEP_LABELS.map((label, index) => {
              const stepNumber = index + 1;
              const state =
                stepNumber === step ? "is-current" : stepNumber < step ? "is-complete" : "";
              return (
                <div className={`auth-step ${state}`.trim()} key={label}>
                  <span className="auth-step-index">{stepNumber}</span>
                  <span className="auth-step-label">{label}</span>
                </div>
              );
            })}
          </div>
          {step === 1 ? (
            <form className="form-stack" onSubmit={handleContinue}>
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
              <p className="auth-input-hint">
                注册后将使用这组信息创建账号，并在同一步登录当前会话。
              </p>
              <button
                className="primary-button"
                disabled={submitting}
                type="submit"
              >
                继续
              </button>
              <div className="auth-link-row">
                <span>已经有账号？</span>
                <Link to="/login">返回登录</Link>
              </div>
            </form>
          ) : null}

          {step === 2 ? (
            <form className="form-stack" onSubmit={handleRegister}>
              {error ? <div className="error-banner">{error}</div> : null}
              <div className="auth-option-card">
                <div className="auth-option-row">
                  <div>
                    <strong>创建默认工作区</strong>
                    <p className="auth-input-hint">
                      为新账号准备一个最小可用的工作台，方便直接开始维护任务和奖励。
                    </p>
                  </div>
                  <label className="auth-checkbox">
                    <input
                      checked={createDefaultWorkspace}
                      onChange={(event) =>
                        setCreateDefaultWorkspace(event.target.checked)
                      }
                      type="checkbox"
                    />
                    <span>启用</span>
                  </label>
                </div>
                <div className="auth-summary">
                  <div>账号：{displayName.trim() || username.trim()}</div>
                  <div>邮箱：{email.trim()}</div>
                  <div>
                    预设：{createDefaultWorkspace ? "创建默认工作区" : "仅创建账号"}
                  </div>
                </div>
              </div>
              <div className="auth-actions">
                <button className="ghost-button" onClick={handleBackToBasics} type="button">
                  返回上一步
                </button>
                <button className="primary-button" disabled={submitting} type="submit">
                  {submitting ? "创建中..." : "创建账号"}
                </button>
              </div>
            </form>
          ) : null}

          {step === 3 ? (
            <div className="auth-success-panel">
              <div className="success-banner">账号创建成功</div>
              <p className="auth-copy">
                {completedRegistration?.displayName || completedRegistration?.username}
                的账号已经可以使用。
                {completedRegistration?.createDefaultWorkspace
                  ? " 默认工作区也已准备完成。"
                  : " 你可以稍后再创建工作区。"}
              </p>
              <div className="auth-summary">
                <div>用户名：{completedRegistration?.username}</div>
                <div>邮箱：{completedRegistration?.email}</div>
                <div>
                  状态：
                  {completedRegistration?.createDefaultWorkspace
                    ? " 已初始化工作台"
                    : " 待手动初始化工作台"}
                </div>
              </div>
              <button className="primary-button" onClick={handleEnterToday} type="button">
                进入今日面板
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
