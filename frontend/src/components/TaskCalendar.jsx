import {
  buildCalendarDays,
  formatMonthLabel,
  getWeekdayLabels,
  shiftMonth,
} from "../utils/calendar";

export default function TaskCalendar({
  calendarSummary,
  selectedDate,
  visibleMonth,
  onChangeMonth,
  onJumpToToday,
  onSelectDate,
}) {
  const markersByDate = Object.fromEntries(
    calendarSummary.map((item) => [item.date, item])
  );
  const days = buildCalendarDays(visibleMonth);

  return (
    <section className="panel">
      <div className="panel-head calendar-head">
        <div>
          <h2>台账日历</h2>
          <p className="calendar-subtitle">选中某一天，下方任务和加任务入口都会切到那一天。</p>
        </div>
        <div className="calendar-controls">
          <button
            className="ghost-button"
            onClick={() => onChangeMonth(shiftMonth(visibleMonth, -1))}
            type="button"
          >
            上个月
          </button>
          <div className="calendar-month-label">{formatMonthLabel(visibleMonth)}</div>
          <button
            className="ghost-button"
            onClick={() => onChangeMonth(shiftMonth(visibleMonth, 1))}
            type="button"
          >
            下个月
          </button>
          <button className="ghost-button" onClick={onJumpToToday} type="button">
            回到今天
          </button>
        </div>
      </div>

      <div className="calendar-weekdays">
        {getWeekdayLabels().map((label) => (
          <div key={label} className="calendar-weekday">
            {label}
          </div>
        ))}
      </div>

      <div className="calendar-grid">
        {days.map((day) => {
          const marker = markersByDate[day.date];
          const taskCount = marker?.task_count ?? 0;
          const completedCount = marker?.completed_count ?? 0;
          const isSelected = selectedDate === day.date;

          return (
            <button
              key={day.date}
              aria-label={
                taskCount > 0
                  ? `选择 ${day.date}，${taskCount} 项任务`
                  : `选择 ${day.date}`
              }
              aria-pressed={isSelected}
              className={`calendar-day${day.isCurrentMonth ? "" : " is-outside-month"}${
                isSelected ? " is-selected" : ""
              }${taskCount > 0 ? " has-tasks" : ""}${
                taskCount > 0 && completedCount === taskCount ? " is-complete" : ""
              }`}
              onClick={() => onSelectDate(day.date)}
              type="button"
            >
              <span className="calendar-day-number">{day.dayOfMonth}</span>
              {taskCount > 0 ? (
                <span className="calendar-day-count">{taskCount} 项</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}
