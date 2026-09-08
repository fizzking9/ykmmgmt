import { describe, it, expect } from "vitest";
import { wrapAngle, clamp, stepToward } from "@/lib/particles/dragRotation";

const PI = Math.PI;

describe("wrapAngle — shortest-arc normalisation", () => {
  it("leaves angles already in range untouched", () => {
    expect(wrapAngle(0)).toBeCloseTo(0);
    expect(wrapAngle(1.0)).toBeCloseTo(1.0);
    expect(wrapAngle(-1.0)).toBeCloseTo(-1.0);
  });

  it("wraps a full turn back to zero", () => {
    expect(wrapAngle(2 * PI)).toBeCloseTo(0);
    expect(wrapAngle(-2 * PI)).toBeCloseTo(0);
  });

  it("maps angles past the half-turn to their negative equivalent", () => {
    expect(wrapAngle(1.5 * PI)).toBeCloseTo(-0.5 * PI);
    expect(wrapAngle(-1.5 * PI)).toBeCloseTo(0.5 * PI);
  });

  it("takes the short way home for a multi-turn drag", () => {
    // 5 rad of accumulated yaw wraps to ~-1.283 rad (the short arc to 0).
    expect(wrapAngle(5.0)).toBeCloseTo(5.0 - 2 * PI);
  });
});

describe("clamp — pitch limits", () => {
  it("passes through values inside the range", () => {
    expect(clamp(0.5, -1.2, 1.2)).toBe(0.5);
  });

  it("pins values below and above the range", () => {
    expect(clamp(-5, -1.2, 1.2)).toBe(-1.2);
    expect(clamp(5, -1.2, 1.2)).toBe(1.2);
  });
});

describe("stepToward — exponential approach / spring home", () => {
  it("returns current when dt is zero", () => {
    expect(stepToward(3, 0, 0, 6)).toBe(3);
  });

  it("moves part-way toward the target in one step", () => {
    const next = stepToward(1, 0, 1 / 60, 6);
    expect(next).toBeLessThan(1);
    expect(next).toBeGreaterThan(0);
  });

  it("converges to the target over many steps (spring home)", () => {
    let v = 2.5;
    for (let i = 0; i < 240; i++) v = stepToward(v, 0, 1 / 60, 6);
    expect(v).toBeCloseTo(0, 3);
  });

  it("a higher rate tracks the target more tightly", () => {
    const slow = stepToward(0, 1, 1 / 60, 6);
    const fast = stepToward(0, 1, 1 / 60, 30);
    expect(fast).toBeGreaterThan(slow);
  });
});
