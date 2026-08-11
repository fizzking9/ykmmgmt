// ── Small info icon with a hover tooltip ─────────────────────────────────
// Used to keep secondary caveats out of the main layout (e.g. the global
// time-filter scope note on the dashboard page).

import { Info } from "lucide-react";

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <Info className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 hidden w-max max-w-xs -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow group-hover:block">
        {text}
      </span>
    </span>
  );
}
