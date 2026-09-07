import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark" | "system";

const options: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "浅色", Icon: Sun },
  { value: "dark", label: "深色", Icon: Moon },
  { value: "system", label: "跟随系统", Icon: Monitor },
];

/**
 * Segmented theme toggle — light / dark / system.
 * Sits in the sidebar footer; the choice persists to localStorage via next-themes.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Avoid hydration mismatch: render a placeholder until mounted.
  if (!mounted) {
    return (
      <div
        className={cn(
          "flex h-8 w-full items-center justify-between rounded-md border border-border bg-muted/40 p-0.5",
          className,
        )}
        aria-hidden="true"
      />
    );
  }

  const current = (theme ?? "system") as Theme;

  return (
    <div
      role="radiogroup"
      aria-label="主题"
      className={cn(
        "flex h-8 w-full items-center justify-between gap-0.5 rounded-md border border-border bg-muted/40 p-0.5",
        className,
      )}
    >
      {options.map(({ value, label, Icon }) => {
        const active = current === value;
        // Show the resolved theme icon when "system" is selected.
        const showActive = active || (value === "system" && current === "system" && resolvedTheme);
        return (
          <Button
            key={value}
            type="button"
            variant="ghost"
            size="sm"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "touch-manipulation flex-1 gap-1 rounded-[4px] px-1.5 text-xs",
              showActive
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{label}</span>
          </Button>
        );
      })}
    </div>
  );
}
