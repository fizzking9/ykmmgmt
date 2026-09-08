import { describe, it, expect } from "vitest";
import {
  collectInkPixels,
  canvasToWorld,
  fitScale,
  toPositionBuffer,
} from "@/lib/particles/sampleGlyphs";

/**
 * Build a synthetic RGBA buffer (length w*h*4) from an alpha function so the
 * point-selection logic can be tested without a real canvas.
 */
function makeImage(
  width: number,
  height: number,
  alphaAt: (x: number, y: number) => number,
): Uint8ClampedArray {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      data[i] = 255;
      data[i + 1] = 255;
      data[i + 2] = 255;
      data[i + 3] = alphaAt(x, y);
    }
  }
  return data;
}

describe("collectInkPixels — ink threshold", () => {
  // 2x1 image: left pixel alpha 100 (faint), right pixel alpha 200 (solid).
  const data = makeImage(2, 1, (x) => (x === 0 ? 100 : 200));

  it("keeps pixels at or above the threshold and drops those below", () => {
    const points = collectInkPixels(data, 2, 1, { stride: 1, threshold: 128 });
    expect(points).toEqual([{ x: 1, y: 0 }]);
  });

  it("collects both pixels when the threshold is lowered below both alphas", () => {
    const points = collectInkPixels(data, 2, 1, { stride: 1, threshold: 50 });
    expect(points).toEqual([
      { x: 0, y: 0 },
      { x: 1, y: 0 },
    ]);
  });

  it("treats the threshold as inclusive (alpha === threshold counts as ink)", () => {
    const points = collectInkPixels(data, 2, 1, { stride: 1, threshold: 200 });
    expect(points).toEqual([{ x: 1, y: 0 }]);
  });
});

describe("collectInkPixels — stride sampling", () => {
  // Fully-inked 4x4 image.
  const data = makeImage(4, 4, () => 255);

  it("collects every pixel at stride 1", () => {
    expect(collectInkPixels(data, 4, 4, { stride: 1 })).toHaveLength(16);
  });

  it("samples a coarser grid at stride 2", () => {
    const points = collectInkPixels(data, 4, 4, { stride: 2 });
    expect(points).toEqual([
      { x: 0, y: 0 },
      { x: 2, y: 0 },
      { x: 0, y: 2 },
      { x: 2, y: 2 },
    ]);
  });

  it("clamps a non-positive stride to 1 (never skips everything)", () => {
    expect(collectInkPixels(data, 4, 4, { stride: 0 })).toHaveLength(16);
  });
});

describe("canvasToWorld — coordinate mapping", () => {
  const width = 100;
  const height = 50;
  const scale = 2;

  it("maps the box centre to the world origin", () => {
    expect(canvasToWorld(50, 25, width, height, scale)).toEqual({ x: 0, y: 0 });
  });

  it("recentres and scales the top-left corner", () => {
    expect(canvasToWorld(0, 0, width, height, scale)).toEqual({ x: -100, y: 50 });
  });

  it("flips the vertical axis (canvas y grows down, world y grows up)", () => {
    expect(canvasToWorld(100, 50, width, height, scale)).toEqual({ x: 100, y: -50 });
  });
});

describe("fitScale — contain scaling", () => {
  it("uses the limiting axis so content fits inside the target", () => {
    // Width ratio 2, height ratio 4 → the tighter (width) ratio wins.
    expect(fitScale(100, 50, 200, 200)).toBe(2);
  });

  it("scales down when the content exceeds the target", () => {
    expect(fitScale(100, 50, 50, 50)).toBe(0.5);
  });

  it("returns 1 for degenerate (non-positive) inputs", () => {
    expect(fitScale(0, 50, 100, 100)).toBe(1);
    expect(fitScale(100, 0, 100, 100)).toBe(1);
    expect(fitScale(100, 50, 0, 100)).toBe(1);
  });
});

describe("toPositionBuffer — xyz packing", () => {
  it("packs 2D points into triples with z = 0", () => {
    const buffer = toPositionBuffer([
      { x: 1, y: 2 },
      { x: 3, y: 4 },
    ]);
    expect(buffer).toBeInstanceOf(Float32Array);
    expect(buffer.length).toBe(6);
    expect(Array.from(buffer)).toEqual([1, 2, 0, 3, 4, 0]);
  });

  it("returns an empty buffer for no points", () => {
    expect(toPositionBuffer([]).length).toBe(0);
  });
});
