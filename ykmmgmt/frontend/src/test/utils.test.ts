import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn — className utility", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "active")).toBe("base active");
  });

  it("resolves tailwind conflicts via twMerge", () => {
    expect(cn("px-4 py-2", "px-6")).toBe("py-2 px-6");
  });

  it("returns empty string for no inputs", () => {
    expect(cn()).toBe("");
  });
});
