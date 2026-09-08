/**
 * sampleGlyphs — turns the "YKM" wordmark + the 云客猫 cat-head mark into
 * particle home-positions for the welcome splash.
 *
 * The point-selection maths (ink threshold, stride sampling, canvas→world
 * mapping, fit-scaling, buffer packing) lives in small PURE functions that
 * operate on raw pixel data / plain numbers, so they can be unit-tested with
 * synthetic input and no real canvas. `sampleGlyphs()` is the only impure
 * entry point: it rasterises the glyphs to an offscreen 2D canvas, then feeds
 * the pixels through the exact same pure pipeline.
 */

/** A single 2D point (canvas pixel or world coordinate). */
export interface SamplePoint {
  x: number;
  y: number;
}

export interface InkSampleOptions {
  /** Sampling step in pixels (>= 1). Larger = sparser particles. */
  stride?: number;
  /** Alpha value (0-255) at or above which a pixel counts as "ink". */
  threshold?: number;
}

export interface SampleGlyphsOptions extends InkSampleOptions {
  /** Width of the offscreen raster canvas, in pixels. */
  canvasWidth?: number;
  /** Height of the offscreen raster canvas, in pixels. */
  canvasHeight?: number;
  /** World-space width the glyph ink is fit into (aspect preserved). */
  targetWidth?: number;
  /** World-space height the glyph ink is fit into (aspect preserved). */
  targetHeight?: number;
}

/**
 * Pure: scan RGBA pixel data on a stride grid and collect every pixel whose
 * alpha is at or above `threshold`. Operates on the raw byte array (no canvas)
 * so it is trivially testable with synthetic pixel data.
 *
 * `data` is a flat RGBA buffer of length `width * height * 4`; the alpha of
 * pixel (x, y) lives at `(y * width + x) * 4 + 3`.
 */
export function collectInkPixels(
  data: ArrayLike<number>,
  width: number,
  height: number,
  options: InkSampleOptions = {},
): SamplePoint[] {
  const stride = Math.max(1, Math.floor(options.stride ?? 3));
  const threshold = options.threshold ?? 128;
  const points: SamplePoint[] = [];
  for (let y = 0; y < height; y += stride) {
    for (let x = 0; x < width; x += stride) {
      const alpha = data[(y * width + x) * 4 + 3];
      if (alpha >= threshold) points.push({ x, y });
    }
  }
  return points;
}

/**
 * Pure: map a pixel coordinate within a `width × height` box to a centred
 * world coordinate scaled by `scale`. The box centre maps to the origin, and
 * the vertical axis is flipped (canvas y grows down, world y grows up).
 */
export function canvasToWorld(
  x: number,
  y: number,
  width: number,
  height: number,
  scale: number,
): SamplePoint {
  return {
    x: (x - width / 2) * scale,
    y: (height / 2 - y) * scale,
  };
}

/**
 * Pure: uniform scale that fits a `contentW × contentH` box inside a
 * `targetW × targetH` box while preserving aspect ratio ("contain", never
 * "cover"). Returns 1 for degenerate (non-positive) inputs.
 */
export function fitScale(
  contentW: number,
  contentH: number,
  targetW: number,
  targetH: number,
): number {
  if (contentW <= 0 || contentH <= 0 || targetW <= 0 || targetH <= 0) return 1;
  return Math.min(targetW / contentW, targetH / contentH);
}

/**
 * Pure: pack 2D points into an xyz position buffer (z = 0), laid out for a
 * THREE.BufferAttribute (three consecutive floats per point).
 */
export function toPositionBuffer(points: SamplePoint[]): Float32Array {
  const out = new Float32Array(points.length * 3);
  for (let i = 0; i < points.length; i++) {
    out[i * 3] = points[i].x;
    out[i * 3 + 1] = points[i].y;
    out[i * 3 + 2] = 0;
  }
  return out;
}

/**
 * Pure: build a cat-head silhouette path — a rounded skull, two pointed ears,
 * and two eye cut-outs left as negative space (drawn with `evenodd` so the
 * eyes subtract from the filled head). Built in a local space centred on
 * (0, 0) with a nominal radius of 1; callers scale/translate it into place.
 */
