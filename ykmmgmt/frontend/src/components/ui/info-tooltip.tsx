import { CircleHelp } from "lucide-react";

import { cn } from "@/lib/utils";

interface InfoTooltipProps {
  /** Tooltip body — a string or rich content. */
  content: React.ReactNode;
  /** Aria label for the trigger icon (also the test hook). */
  ariaLabel: string;
  /** Which side of the icon the bubble opens on. */
  side?: "top" | "bottom";
  className?: string;
}

/** Lightweight hover/focus tooltip for informational caveats.
 *  Pure CSS visibility toggling (group hover / focus-within) — no portal,
 *  keyboard-accessible because the trigger icon is focusable. */
export function InfoTooltip({ content, ariaLabel, side = "bottom", className }: InfoTooltipProps) {
  const vertical = side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5";
  return (
    <span
      tabIndex={0}
      aria-label={ariaLabel}
      className={cn(
        "group relative inline-flex cursor-help items-center align-middle text-muted-foreground outline-none",
        className,
      )}
    >
      <CircleHelp className="h-3.5 w-3.5" />
      <span
        role="tooltip"
        className={cn(
          "invisible absolute left-0 z-50 w-64 rounded-md border bg-card p-3 text-xs font-normal leading-relaxed text-card-foreground opacity-0 shadow-md transition-opacity",
          "group-hover:visible group-hover:opacity-100 group-focus:visible group-focus:opacity-100",
          vertical,
        )}
      >
        {content}
      </span>
    </span>
  );
}
