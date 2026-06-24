import DailyTaskList from "../components/DailyTaskList";
import TaskCalendar from "../components/TaskCalendar";
import TaskQuickAddPanel from "../components/TaskQuickAddPanel";
import TaskSummaryCards from "../components/TaskSummaryCards";
import useTodayBoard from "../hooks/useTodayBoard";
import { formatSelectedDateLabel } from "../utils/calendar";

export default function TodayPage() {
  const board = useTodayBoard();
  const emptyText =
    board.selectedDate === board.today
      ? "今天还没有安排任务。"
      : `${board.selectedDate} 还没有安排任务。`;

  return (
    <div className="page-stack">
      <header className="page-head">
        <div className="page-head-main">
          <div className="page-kicker">Ledger</div>
          <h2>台账不只盯今天，选一天就从那一天开工。</h2>
          <div className="page-context">{formatSelectedDateLabel(board.selectedDate)}</div>
        </div>
        <aside className="page-stamp">
          <div className="page-stamp-label">当前焦点</div>
          <div className="page-stamp-value">{board.selectedDate}</div>
        </aside>
      </header>
      {board.loading ? (
        <div className="loading-card">加载中...</div>
      ) : (
        <>
          <TaskCalendar
            calendarSummary={board.calendarSummary}
            onChangeMonth={board.setVisibleMonth}
            onJumpToToday={board.jumpToToday}
            onSelectDate={board.selectDate}
            selectedDate={board.selectedDate}
            visibleMonth={board.visibleMonth}
          />
          <TaskSummaryCards summary={board.summary} tasks={board.tasks} />
          {board.error ? <div className="error-banner">{board.error}</div> : null}
          <div className="board-grid">
            <DailyTaskList
              emptyText={emptyText}
              onDeleteTask={board.deleteStandaloneTask}
              pendingTaskId={board.pendingTaskId}
              pendingTaskAction={board.pendingTaskAction}
              onFinishTask={board.finishTask}
              onReopenTask={board.reopenTask}
              tasks={board.tasks}
              title="当日任务"
            />
            <TaskQuickAddPanel
              addingTemplateId={board.addingTemplateId}
              addingStandaloneTask={board.addingStandaloneTask}
              onAddStandaloneTask={board.addStandaloneTask}
              onAddTemplate={board.addTemplateToSelectedDate}
              selectedDate={board.selectedDate}
              templates={board.quickAddTemplates}
            />
          </div>
        </>
      )}
    </div>
  );
}
