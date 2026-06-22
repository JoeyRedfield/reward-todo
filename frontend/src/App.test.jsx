import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

const authState = {
  currentUser: null,
  loginResult: {
    id: 1,
    username: "reward",
    display_name: "Reward",
    email: "reward@local.invalid",
    last_login_at: null,
  },
  registerResult: {
    id: 2,
    username: "new-user",
    display_name: "New User",
    email: "new-user@example.com",
    last_login_at: null,
  },
  changePasswordError: null,
  loginError: null,
  registerError: null,
};

const apiMocks = vi.hoisted(() => ({
  fetchCurrentUserMock: vi.fn(),
  loginMock: vi.fn(),
  registerMock: vi.fn(),
  logoutMock: vi.fn(),
  changePasswordMock: vi.fn(),
  fetchDailyTasksMock: vi.fn(),
  fetchRewardSummaryMock: vi.fn(),
  completeDailyTaskMock: vi.fn(),
  reopenDailyTaskMock: vi.fn(),
  fetchProjectsMock: vi.fn(),
  fetchTaskTemplatesMock: vi.fn(),
  createProjectMock: vi.fn(),
  updateProjectMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  updateTaskTemplateMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
  fetchRewardLedgerMock: vi.fn(),
  spendRewardMock: vi.fn(),
  fetchAccountProfileMock: vi.fn(),
  fetchAccountSessionsMock: vi.fn(),
  revokeAccountSessionMock: vi.fn(),
  revokeOtherAccountSessionsMock: vi.fn(),
  fetchAccessTokensMock: vi.fn(),
  createAccessTokenMock: vi.fn(),
  revokeAccessTokenMock: vi.fn(),
}));

