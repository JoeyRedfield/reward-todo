import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="layout-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-kicker">Reward Todo</div>
          <h1 className="brand-title">
            <span>个人执行</span>
            <span>台账</span>
          </h1>
          <p className="brand-copy">
            把任务、时长和奖励放进同一张工作台，先完成，再结算。
          </p>
          <div className="brand-meter" aria-hidden="true">
            <div className="brand-meter-item">
              <span>PLAN</span>
              <strong>排任务</strong>
            </div>
            <div className="brand-meter-item">
              <span>EARN</span>
              <strong>赚奖励</strong>
            </div>
            <div className="brand-meter-item">
              <span>SPEND</span>
              <strong>再使用</strong>
            </div>
          </div>
        </div>
        <section className="account-panel">
          <div className="account-label">当前用户</div>
          <div className="account-name">{user?.display_name || user?.username}</div>
          <div className="account-secondary">
            {user?.username ? `@${user.username}` : ""}
          </div>
          <div className="account-actions">
            <NavLink className="ghost-link" to="/account">
              账号设置
            </NavLink>
            <button className="ghost-button" onClick={handleLogout} type="button">
              登出
            </button>
          </div>
        </section>
        <nav className="nav-links">
          <NavLink to="/today">今日</NavLink>
          <NavLink to="/projects">项目</NavLink>
          <NavLink to="/rewards">奖励</NavLink>
          <NavLink to="/account">账号</NavLink>
        </nav>
      </aside>
      <main className="page-shell">
        <div className="page-frame">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
