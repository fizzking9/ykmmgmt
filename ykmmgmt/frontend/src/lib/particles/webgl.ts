/**
 * webgl — a tiny, dependency-free WebGL capability probe.
 *
 * Kept separate from `pointsField.ts` so the welcome page can decide whether
 * to mount the Three.js canvas (or a static fallback) without pulling the
 * Three.js module graph into that decision.
 */

/** True when the browser can create a WebGL rendering context. */
export function isWebGLAvailable(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");
    return !!gl;
  } catch {
    return false;
  }
}
