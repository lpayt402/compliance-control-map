import { describe, expect, it } from "vitest";

import { formatActionCode } from "./format";

describe("formatActionCode", () => {
  it("uses readable labels for known and future action codes", () => {
    expect(formatActionCode("ASSESSMENT_UPDATED")).toBe("Assessment updated");
    expect(formatActionCode("SOMETHING_NEW_HAPPENED")).toBe("Something new happened");
  });
});