vi.mock("./api/client", () => ({
  setUnauthorizedHandler: vi.fn(),
  fetchCurrentUser: apiMocks.fetchCurrentUserMock,
  login: apiMocks.loginMock,
  register: apiMocks.registerMock,
  logout: apiMocks.logoutMock,
  changePassword: apiMocks.changePasswordMock,
  fetchDailyTasks: apiMocks.fetchDailyTasksMock,
  fetchRewardSummary: apiMocks.fetchRewardSummaryMock,
  completeDailyTask: apiMocks.completeDailyTaskMock,
  reopenDailyTask: apiMocks.reopenDailyTaskMock,
  fetchProjects: apiMocks.fetchProjectsMock,
  fetchTaskTemplates: apiMocks.fetchTaskTemplatesMock,
  createProject: apiMocks.createProjectMock,
  updateProject: apiMocks.updateProjectMock,
  createTaskTemplate: apiMocks.createTaskTemplateMock,
  updateTaskTemplate: apiMocks.updateTaskTemplateMock,
  createDailyTask: apiMocks.createDailyTaskMock,
  fetchRewardLedger: apiMocks.fetchRewardLedgerMock,
  spendReward: apiMocks.spendRewardMock,
  fetchAccountProfile: apiMocks.fetchAccountProfileMock,
  fetchAccountSessions: apiMocks.fetchAccountSessionsMock,
  revokeAccountSession: apiMocks.revokeAccountSessionMock,
  revokeOtherAccountSessions: apiMocks.revokeOtherAccountSessionsMock,
  fetchAccessTokens: apiMocks.fetchAccessTokensMock,
  createAccessToken: apiMocks.createAccessTokenMock,
  revokeAccessToken: apiMocks.revokeAccessTokenMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

function renderAt(pathname) {
  window.history.pushState({}, "", pathname);
  return render(<App />);
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.currentUser = null;
  authState.loginError = null;
  authState.changePasswordError = null;
  authState.registerError = null;

  apiMocks.fetchCurrentUserMock.mockImplementation(async () => {
    if (!authState.currentUser) {
      throw new Error("未登录");
    }
    return authState.currentUser;
  });
  apiMocks.loginMock.mockImplementation(async () => {
    if (authState.loginError) {
      throw authState.loginError;
    }
    authState.currentUser = authState.loginResult;
    return authState.loginResult;
  });
  apiMocks.registerMock.mockImplementation(async () => {
    if (authState.registerError) {
      throw authState.registerError;
    }
    authState.currentUser = authState.registerResult;
    return authState.registerResult;
  });
  apiMocks.logoutMock.mockResolvedValue({ ok: true });
  apiMocks.changePasswordMock.mockImplementation(async () => {
    if (authState.changePasswordError) {
      throw authState.changePasswordError;
    }
    return authState.loginResult;
  });

  apiMocks.fetchDailyTasksMock.mockResolvedValue([]);
  apiMocks.fetchRewardSummaryMock.mockResolvedValue({
    current_balance: 0,
    today_earned: 0,
  });
  apiMocks.completeDailyTaskMock.mockResolvedValue(null);
  apiMocks.reopenDailyTaskMock.mockResolvedValue(null);
  apiMocks.fetchProjectsMock.mockResolvedValue([
    { id: 1, name: "健身", status: "active", sort_order: 0 },
  ]);
  apiMocks.fetchTaskTemplatesMock.mockResolvedValue([
    {
      id: 1,
      project_id: 1,
      name: "跑步 30 分钟",
      default_estimated_duration_minutes: 30,
      default_reward_amount: 2000,
      notes: "",
      is_active: true,
    },
  ]);
  apiMocks.createProjectMock.mockResolvedValue({
    id: 2,
    name: "写作",
    status: "active",
    sort_order: 1,
  });
  apiMocks.updateProjectMock.mockResolvedValue({
    id: 1,
    name: "健身",
    status: "active",
    sort_order: 0,
  });
  apiMocks.createTaskTemplateMock.mockResolvedValue({ id: 2 });
  apiMocks.updateTaskTemplateMock.mockResolvedValue({
    id: 1,
    project_id: 1,
    name: "跑步 30 分钟",
    default_estimated_duration_minutes: 30,
    default_reward_amount: 2000,
    notes: "",
    is_active: true,
  });
  apiMocks.createDailyTaskMock.mockResolvedValue({ id: 3 });
  apiMocks.fetchRewardLedgerMock.mockResolvedValue([]);
  apiMocks.spendRewardMock.mockResolvedValue({ id: 4 });
  apiMocks.fetchAccountProfileMock.mockResolvedValue({
    id: 1,
    username: "reward",
    display_name: "Reward",
    email: "reward@local.invalid",
    created_at: "2026-06-22T00:00:00Z",
    password_changed_at: "2026-06-22T00:00:00Z",
    last_login_at: "2026-06-22T01:00:00Z",
    api_token_enabled: true,
    mcp_enabled: true,
  });
  apiMocks.fetchAccountSessionsMock.mockResolvedValue({
    items: [
      {
        id: 1,
        created_at: "2026-06-22T00:00:00Z",
        expires_at: "2026-06-29T00:00:00Z",
        last_seen_at: "2026-06-22T01:00:00Z",
        is_current: true,
      },
    ],
  });
  apiMocks.revokeAccountSessionMock.mockResolvedValue(null);
  apiMocks.revokeOtherAccountSessionsMock.mockResolvedValue(null);
  apiMocks.fetchAccessTokensMock.mockResolvedValue({
    items: [],
  });
  apiMocks.createAccessTokenMock.mockResolvedValue({
    id: 9,
    name: "Claude Desktop",
    token_type: "mcp",
    token: "mcp-secret-token",
    created_at: "2026-06-22T02:00:00Z",
    expires_at: "2026-07-22T02:00:00Z",
    api_base_url: null,
    mcp_url: "http://localhost:8088/mcp",
  });
  apiMocks.revokeAccessTokenMock.mockResolvedValue(null);
});

test("redirects unauthenticated users to login", async () => {
  renderAt("/today");

  expect(await screen.findByRole("heading", { name: "登录" })).toBeInTheDocument();
});

test("renders signup page at /signup", async () => {
  renderAt("/signup");

  expect(await screen.findByRole("heading", { name: "创建账号" })).toBeInTheDocument();
  expect(screen.getByText("第 1 步，共 3 步")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "基础信息" })).toBeInTheDocument();
});

