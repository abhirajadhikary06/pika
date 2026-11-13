import { describe, it, expect } from "vitest";
import { cn, statusLabel } from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("px-2", "py-1")).toContain("px-2");
  });
});

describe("statusLabel", () => {
  it("replaces underscores", () => {
    expect(statusLabel("in_progress")).toBe("in progress");
  });
});
