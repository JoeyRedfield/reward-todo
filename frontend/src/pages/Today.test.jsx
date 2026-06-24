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

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

const {
  completeDailyTaskMock,
  createDailyTaskMock,
  deleteDailyTaskMock,
  fetchDailyTaskCalendarMock,
  fetchDailyTasksMock,
  fetchProjectsMock,
  fetchRewardSummaryMock,
  fetchTaskTemplatesMock,
  reopenDailyTaskMock,
} = vi.hoisted(() => ({
  completeDailyTaskMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
  deleteDailyTaskMock: vi.fn(),
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
  deleteDailyTask: deleteDailyTaskMock,
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
  vi.stubGlobal("confirm", vi.fn(() => true));

  fetchDailyTasksMock.mockResolvedValue([task]);
  fetchDailyTaskCalendarMock.mockResolvedValue(calendarSummary);
  fetchRewardSummaryMock.mockResolvedValue({
    current_balance: 0,
    today_earned: 0,
  });
  fetchProjectsMock.mockResolvedValue(projects);
  fetchTaskTemplatesMock.mockResolvedValue(templates);
  createDailyTaskMock.mockResolvedValue({ id: 3 });
  deleteDailyTaskMock.mockResolvedValue(null);
  completeDailyTaskMock.mockResolvedValue(completedTask);
  reopenDailyTaskMock.mockResolvedValue(task);
});

const standaloneTask = {
  id: 4,
  date: "2026-06-22",
  project_id: null,
  task_template_id: null,
  name_snapshot: "临时买菜",
  estimated_duration_minutes_snapshot: 20,
  reward_amount_snapshot: 0,
  status: "pending",
  actual_duration_minutes: null,
  completed_at: null,
};

const completedStandaloneTask = {
  ...standaloneTask,
  id: 5,
  status: "completed",
  completed_at: "2026-06-22T11:00:00Z",
};

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

test("shows standalone add form even when no templates are available", async () => {
  fetchTaskTemplatesMock.mockResolvedValue([]);

  render(<TodayPage />);

  expect(await screen.findByLabelText("任务名称")).toBeInTheDocument();
  expect(screen.getByLabelText("预计时长（分钟）")).toBeInTheDocument();
  expect(screen.getByLabelText("奖励金额（元）")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("0.00")).toBeInTheDocument();
  expect(screen.getByText("留空按 ¥0.00 处理")).toBeInTheDocument();
  expect(screen.getByText("当前没有可直接加入台账的启用模板。")).toBeInTheDocument();
});

test("adds a standalone task with empty reward as zero and refreshes selected date", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([task])
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([standaloneTask]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "选择 2026-06-22" }));
  await screen.findByText("2026-06-22 还没有安排任务。");

  fireEvent.change(screen.getByLabelText("任务名称"), {
    target: { value: "临时买菜" },
  });
  fireEvent.change(screen.getByLabelText("预计时长（分钟）"), {
    target: { value: "20" },
  });
  fireEvent.click(screen.getByRole("button", { name: "直接添加任务" }));

  await waitFor(() => {
    expect(createDailyTaskMock).toHaveBeenCalledWith({
      date: "2026-06-22",
      name: "临时买菜",
      estimated_duration_minutes: 20,
      reward_amount: 0,
    });
    expect(screen.getByText("临时买菜")).toBeInTheDocument();
  });
});

