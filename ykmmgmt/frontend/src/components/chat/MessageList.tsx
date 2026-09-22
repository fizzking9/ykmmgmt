import { useEffect, useRef } from "react";
import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownAnswer } from "./MarkdownAnswer";

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

function formatTime(iso?: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d.toLocaleString("zh-CN", { hour12: false });
}

/** Scrollable transcript. Assistant messages render as Markdown. */
export function MessageList({
  messages,
  typing,
}: {
  messages: UiMessage[];
  typing: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = bottomRef.current;
    // jsdom lacks scrollIntoView; guard so tests and non-browser envs don't throw
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ block: "end" });
    }
  }, [messages.length, typing]);

  return (
    <div className="flex-1 space-y-3 overflow-y-auto p-3">
      {messages.map((m) => {
        const isUser = m.role === "user";
        const time = formatTime(m.created_at);
        return (
          <div key={m.id} className={cn("flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3 py-2 text-sm shadow-sm",
                isUser
                  ? "rounded-br-sm bg-primary text-primary-foreground"
                  : "rounded-bl-sm border bg-muted",
              )}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap break-words">{m.content}</p>
              ) : (
                <MarkdownAnswer content={m.content} />
              )}
            </div>
            {!isUser && (
              <span className="flex items-center gap-1 pl-1 text-[10px] text-muted-foreground">
                <Bot className="h-3 w-3" />
                智能助手
                {time && <span className="ml-1 tabular-nums">· {time}</span>}
              </span>
            )}
            {isUser && time && (
              <span className="pr-1 text-[10px] tabular-nums text-muted-foreground">{time}</span>
            )}
          </div>
        );
      })}

      {typing && (
        <div className="flex items-start">
          <div className="flex gap-1 rounded-2xl rounded-bl-sm border bg-muted px-3 py-2.5">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
