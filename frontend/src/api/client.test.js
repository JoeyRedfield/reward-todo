import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  changePassword,
  fetchCurrentUser,
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

test("triggers unauthorized handler only for authentication-required responses", async () => {
  const unauthorized = vi.fn();
  setUnauthorizedHandler(unauthorized);
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "Authentication required" }),
  });

  await expect(fetchCurrentUser()).rejects.toThrow("Authentication required");

  expect(unauthorized).toHaveBeenCalledTimes(1);
});

test("does not trigger unauthorized handler for wrong current password", async () => {
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
