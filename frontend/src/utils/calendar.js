import { formatLocalDate } from "./date";

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

export function getWeekdayLabels() {
  return WEEKDAY_LABELS;
}

export function parseLocalDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 12);
}

export function shiftMonth(value, offset) {
  const current = parseLocalDate(value);
  const target = new Date(current.getFullYear(), current.getMonth() + offset, 1, 12);
  const lastDayOfMonth = new Date(
    target.getFullYear(),
    target.getMonth() + 1,
    0,
    12
  ).getDate();
  target.setDate(Math.min(current.getDate(), lastDayOfMonth));
  return formatLocalDate(target);
}

export function getMonthBounds(value) {
  const current = parseLocalDate(value);
  const start = new Date(current.getFullYear(), current.getMonth(), 1, 12);
  const end = new Date(current.getFullYear(), current.getMonth() + 1, 0, 12);
  return {
    start: formatLocalDate(start),
    end: formatLocalDate(end),
  };
}

function addDays(date, offset) {
  const next = new Date(date);
  next.setDate(next.getDate() + offset);
  return next;
}

function startOfCalendarGrid(monthStart) {
  const offset = (monthStart.getDay() + 6) % 7;
  return addDays(monthStart, -offset);
}

function endOfCalendarGrid(monthEnd) {
  const offset = 6 - ((monthEnd.getDay() + 6) % 7);
  return addDays(monthEnd, offset);
}

export function buildCalendarDays(value) {
  const current = parseLocalDate(value);
  const monthStart = new Date(current.getFullYear(), current.getMonth(), 1, 12);
  const monthEnd = new Date(current.getFullYear(), current.getMonth() + 1, 0, 12);
  const gridStart = startOfCalendarGrid(monthStart);
  const gridEnd = endOfCalendarGrid(monthEnd);
  const days = [];

  for (let cursor = new Date(gridStart); cursor <= gridEnd; cursor = addDays(cursor, 1)) {
    days.push({
      date: formatLocalDate(cursor),
      dayOfMonth: cursor.getDate(),
      isCurrentMonth: cursor.getMonth() === current.getMonth(),
    });
  }

  return days;
}

export function formatMonthLabel(value) {
  const current = parseLocalDate(value);
  return `${current.getFullYear()} 年 ${current.getMonth() + 1} 月`;
}

export function formatSelectedDateLabel(value) {
  const current = parseLocalDate(value);
  return current.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}
