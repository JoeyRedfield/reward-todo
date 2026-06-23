import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import RewardsPage from "./Rewards";

const {
  fetchRewardLedgerMock,
  fetchRewardSummaryMock,
  spendRewardMock,
} = vi.hoisted(() => ({
  fetchRewardLedgerMock: vi.fn(),
  fetchRewardSummaryMock: vi.fn(),
  spendRewardMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchRewardLedger: fetchRewardLedgerMock,
  fetchRewardSummary: fetchRewardSummaryMock,
  spendReward: spendRewardMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();
  fetchRewardLedgerMock.mockResolvedValue([
    {
      id: 1,
      entry_type: "earn",
      amount: 2000,
      reason: "跑步 30 分钟",
      daily_task_id: 1,
      created_at: "2026-06-21T10:00:00Z",
    },
  ]);
  fetchRewardSummaryMock.mockResolvedValue({
    current_balance: 2000,
    today_earned: 2000,
  });
  spendRewardMock.mockResolvedValue({
    id: 2,
    entry_type: "spend",
    amount: -500,
    reason: "咖啡",
    daily_task_id: null,
    created_at: "2026-06-21T11:00:00Z",
  });
});

test("renders reward ledger", async () => {
  render(<RewardsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
});

test("submits reward spend form", async () => {
  render(<RewardsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("例如：5.00"), {
    target: { value: "4.50" },
  });
  fireEvent.change(screen.getByPlaceholderText("例如：咖啡"), {
    target: { value: "咖啡" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认扣减" }));

  await waitFor(() => {
    expect(spendRewardMock).toHaveBeenCalledWith(450, "咖啡");
  });
});