test("moves signup flow to next step after submitting basic info", async () => {
  renderAt("/signup");

  await screen.findByRole("heading", { name: "创建账号" });
  fireEvent.change(screen.getByLabelText("用户名"), {
    target: { value: "new-user" },
  });
  fireEvent.change(screen.getByLabelText("显示名称"), {
    target: { value: "New User" },
  });
  fireEvent.change(screen.getByLabelText("邮箱"), {
    target: { value: "new-user@example.com" },
  });
  fireEvent.change(screen.getByLabelText("密码"), {
    target: { value: "super-secret" },
  });
  fireEvent.change(screen.getByLabelText("确认密码"), {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "继续" }));

  await waitFor(() => {
    expect(apiMocks.registerMock).not.toHaveBeenCalled();
    expect(screen.getByText("第 2 步，共 3 步")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "初始化工作台" })).toBeInTheDocument();
    expect(screen.getByText("创建默认工作区")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "创建账号" }));

  await waitFor(() => {
    expect(apiMocks.registerMock).toHaveBeenCalledWith({
      username: "new-user",
      display_name: "New User",
      email: "new-user@example.com",
      password: "super-secret",
      confirm_password: "super-secret",
      create_default_workspace: true,
    });
    expect(screen.getByText("第 3 步，共 3 步")).toBeInTheDocument();
    expect(screen.getByText("账号创建成功")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "进入今日面板" })
    ).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "进入今日面板" }));

  await waitFor(() => {
    expect(screen.getByText("今天还没有安排任务。")).toBeInTheDocument();
  });
});

test("redirects authenticated users away from signup", async () => {
  authState.currentUser = authState.loginResult;

  renderAt("/signup");

  expect(await screen.findByText("今天还没有安排任务。")).toBeInTheDocument();
});

test("redirects back to requested page after login", async () => {
  renderAt("/rewards");

  await screen.findByRole("heading", { name: "登录" });
  fireEvent.change(screen.getByLabelText("用户名"), {
    target: { value: "reward" },
  });
  fireEvent.change(screen.getByLabelText("密码"), {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));

  await waitFor(() => {
    expect(screen.getByText("把奖励额度当作账本，明确地赚、明确地花。")).toBeInTheDocument();
  });
});

test("shows account actions in sidebar", async () => {
  authState.currentUser = authState.loginResult;

  renderAt("/today");

  expect(await screen.findByText("Reward")).toBeInTheDocument();
  expect(screen.getByText("@reward")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "账号设置" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "登出" })).toBeInTheDocument();
});

test("logs out from sidebar account panel", async () => {
  authState.currentUser = authState.loginResult;

  renderAt("/today");

  await screen.findByText("Reward");
  fireEvent.click(screen.getByRole("button", { name: "登出" }));

  await waitFor(() => {
    expect(apiMocks.logoutMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "登录" })).toBeInTheDocument();
  });
});

test("shows password change success feedback", async () => {
  authState.currentUser = authState.loginResult;

  renderAt("/account");

  await screen.findByText("账号资料");
  fireEvent.change(screen.getAllByLabelText("当前密码")[0], {
    target: { value: "super-secret" },
  });
  fireEvent.change(screen.getByLabelText("新密码"), {
    target: { value: "new-secret1" },
  });
  fireEvent.change(screen.getByLabelText("确认新密码"), {
    target: { value: "new-secret1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "更新密码" }));

  await waitFor(() => {
    expect(screen.getByText("密码已更新")).toBeInTheDocument();
  });
});

test("shows password change error feedback", async () => {
  authState.currentUser = authState.loginResult;
  authState.changePasswordError = new Error("当前密码错误");

  renderAt("/account");

  await screen.findByText("账号资料");
  fireEvent.change(screen.getAllByLabelText("当前密码")[0], {
    target: { value: "wrong-pass" },
  });
  fireEvent.change(screen.getByLabelText("新密码"), {
    target: { value: "new-secret1" },
  });
  fireEvent.change(screen.getByLabelText("确认新密码"), {
    target: { value: "new-secret1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "更新密码" }));

  await waitFor(() => {
    expect(screen.getByText("当前密码错误")).toBeInTheDocument();
  });
});

test("renders account settings page and creates mcp token", async () => {
  authState.currentUser = authState.loginResult;

  renderAt("/account");

  expect(await screen.findByText("账号资料")).toBeInTheDocument();
  expect(screen.getByText("用户名")).toBeInTheDocument();
  expect(screen.getByText("当前会话")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Token 名称"), {
    target: { value: "Claude Desktop" },
  });
  fireEvent.change(screen.getByLabelText("Token 类型"), {
    target: { value: "mcp" },
  });
  fireEvent.change(screen.getAllByLabelText("当前密码")[1], {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成 Token" }));

  await waitFor(() => {
    expect(apiMocks.createAccessTokenMock).toHaveBeenCalledWith({
      name: "Claude Desktop",
      token_type: "mcp",
      password: "super-secret",
      expires_in_seconds: 2592000,
    });
    expect(screen.getByDisplayValue("mcp-secret-token")).toBeInTheDocument();
    expect(screen.getByDisplayValue("http://localhost:8088/mcp")).toBeInTheDocument();
  });
});
