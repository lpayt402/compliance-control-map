import { describe, expect, it } from "vitest";

import { formatDateOnly } from "./format";

describe("formatDateOnly", () => {
  it("renders an ISO calendar date without applying a local timezone shift", () => {
    expect(formatDateOnly("2026-08-24", "en-US")).toBe("Aug 24, 2026");
  });

  it("returns a stable fallback for missing or invalid dates", () => {
    expect(formatDateOnly(null, "en-US")).toBe("—");
    expect(formatDateOnly("not-a-date", "en-US")).toBe("not-a-date");
  });
});
