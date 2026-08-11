// ── Small info icon with a hover tooltip ─────────────────────────────────
// Keeps secondary caveats out of the main layout (e.g. the global
// time-filter scope note on the dashboard page).
//
// Rendered through a portal with `position: fixed` so that no ancestor's
// `overflow: hidden` (Cards clip) can clip the tooltip. Positioned below the
// icon and clamped to the viewport horizontally.

import { useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

export function InfoTip({ text }: { text: string }) {
  const iconRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const show = useCallback(() => {
    const node = iconRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    setPos({ top: rect.bottom + 6, left: rect.left + rect.width / 2 });
  }, []);

  const hide = useCallback(() => setPos(null), []);

  // Keep the (up to ~320px wide) box inside the viewport.
  const clampedLeft = pos ? Math.min(Math.max(pos.left, 170), window.innerWidth - 170) : 0;

  return (
    <>
      <span
        ref={iconRef}
        className="inline-flex align-middle"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        tabIndex={0}
      >
        <Info className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
      </span>
      {pos &&
        createPortal(
          <div
            className="pointer-events-none fixed z-[100] w-max max-w-xs -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow"
            style={{ top: pos.top, left: clampedLeft }}
          >
            {text}
          </div>,
          document.body,
        )}
    </>
  );
}
