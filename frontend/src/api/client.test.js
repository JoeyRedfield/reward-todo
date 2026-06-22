import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  changePassword,
  fetchCurrentUser,
  login,
  setUnauthorizedHandler,
} from "./client";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

test("triggers unauthorized handler for non-auth-endpoint 401 responses", async () => {
  const unauthorized = vi.fn();
  setUnauthorizedHandler(unauthorized);
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "Session expired" }),
  });

  await expect(fetchCurrentUser()).rejects.toThrow("Session expired");

  expect(unauthorized).toHaveBeenCalledTimes(1);
});

test("does not trigger unauthorized handler for auth endpoint 401 responses", async () => {
  const unauthorized = vi.fn();
  setUnauthorizedHandler(unauthorized);
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "Invalid username or password" }),
  });

  await expect(
    changePassword({
      current_password: "wrong-pass",
      new_password: "new-secret1",
      confirm_new_password: "new-secret1",
    })
  ).rejects.toThrow("Invalid username or password");

  expect(unauthorized).not.toHaveBeenCalled();
});

test("does not trigger unauthorized handler for login failures", async () => {
  const unauthorized = vi.fn();
  setUnauthorizedHandler(unauthorized);
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "Invalid username or password" }),
  });

  await expect(
    login({
      username: "reward",
      password: "wrong-pass",
    })
  ).rejects.toThrow("Invalid username or password");

  expect(unauthorized).not.toHaveBeenCalled();
});
