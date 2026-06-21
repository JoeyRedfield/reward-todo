import DailyTaskList from "../components/DailyTaskList";
import TaskSummaryCards from "../components/TaskSummaryCards";
import useTodayBoard from "../hooks/useTodayBoard";

export default function TodayPage() {
  const { tasks, summary, loading, error, finishingTaskId, finishTask } =
    useTodayBoard();

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="page-kicker">Today</div>
          <h2>今天先完成这些，再决定怎么奖励自己。</h2>
        </div>
      </header>
      {loading ? (
        <div className="loading-card">加载中...</div>
      ) : (
        <>
          <TaskSummaryCards summary={summary} tasks={tasks} />
          {error ? <div className="error-banner">{error}</div> : null}
          <DailyTaskList
            tasks={tasks}
            finishingTaskId={finishingTaskId}
            onFinishTask={finishTask}
          />
        </>
      )}
    </div>
  );
}
