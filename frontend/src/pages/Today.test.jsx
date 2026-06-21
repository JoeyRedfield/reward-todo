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

const {
  fetchDailyTasksMock,
  fetchRewardSummaryMock,
  completeDailyTaskMock,
} = vi.hoisted(() => ({
  fetchDailyTasksMock: vi.fn(),
  fetchRewardSummaryMock: vi.fn(),
  completeDailyTaskMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchDailyTasks: fetchDailyTasksMock,
  fetchRewardSummary: fetchRewardSummaryMock,
  completeDailyTask: completeDailyTaskMock,
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
    ...task,
    status: "completed",
    actual_duration_minutes: 28,
    completed_at: "2026-06-21T10:00:00Z",
  });
});

test("shows today board data", async () => {
  render(<TodayPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  expect(screen.getByText("当前奖励余额")).toBeInTheDocument();
});

test("completes a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([task])
    .mockResolvedValueOnce([
      {
        ...task,
        status: "completed",
        actual_duration_minutes: 28,
        completed_at: "2026-06-21T10:00:00Z",
      },
    ]);
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
