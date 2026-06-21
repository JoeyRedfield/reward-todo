import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout, changePassword } = useAuth();
  const navigate = useNavigate();
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  async function handlePasswordSubmit(event) {
    event.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_new_password: confirmNewPassword,
      });
      setPasswordSuccess("密码已更新");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
      setShowPasswordForm(false);
    } catch (error) {
      setPasswordError(error.message || "修改密码失败");
    }
  }

  return (
    <div className="layout-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-kicker">Reward Todo</div>
          <h1 className="brand-title">个人任务板 + 奖励账本</h1>
          <p className="brand-copy">
            管理今天要做的事，完成后累计奖励额度，再决定怎么花掉它。
          </p>
        </div>
        <section className="account-panel">
          <div className="account-label">当前用户</div>
          <div className="account-name">{user?.username}</div>
          <div className="account-actions">
            <button
              className="ghost-button"
              onClick={() => setShowPasswordForm((value) => !value)}
              type="button"
            >
              修改密码
            </button>
            <button className="ghost-button" onClick={handleLogout} type="button">
              登出
            </button>
          </div>
          {passwordError ? <div className="error-banner">{passwordError}</div> : null}
          {passwordSuccess ? (
            <div className="success-banner">{passwordSuccess}</div>
          ) : null}
          {showPasswordForm ? (
            <form className="form-stack account-form" onSubmit={handlePasswordSubmit}>
              <label>
                当前密码
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                />
              </label>
              <label>
                新密码
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </label>
              <label>
                确认新密码
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(event) => setConfirmNewPassword(event.target.value)}
                />
              </label>
              <button className="primary-button" type="submit">
                确认修改
              </button>
            </form>
          ) : null}
        </section>
        <nav className="nav-links">
          <NavLink to="/today">今日</NavLink>
          <NavLink to="/projects">项目</NavLink>
          <NavLink to="/rewards">奖励</NavLink>
        </nav>
      </aside>
      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