export function buildCatPath(): Path2D {
  const path = new Path2D();

  // Rounded skull — slightly wider than tall for a feline face.
  path.moveTo(-0.72, -0.1);
  path.bezierCurveTo(-0.78, 0.55, -0.42, 0.86, 0, 0.86);
  path.bezierCurveTo(0.42, 0.86, 0.78, 0.55, 0.72, -0.1);
  path.bezierCurveTo(0.7, -0.42, 0.5, -0.6, 0.34, -0.66);
  // Right ear (outer edge up to the tip, back down to the crown).
  path.lineTo(0.78, -1.06);
  path.lineTo(0.2, -0.74);
  // Crown dip between the ears.
  path.lineTo(-0.2, -0.74);
  // Left ear.
  path.lineTo(-0.78, -1.06);
  path.lineTo(-0.34, -0.66);
  path.bezierCurveTo(-0.5, -0.6, -0.7, -0.42, -0.72, -0.1);
  path.closePath();

  // Eyes — almond cut-outs, added as subpaths so `evenodd` punches them out.
  addEye(path, -0.33, 0.02, 0.17, 0.12);
  addEye(path, 0.33, 0.02, 0.17, 0.12);

  return path;
}

function addEye(path: Path2D, cx: number, cy: number, rx: number, ry: number): void {
  path.moveTo(cx - rx, cy);
  path.bezierCurveTo(cx - rx, cy - ry, cx + rx, cy - ry, cx + rx, cy);
  path.bezierCurveTo(cx + rx, cy + ry, cx - rx, cy + ry, cx - rx, cy);
  path.closePath();
}

/**
 * Impure: rasterise the cat-head mark and the "YKM" wordmark to an offscreen
 * 2D canvas, then sample the ink into a Float32Array of xyz home positions
 * centred on the origin and fit into the requested world box.
 *
 * Awaits `document.fonts.ready` so Geist is loaded before the text is drawn.
 */
export async function sampleGlyphs(options: SampleGlyphsOptions = {}): Promise<Float32Array> {
  const canvasWidth = options.canvasWidth ?? 1024;
  const canvasHeight = options.canvasHeight ?? 384;
  const targetWidth = options.targetWidth ?? 20;
  const targetHeight = options.targetHeight ?? 7;
  const stride = options.stride ?? 3;
  const threshold = options.threshold ?? 128;

  // Wait for webfonts so "YKM" is drawn in Geist, not a fallback metric.
  if (typeof document !== "undefined" && document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      // Font loading failures are non-fatal — fall back to the default face.
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = canvasWidth;
  canvas.height = canvasHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new Float32Array(0);

  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  ctx.fillStyle = "#ffffff";

  // --- Cat head (left of the wordmark) ---------------------------------
  const catScale = canvasHeight * 0.3;
  ctx.save();
  ctx.translate(canvasHeight * 0.52, canvasHeight * 0.54);
  ctx.scale(catScale, catScale);
  ctx.fill(buildCatPath(), "evenodd");
  ctx.restore();

  // --- "YKM" wordmark (right of the cat) --------------------------------
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.font = `700 ${Math.round(canvasHeight * 0.62)}px "Geist Variable", "Geist", sans-serif`;
  ctx.fillText("YKM", canvasHeight * 0.98, canvasHeight * 0.54);

  // --- Sample the ink through the shared pure pipeline ------------------
  const { data } = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
  const ink = collectInkPixels(data, canvasWidth, canvasHeight, { stride, threshold });
  if (ink.length === 0) return new Float32Array(0);

  // Ink bounding box — used to centre the composition and derive the fit.
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const p of ink) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const contentW = Math.max(1, maxX - minX);
  const contentH = Math.max(1, maxY - minY);
  const scale = fitScale(contentW, contentH, targetWidth, targetHeight);

  const world = ink.map((p) => canvasToWorld(p.x - minX, p.y - minY, contentW, contentH, scale));
  return toPositionBuffer(world);
}
