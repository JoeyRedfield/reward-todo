import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import AccountPage from "./Account";

const apiMocks = vi.hoisted(() => ({
  fetchAccountProfileMock: vi.fn(),
  fetchAccountSessionsMock: vi.fn(),
  revokeAccountSessionMock: vi.fn(),
  revokeOtherAccountSessionsMock: vi.fn(),
  fetchAccessTokensMock: vi.fn(),
  changePasswordMock: vi.fn(),
  createAccessTokenMock: vi.fn(),
  revokeAccessTokenMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchAccountProfile: apiMocks.fetchAccountProfileMock,
  fetchAccountSessions: apiMocks.fetchAccountSessionsMock,
  revokeAccountSession: apiMocks.revokeAccountSessionMock,
  revokeOtherAccountSessions: apiMocks.revokeOtherAccountSessionsMock,
  fetchAccessTokens: apiMocks.fetchAccessTokensMock,
  changePassword: apiMocks.changePasswordMock,
  createAccessToken: apiMocks.createAccessTokenMock,
  revokeAccessToken: apiMocks.revokeAccessTokenMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();
  apiMocks.fetchAccountProfileMock.mockResolvedValue({
    id: 1,
    username: "reward",
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
      {
        id: 2,
        created_at: "2026-06-21T00:00:00Z",
        expires_at: "2026-06-28T00:00:00Z",
        last_seen_at: "2026-06-21T08:00:00Z",
        is_current: false,
      },
    ],
  });
  apiMocks.revokeAccountSessionMock.mockResolvedValue(null);
  apiMocks.revokeOtherAccountSessionsMock.mockResolvedValue(null);
  apiMocks.fetchAccessTokensMock.mockResolvedValue({
    items: [
      {
        id: 9,
        name: "Codex API",
        token_type: "api",
        created_at: "2026-06-22T02:00:00Z",
        expires_at: "2026-07-22T02:00:00Z",
        last_seen_at: null,
      },
    ],
  });
  apiMocks.changePasswordMock.mockResolvedValue({
    id: 1,
    username: "reward",
    created_at: "2026-06-22T00:00:00Z",
    password_changed_at: "2026-06-22T04:00:00Z",
    last_login_at: "2026-06-22T01:00:00Z",
    api_token_enabled: true,
    mcp_enabled: true,
  });
  apiMocks.createAccessTokenMock.mockResolvedValue({
    id: 10,
    name: "Claude Desktop",
    token_type: "mcp",
    token: "mcp-secret-token",
    created_at: "2026-06-22T03:00:00Z",
    expires_at: "2026-07-22T03:00:00Z",
    api_base_url: null,
    mcp_url: "http://localhost:8088/mcp",
  });
  apiMocks.revokeAccessTokenMock.mockResolvedValue(null);
});

test("renders account profile, sessions and tokens", async () => {
  render(<AccountPage />);

  expect(await screen.findByRole("heading", { name: "账号设置" })).toBeInTheDocument();
  expect(screen.getByText("账号资料")).toBeInTheDocument();
  expect(screen.getByText("最近登录与会话")).toBeInTheDocument();
  expect(screen.getByText("密码修改")).toBeInTheDocument();
  expect(screen.getByText("Token 管理")).toBeInTheDocument();
  expect(screen.getByText("Codex API")).toBeInTheDocument();
});

