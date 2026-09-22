import { MessageCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** Fixed bottom-right launcher; shows a hint dot until first opened. */
export function ChatToggleButton({
  open,
  onClick,
  showHint,
}: {
  open: boolean;
  onClick: () => void;
  showHint: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={open ? "关闭智能问答" : "打开智能问答"}
      aria-expanded={open}
      className={cn(
        "touch-manipulation fixed bottom-5 right-5 z-40 inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      )}
    >
      {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      {!open && showHint && (
        <span className="absolute right-1 top-1 h-3 w-3 rounded-full border-2 border-background bg-red-500" />
      )}
    </button>
  );
}
