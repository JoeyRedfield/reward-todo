import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import TodayPage from "./Today";

const task = {
  id: 1,
  date: "2026-06-21",
  project_id: 1,
  task_template_id: 1,
  name_snapshot: "跑步 30 分钟",
  estimated_duration_minutes_snapshot: 30,
  reward_amount_snapshot: 2000,
  status: "pending",
  actual_duration_minutes: null,
  completed_at: null,
};

const completedTask = {
  ...task,
  status: "completed",
  actual_duration_minutes: 28,
  completed_at: "2026-06-21T10:00:00Z",
};

const selectedDateTask = {
  id: 2,
  date: "2026-06-22",
  project_id: 2,
  task_template_id: 2,
  name_snapshot: "晨间复盘 15 分钟",
  estimated_duration_minutes_snapshot: 15,
  reward_amount_snapshot: 900,
  status: "pending",
  actual_duration_minutes: null,
  completed_at: null,
};

const projects = [
  { id: 1, name: "健身", status: "active", sort_order: 0 },
  { id: 2, name: "写作", status: "active", sort_order: 1 },
];

const templates = [
  {
    id: 1,
    project_id: 1,
    name: "跑步 30 分钟",
    default_estimated_duration_minutes: 30,
    default_reward_amount: 2000,
    notes: "",
    is_active: true,
  },
  {
    id: 2,
    project_id: 2,
    name: "晨间复盘 15 分钟",
    default_estimated_duration_minutes: 15,
    default_reward_amount: 900,
    notes: "",
    is_active: true,
  },
  {
    id: 3,
    project_id: 1,
    name: "停用模板",
    default_estimated_duration_minutes: 20,
    default_reward_amount: 600,
    notes: "",
    is_active: false,
  },
];

const calendarSummary = [
  { date: "2026-06-21", task_count: 1, completed_count: 0 },
  { date: "2026-06-23", task_count: 1, completed_count: 1 },
];

const {
  completeDailyTaskMock,
  createDailyTaskMock,
  fetchDailyTaskCalendarMock,
  fetchDailyTasksMock,
  fetchProjectsMock,
  fetchRewardSummaryMock,
  fetchTaskTemplatesMock,
  reopenDailyTaskMock,
} = vi.hoisted(() => ({
  completeDailyTaskMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
  fetchDailyTaskCalendarMock: vi.fn(),
  fetchDailyTasksMock: vi.fn(),
  fetchProjectsMock: vi.fn(),
  fetchRewardSummaryMock: vi.fn(),
  fetchTaskTemplatesMock: vi.fn(),
  reopenDailyTaskMock: vi.fn(),
}));

vi.mock("../utils/date", async () => {
  const actual = await vi.importActual("../utils/date");

  return {
    ...actual,
    formatLocalDate: (date) =>
      actual.formatLocalDate(date ?? new Date("2026-06-21T08:00:00+08:00")),
  };
});

vi.mock("../api/client", () => ({
  completeDailyTask: completeDailyTaskMock,
  createDailyTask: createDailyTaskMock,
  fetchDailyTaskCalendar: fetchDailyTaskCalendarMock,
  fetchDailyTasks: fetchDailyTasksMock,
  fetchProjects: fetchProjectsMock,
  fetchRewardSummary: fetchRewardSummaryMock,
  fetchTaskTemplates: fetchTaskTemplatesMock,
  reopenDailyTask: reopenDailyTaskMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();

  fetchDailyTasksMock.mockResolvedValue([task]);
  fetchDailyTaskCalendarMock.mockResolvedValue(calendarSummary);
  fetchRewardSummaryMock.mockResolvedValue({
    current_balance: 0,
    today_earned: 0,
  });
  fetchProjectsMock.mockResolvedValue(projects);
  fetchTaskTemplatesMock.mockResolvedValue(templates);
  createDailyTaskMock.mockResolvedValue({ id: 3 });
  completeDailyTaskMock.mockResolvedValue(completedTask);
  reopenDailyTaskMock.mockResolvedValue(task);
});

test("shows calendar markers and quick add options", async () => {
  render(<TodayPage />);

  expect(await screen.findByText("快速加任务")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "加入 2026-06-21：跑步 30 分钟" })
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "选择 2026-06-23，1 项任务" })).toBeInTheDocument();
});

test("switches selected date and shows empty state", async () => {
  fetchDailyTasksMock.mockResolvedValueOnce([task]).mockResolvedValueOnce([]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "选择 2026-06-22" }));

  await waitFor(() => {
    expect(fetchDailyTasksMock).toHaveBeenLastCalledWith("2026-06-22");
    expect(fetchRewardSummaryMock).toHaveBeenLastCalledWith("2026-06-22");
    expect(screen.getByText("2026-06-22 还没有安排任务。")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "加入 2026-06-22：跑步 30 分钟" })
    ).toBeInTheDocument();
  });
});

test("adds a template to the selected date and refreshes the board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([task])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([selectedDateTask]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 900, today_earned: 0 });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "选择 2026-06-22" }));
  await screen.findByText("2026-06-22 还没有安排任务。");

  fireEvent.click(
    screen.getByRole("button", { name: "加入 2026-06-22：晨间复盘 15 分钟" })
  );

  await waitFor(() => {
    expect(createDailyTaskMock).toHaveBeenCalledWith({
      date: "2026-06-22",
      task_template_id: 2,
      estimated_duration_minutes: 15,
      reward_amount: 900,
    });
    expect(screen.getByText("晨间复盘 15 分钟")).toBeInTheDocument();
  });
});

test("completes a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([task])
    .mockResolvedValueOnce([completedTask]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 2000, today_earned: 2000 });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "完成" }));
  fireEvent.change(screen.getByPlaceholderText("选填，单位分钟"), {
    target: { value: "28" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认完成" }));

  await waitFor(() => {
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });
});

test("reopens a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([completedTask])
    .mockResolvedValueOnce([task]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 2000, today_earned: 2000 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  await screen.findByText("实际时长 28 分钟");
  fireEvent.click(screen.getByRole("button", { name: "撤销完成" }));

  await waitFor(() => {
    expect(reopenDailyTaskMock).toHaveBeenCalledWith(1);
    expect(screen.getAllByText("¥0.00")).toHaveLength(2);
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "撤销完成" })).not.toBeInTheDocument();
    expect(screen.queryByText("实际时长 28 分钟")).not.toBeInTheDocument();
  });
});

test("shows error when reopen fails", async () => {
  fetchDailyTasksMock.mockResolvedValue([completedTask]);
  reopenDailyTaskMock.mockRejectedValue(new Error("撤销失败"));

  render(<TodayPage />);
  await screen.findByText("实际时长 28 分钟");
  fireEvent.click(screen.getByRole("button", { name: "撤销完成" }));

  expect(await screen.findByText("撤销失败")).toBeInTheDocument();
});
