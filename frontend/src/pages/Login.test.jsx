import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import LoginPage from "./Login";

const authState = {
  loading: false,
  user: null,
  sessionExpired: false,
  loginError: null,
};

const authMocks = vi.hoisted(() => ({
  loginMock: vi.fn(),
  clearSessionExpiredMock: vi.fn(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    loading: authState.loading,
    user: authState.user,
    sessionExpired: authState.sessionExpired,
    clearSessionExpired: authMocks.clearSessionExpiredMock,
    login: authMocks.loginMock,
  }),
}));

function renderLogin(initialEntry = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/today" element={<div>today page</div>} />
        <Route path="/projects" element={<div>projects page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.loading = false;
  authState.user = null;
  authState.sessionExpired = false;
  authState.loginError = null;

  authMocks.loginMock.mockImplementation(async () => {
    if (authState.loginError) {
      throw authState.loginError;
    }
    return { id: 1, username: "reward", last_login_at: null };
  });
  authMocks.clearSessionExpiredMock.mockImplementation(() => {});
});

test("redirects authenticated users away from login", async () => {
  authState.user = { id: 1, username: "reward", last_login_at: null };

  renderLogin("/login?redirect=%2Fprojects");

  expect(await screen.findByText("projects page")).toBeInTheDocument();
});

test("shows session expired message and clears flag on submit", async () => {
  authState.sessionExpired = true;

  renderLogin();

  expect(screen.getByText("登录已失效，请重新登录")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("用户名"), {
    target: { value: "reward" },
  });
  fireEvent.change(screen.getByLabelText("密码"), {
    target: { value: "super-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));

  await waitFor(() => {
    expect(authMocks.clearSessionExpiredMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText("today page")).toBeInTheDocument();
  });
});

test("shows login failure message", async () => {
  authState.loginError = new Error("用户名或密码错误");

  renderLogin();

  fireEvent.change(screen.getByLabelText("用户名"), {
    target: { value: "reward" },
  });
  fireEvent.change(screen.getByLabelText("密码"), {
    target: { value: "wrong-pass" },
  });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));

  expect(await screen.findByText("用户名或密码错误")).toBeInTheDocument();
});
