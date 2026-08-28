// ── Shared PNG export helpers ───────────────────────────────────────────────
// html2canvas capture + download utilities shared by the visualization &
// dashboard list-page exports.

import html2canvas from "html2canvas";

/** Capture a DOM element as a PNG blob (white background, 2× resolution). */
export async function elementToPngBlob(el: HTMLElement): Promise<Blob> {
  const canvas = await html2canvas(el, {
    backgroundColor: "#ffffff",
    scale: 2,
  });
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("PNG 生成失败"))),
      "image/png",
    );
  });
}

/** Trigger a browser download for a blob. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.download = filename;
  link.href = url;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

/** Strip characters Windows forbids in file names. */
export function sanitizeFilename(name: string): string {
  const cleaned = name.replace(/[\\/:*?"<>|]/g, "_").trim();
  return cleaned || "未命名";
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/**
 * Batch identifier for exported filenames: "{prefix}_YYYY-MM-DD_HH-mm-ss".
 * Batch exports go straight to the browser's default download location (no
 * save-as dialog); embedding this identifier in every filename keeps the
 * batch grouped and sortable, since a web page cannot create a real
 * subfolder there without an explicit directory picker.
 */
export function batchStamp(prefix: string): string {
  const now = new Date();
  const stamp =
    `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
    `_${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
  return `${prefix}_${stamp}`;
}
