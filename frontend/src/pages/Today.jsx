import DailyTaskList from "../components/DailyTaskList";
import TaskSummaryCards from "../components/TaskSummaryCards";
import useTodayBoard from "../hooks/useTodayBoard";

export default function TodayPage() {
  const {
    tasks,
    summary,
    loading,
    error,
    pendingTaskId,
    finishTask,
    reopenTask,
  } = useTodayBoard();

  return (
    <div className="page-stack">
      <header className="page-head">
        <div className="page-head-main">
          <div className="page-kicker">Today</div>
          <h2>今天先完成这些，再决定怎么奖励自己。</h2>
        </div>
        <aside className="page-stamp">
          <div className="page-stamp-label">本页用途</div>
          <div className="page-stamp-value">先排今天，再确认奖励。</div>
        </aside>
      </header>
      {loading ? (
        <div className="loading-card">加载中...</div>
      ) : (
        <>
          <TaskSummaryCards summary={summary} tasks={tasks} />
          {error ? <div className="error-banner">{error}</div> : null}
          <DailyTaskList
            tasks={tasks}
            pendingTaskId={pendingTaskId}
            onFinishTask={finishTask}
            onReopenTask={reopenTask}
          />
        </>
      )}
    </div>
  );
}
