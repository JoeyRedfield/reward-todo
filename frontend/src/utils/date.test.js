import { expect, test } from "vitest";
import { formatLocalDate } from "./date";

test("formats date using local calendar fields instead of UTC iso string", () => {
  const date = new Date("2026-06-20T16:30:00.000Z");

  expect(formatLocalDate(date)).toBe("2026-06-21");
});
