import { NavLink, Outlet } from "react-router-dom";

export default function Layout() {
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
