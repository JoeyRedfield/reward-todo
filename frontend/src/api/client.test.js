import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  changePassword,
  fetchDailyTaskCalendar,
  fetchRewardSummary,
  fetchCurrentUser,
  login,
  reopenDailyTask,
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

test("reopens a completed task with POST request", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ id: 1, status: "pending" }),
  });

  await reopenDailyTask(1);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/daily-tasks/1/reopen",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
    })
  );
});

test("fetches reward summary for a selected date", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ current_balance: 0, today_earned: 0 }),
  });

  await fetchRewardSummary("2026-06-20");

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/rewards/summary?date=2026-06-20",
    expect.objectContaining({
      credentials: "include",
    })
  );
});

test("fetches daily task calendar summary for a date range", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });

  await fetchDailyTaskCalendar("2026-06-01", "2026-06-30");

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/daily-tasks/calendar?start=2026-06-01&end=2026-06-30",
    expect.objectContaining({
      credentials: "include",
    })
  );
});
