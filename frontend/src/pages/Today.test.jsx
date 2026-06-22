import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
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

const {
  fetchDailyTasksMock,
  fetchRewardSummaryMock,
  completeDailyTaskMock,
  reopenDailyTaskMock,
} = vi.hoisted(() => ({
  fetchDailyTasksMock: vi.fn(),
  fetchRewardSummaryMock: vi.fn(),
  completeDailyTaskMock: vi.fn(),
  reopenDailyTaskMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchDailyTasks: fetchDailyTasksMock,
  fetchRewardSummary: fetchRewardSummaryMock,
  completeDailyTask: completeDailyTaskMock,
  reopenDailyTask: reopenDailyTaskMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();
  fetchDailyTasksMock.mockResolvedValue([task]);
  fetchRewardSummaryMock.mockResolvedValue({
    current_balance: 0,
    today_earned: 0,
  });
  completeDailyTaskMock.mockResolvedValue({
    ...completedTask,
  });
  reopenDailyTaskMock.mockResolvedValue(task);
});

test("shows today board data", async () => {
  render(<TodayPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  expect(screen.getByText("当前奖励余额")).toBeInTheDocument();
});

test("completes a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([task])
    .mockResolvedValueOnce([completedTask]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 2000, today_earned: 2000 });

  render(<TodayPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "完成" }));
  fireEvent.change(screen.getByPlaceholderText("选填，单位分钟"), {
    target: { value: "28" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认完成" }));

  await waitFor(() => {
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });
});

test("shows reopen action for completed tasks", async () => {
  fetchDailyTasksMock.mockResolvedValue([completedTask]);

  render(<TodayPage />);

  expect(await screen.findByRole("button", { name: "撤销完成" })).toBeInTheDocument();
});

test("reopens a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([completedTask])
    .mockResolvedValueOnce([task]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 2000, today_earned: 2000 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "撤销完成" }));

  await waitFor(() => {
    expect(reopenDailyTaskMock).toHaveBeenCalledWith(1);
    expect(screen.getByRole("button", { name: "完成" })).toBeInTheDocument();
  });
});

test("shows error when reopen fails", async () => {
  fetchDailyTasksMock.mockResolvedValue([completedTask]);
  reopenDailyTaskMock.mockRejectedValue(new Error("撤销失败"));

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "撤销完成" }));

  expect(await screen.findByText("撤销失败")).toBeInTheDocument();
});