test("shows standalone add pending state while request is in flight", async () => {
  const createRequest = createDeferred();
  createDailyTaskMock.mockReturnValue(createRequest.promise);
  fetchDailyTasksMock.mockResolvedValue([]);
  fetchRewardSummaryMock.mockResolvedValue({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  await screen.findByText("今天还没有安排任务。");

  fireEvent.change(screen.getByLabelText("任务名称"), {
    target: { value: "临时买菜" },
  });
  fireEvent.change(screen.getByLabelText("预计时长（分钟）"), {
    target: { value: "20" },
  });
  fireEvent.click(screen.getByRole("button", { name: "直接添加任务" }));

  await waitFor(() => {
    expect(createDailyTaskMock).toHaveBeenCalledWith({
      date: "2026-06-21",
      name: "临时买菜",
      estimated_duration_minutes: 20,
      reward_amount: 0,
    });
    expect(screen.getByRole("button", { name: "添加中..." })).toBeDisabled();
    expect(screen.getByLabelText("任务名称")).toBeDisabled();
    expect(screen.getByLabelText("预计时长（分钟）")).toBeDisabled();
    expect(screen.getByLabelText("奖励金额（元）")).toBeDisabled();
  });

  createRequest.resolve({ id: 9 });
  await createRequest.promise;
});

test("marks standalone tasks and only shows delete buttons for standalone tasks", async () => {
  fetchDailyTasksMock.mockResolvedValue([task, standaloneTask, completedStandaloneTask]);

  render(<TodayPage />);

  expect(await screen.findAllByText("独立任务")).toHaveLength(2);
  expect(screen.getAllByRole("button", { name: "删除" })).toHaveLength(2);
  expect(screen.getAllByRole("button", { name: "完成" })).toHaveLength(2);
  expect(screen.getByRole("button", { name: "撤销完成" })).toBeInTheDocument();
});

test("deletes a standalone task and refreshes the board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([standaloneTask])
    .mockResolvedValueOnce([]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  await screen.findByText("临时买菜");
  fireEvent.click(screen.getByRole("button", { name: "删除" }));

  await waitFor(() => {
    expect(confirm).toHaveBeenCalledWith("确认删除任务「临时买菜」吗？");
    expect(deleteDailyTaskMock).toHaveBeenCalledWith(4);
    expect(screen.getByText("今天还没有安排任务。")).toBeInTheDocument();
  });
});

test("uses completed standalone delete confirmation copy with reward warning", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([completedStandaloneTask])
    .mockResolvedValueOnce([]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });

  render(<TodayPage />);
  await screen.findByText("临时买菜");
  fireEvent.click(screen.getByRole("button", { name: "删除" }));

  await waitFor(() => {
    expect(confirm).toHaveBeenCalledWith(
      "确认删除已完成任务「临时买菜」吗？删除后会扣回已发放奖励。"
    );
    expect(deleteDailyTaskMock).toHaveBeenCalledWith(5);
  });
});

test("keeps reopen label unchanged while standalone deletion is pending", async () => {
  const deleteRequest = createDeferred();
  fetchDailyTasksMock.mockResolvedValue([completedStandaloneTask]);
  deleteDailyTaskMock.mockReturnValue(deleteRequest.promise);

  render(<TodayPage />);
  await screen.findByText("临时买菜");
  fireEvent.click(screen.getByRole("button", { name: "删除" }));

  await waitFor(() => {
    expect(deleteDailyTaskMock).toHaveBeenCalledWith(5);
    expect(screen.getByRole("button", { name: "删除中..." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "撤销完成" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "撤销中..." })).not.toBeInTheDocument();
  });

  deleteRequest.resolve(null);
  await deleteRequest.promise;
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

test("keeps the newly selected date when a pending completion finishes later", async () => {
  const finishRequest = createDeferred();
  let initialTodayLoad = true;
  completeDailyTaskMock.mockReturnValue(finishRequest.promise);
  fetchDailyTasksMock.mockImplementation(async (date) => {
    if (date === "2026-06-21") {
      if (initialTodayLoad) {
        initialTodayLoad = false;
        return [task];
      }
      return [completedTask];
    }

    if (date === "2026-06-22") {
      return [];
    }

    return [];
  });
  fetchRewardSummaryMock.mockImplementation(async (date) => {
    if (date === "2026-06-21") {
      return initialTodayLoad
        ? { current_balance: 0, today_earned: 0 }
        : { current_balance: 2000, today_earned: 2000 };
    }

    return { current_balance: 0, today_earned: 0 };
  });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "完成" }));
  fireEvent.change(screen.getByPlaceholderText("选填，单位分钟"), {
    target: { value: "28" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认完成" }));
  fireEvent.click(screen.getByRole("button", { name: "选择 2026-06-22" }));

  await waitFor(() => {
    expect(fetchDailyTasksMock).toHaveBeenLastCalledWith("2026-06-22");
    expect(screen.getByText("2026-06-22 还没有安排任务。")).toBeInTheDocument();
  });

  finishRequest.resolve(completedTask);

  await waitFor(() => {
    expect(completeDailyTaskMock).toHaveBeenCalledWith(1, 28);
    expect(fetchDailyTasksMock.mock.calls.slice(1).every(([date]) => date !== "2026-06-21")).toBe(
      true
    );
    expect(screen.getByText("2026-06-22 还没有安排任务。")).toBeInTheDocument();
    expect(screen.queryByText("实际时长 28 分钟")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "撤销完成" })).not.toBeInTheDocument();
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
