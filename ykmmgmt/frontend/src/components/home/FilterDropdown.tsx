import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export interface FilterOption {
  value: string;
  label: string;
}

const PANEL_WIDTH = 176; // w-44

/**
 * Column-header filter: a caret trigger that opens an opaque checkbox-list
 * panel (selection applies live) with 筛选 / 重置 actions, mirroring the
 * reference board's header filters.
 *
 * The panel is portaled to <body> with fixed positioning so no scroll
 * container around the table (vertical list scroll or horizontal overflow)
 * can clip it — important when the table is short and the panel would
 * otherwise be cut off by the table's scroll boundary.
 */
export function FilterDropdown({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: FilterOption[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  function openPanel() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      setPos({
        top: rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - PANEL_WIDTH - 8)),
      });
    }
    setOpen(true);
  }

  // Close on outside click / Escape / resize; close on any scroll except the
  // panel's own list (fixed positioning would otherwise drift from trigger).
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t) || panelRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onScroll = (e: Event) => {
      if (panelRef.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    const onResize = () => setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  const active = selected.length > 0;

  function toggle(value: string) {
    onChange(
      selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value],
    );
  }

  return (
    <div ref={triggerRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openPanel())}
        aria-expanded={open}
        className={cn(
          "flex items-center gap-1 font-medium whitespace-nowrap",
          active ? "text-primary" : "text-foreground",
        )}
      >
        {label}
        <ChevronDown
          className={cn("h-3.5 w-3.5", active ? "text-primary" : "text-muted-foreground")}
        />
      </button>
      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            style={{ top: pos.top, left: pos.left, width: PANEL_WIDTH }}
            className="fixed z-50 rounded-md border bg-background p-2 shadow-md"
          >
            <div className="max-h-48 space-y-1 overflow-auto">
              {options.length === 0 && (
                <div className="p-2 text-xs text-muted-foreground">无可选值</div>
              )}
              {options.map((o) => (
                <label
                  key={o.value}
                  title={o.label}
                  className="flex cursor-pointer items-center gap-2 overflow-x-auto text-sm whitespace-nowrap"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(o.value)}
                    onChange={() => toggle(o.value)}
                    className="size-3.5 shrink-0 accent-primary"
                  />
                  <span>{o.label}</span>
                </label>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-3 border-t pt-2 text-xs">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-primary hover:underline"
              >
                筛选
              </button>
              <button
                type="button"
                onClick={() => onChange([])}
                className="text-muted-foreground hover:underline"
              >
                重置
              </button>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
