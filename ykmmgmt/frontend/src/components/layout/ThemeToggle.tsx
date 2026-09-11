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
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  // The OS setting itself. resolvedTheme only mirrors it while "system" is the
  // active choice, so the media query is read directly to describe it at all times.
  const [osPrefersDark, setOsPrefersDark] = useState<boolean | null>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => setOsPrefersDark(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

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

  // Mirrors defaultTheme in main.tsx for the pre-resolution render.
  const current = (theme ?? "light") as Theme;
  const systemSetting = osPrefersDark === null ? null : osPrefersDark ? "深色" : "浅色";

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
        const isSystem = value === "system";
        return (
          <Button
            key={value}
            type="button"
            variant="ghost"
            size="sm"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={isSystem && systemSetting ? `跟随系统（当前系统为${systemSetting}）` : label}
            onClick={() => setTheme(value)}
            className={cn(
              "touch-manipulation flex-1 gap-1 rounded-[4px] px-1.5 text-xs",
              active
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
