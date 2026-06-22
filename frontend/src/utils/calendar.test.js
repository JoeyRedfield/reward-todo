import { expect, test } from "vitest";
import { buildCalendarDays, getMonthBounds, shiftMonth } from "./calendar";

test("builds a monday-first calendar grid for the visible month", () => {
  const days = buildCalendarDays("2026-06-21");

  expect(days).toHaveLength(35);
  expect(days[0]).toMatchObject({
    date: "2026-06-01",
    dayOfMonth: 1,
    isCurrentMonth: true,
  });
  expect(days.at(-1)).toMatchObject({
    date: "2026-07-05",
    dayOfMonth: 5,
    isCurrentMonth: false,
  });
});

test("returns month bounds for the visible month", () => {
  expect(getMonthBounds("2026-06-21")).toEqual({
    start: "2026-06-01",
    end: "2026-06-30",
  });
});

test("shifts visible month while preserving the local day when possible", () => {
  expect(shiftMonth("2026-06-21", -1)).toBe("2026-05-21");
  expect(shiftMonth("2026-06-21", 1)).toBe("2026-07-21");
});
