/**
 * dragRotation — pure, Three-free rotation math for the splash's
 * drag-to-rotate interaction.
 *
 * Kept separate from `pointsField.ts` (which owns the WebGL scene) so the
 * clamp / wrap / easing behaviour can be unit-tested without a WebGL context.
 */

/** Wrap an angle in radians into the interval [-PI, PI]. */
export function wrapAngle(angle: number): number {
  const twoPi = Math.PI * 2;
  let a = angle % twoPi;
  if (a > Math.PI) a -= twoPi;
  if (a < -Math.PI) a += twoPi;
  return a;
}

/** Clamp `value` into the inclusive range [min, max]. */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Frame-rate-independent exponential approach: move `current` toward `target`
 * over `dt` seconds at `rate` (per second). Used both to follow the drag
 * target while the pointer is down and, after release, to spring home toward
 * zero. A higher `rate` tracks more tightly; `dt = 0` returns `current`.
 */
export function stepToward(current: number, target: number, dt: number, rate: number): number {
  return target + (current - target) * Math.exp(-rate * dt);
}