test("submits password change from the account page", async () => {
  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

  fireEvent.change(screen.getAllByLabelText("当前密码")[0], {
    target: { value: "old-secret" },
  });
  fireEvent.change(screen.getByLabelText("新密码"), {
    target: { value: "new-secret" },
  });
  fireEvent.change(screen.getByLabelText("确认新密码"), {
    target: { value: "new-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "更新密码" }));

  await waitFor(() => {
    expect(apiMocks.changePasswordMock).toHaveBeenCalledWith({
      current_password: "old-secret",
      new_password: "new-secret",
      confirm_new_password: "new-secret",
    });
    expect(screen.getByText("密码已更新")).toBeInTheDocument();
  });
});

test("creates and shows a new mcp token", async () => {
  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

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
    expect(screen.getByDisplayValue(/"reward-todo-mcp"/)).toBeInTheDocument();
    expect(screen.getByText(/大语言模型也可能访问你的私有数据/)).toBeInTheDocument();
  });
});

test("shows agent config snippet for api token", async () => {
  apiMocks.createAccessTokenMock.mockResolvedValueOnce({
    id: 11,
    name: "Codex Agent",
    token_type: "api",
    token: "api-secret-token",
    created_at: "2026-06-22T03:00:00Z",
    expires_at: "2026-07-22T03:00:00Z",
    api_base_url: "http://localhost:8088/api",
    mcp_url: null,
  });

  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

  fireEvent.change(screen.getByLabelText("Token 名称"), {
    target: { value: "Codex Agent" },
  });
  fireEvent.change(screen.getByLabelText("Token 类型"), {
    target: { value: "api" },
  });
  fireEvent.change(screen.getAllByLabelText("当前密码")[1], {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成 Token" }));

  await waitFor(() => {
    expect(screen.getByDisplayValue(/REWARDTOOL_SERVER_BASEURL="http:\/\/localhost:8088\/api"/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/REWARDTOOL_TOKEN="api-secret-token"/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/sh skills\/reward-todo\/scripts\/rewardtools\.sh projects-list/)).toBeInTheDocument();
  });
});

test("supports custom expiry and never-expire token options", async () => {
  apiMocks.createAccessTokenMock.mockResolvedValueOnce({
    id: 12,
    name: "Long Lived API",
    token_type: "api",
    token: "api-custom-token",
    created_at: "2026-06-22T03:00:00Z",
    expires_at: "2026-06-22T05:00:00Z",
    api_base_url: "http://localhost:8088/api",
    mcp_url: null,
  });

  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

  fireEvent.change(screen.getByLabelText("Token 名称"), {
    target: { value: "Long Lived API" },
  });
  fireEvent.change(screen.getByLabelText("过期时间"), {
    target: { value: "custom" },
  });
  fireEvent.change(screen.getByLabelText("自定义过期秒数"), {
    target: { value: "7200" },
  });
  fireEvent.change(screen.getAllByLabelText("当前密码")[1], {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成 Token" }));

  await waitFor(() => {
    expect(apiMocks.createAccessTokenMock).toHaveBeenCalledWith({
      name: "Long Lived API",
      token_type: "api",
      password: "super-secret",
      expires_in_seconds: 7200,
    });
  });

  apiMocks.createAccessTokenMock.mockResolvedValueOnce({
    id: 13,
    name: "Never Expire API",
    token_type: "api",
    token: "api-never-expire-token",
    created_at: "2026-06-22T03:00:00Z",
    expires_at: null,
    api_base_url: "http://localhost:8088/api",
    mcp_url: null,
  });

  fireEvent.change(screen.getByLabelText("Token 名称"), {
    target: { value: "Never Expire API" },
  });
  fireEvent.change(screen.getByLabelText("过期时间"), {
    target: { value: "never" },
  });
  fireEvent.change(screen.getAllByLabelText("当前密码")[1], {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成 Token" }));

  await waitFor(() => {
    expect(apiMocks.createAccessTokenMock).toHaveBeenCalledWith({
      name: "Never Expire API",
      token_type: "api",
      password: "super-secret",
      expires_in_seconds: 0,
    });
    expect(screen.getByText(/这个 Token 永不过期/)).toBeInTheDocument();
  });
});

test("revokes session and token", async () => {
  render(<AccountPage />);

  expect(await screen.findByText("其他设备会话")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "撤销会话 2" }));
  fireEvent.click(screen.getByRole("button", { name: "撤销 Token 9" }));

  await waitFor(() => {
    expect(apiMocks.revokeAccountSessionMock).toHaveBeenCalledWith(2);
    expect(apiMocks.revokeAccessTokenMock).toHaveBeenCalledWith(9);
  });
});

test("revokes all other sessions", async () => {
  render(<AccountPage />);

  expect(await screen.findByText("其他设备会话")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "退出其他会话" }));

  await waitFor(() => {
    expect(apiMocks.revokeOtherAccountSessionsMock).toHaveBeenCalledTimes(1);
  });
});

test("hides token creation when api token and mcp are both disabled", async () => {
  apiMocks.fetchAccountProfileMock.mockResolvedValueOnce({
    id: 1,
    username: "reward",
    created_at: "2026-06-22T00:00:00Z",
    password_changed_at: "2026-06-22T00:00:00Z",
    last_login_at: "2026-06-22T01:00:00Z",
    api_token_enabled: false,
    mcp_enabled: false,
  });

  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

  expect(screen.getByText("当前服务未启用 Agent API Token 或 MCP。")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "生成 Token" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Token 类型")).not.toBeInTheDocument();
});

test("only shows enabled token types from server capabilities", async () => {
  apiMocks.fetchAccountProfileMock.mockResolvedValueOnce({
    id: 1,
    username: "reward",
    created_at: "2026-06-22T00:00:00Z",
    password_changed_at: "2026-06-22T00:00:00Z",
    last_login_at: "2026-06-22T01:00:00Z",
    api_token_enabled: false,
    mcp_enabled: true,
  });

  render(<AccountPage />);

  await screen.findByRole("heading", { name: "账号设置" });

  const tokenTypeSelect = screen.getByLabelText("Token 类型");
  const tokenTypeOptions = Array.from(tokenTypeSelect.querySelectorAll("option")).map(
    (option) => option.value
  );

  expect(tokenTypeOptions).toEqual(["mcp"]);
});
