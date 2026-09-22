import { Loader2, MessagesSquare, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MessageInput } from "./MessageInput";
import { MessageList, type UiMessage } from "./MessageList";
import { SuggestedQuestions } from "./SuggestedQuestions";

/** Right-edge slide-in panel: header, transcript / empty state, composer. */
export function ChatPanel({
  open,
  messages,
  typing,
  suggestions,
  loadingHistory,
  onSend,
  onNewConversation,
  onClose,
}: {
  open: boolean;
  messages: UiMessage[];
  typing: boolean;
  suggestions: string[];
  loadingHistory: boolean;
  onSend: (text: string) => void;
  onNewConversation: () => void;
  onClose: () => void;
}) {
  const isEmpty = !loadingHistory && messages.length === 0;

  return (
    <>
      {/* Mobile backdrop — fades in, tap to dismiss */}
      <div
        onClick={onClose}
        aria-hidden="true"
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 sm:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <aside
        role="dialog"
        aria-label="智能问答"
        aria-hidden={!open}
        className={cn(
          "fixed right-0 top-0 z-50 flex h-dvh w-full flex-col border-l bg-card shadow-2xl transition-transform duration-300 ease-out sm:w-[380px]",
          open ? "translate-x-0" : "pointer-events-none translate-x-full",
        )}
      >
        <header className="flex items-center gap-2 border-b bg-background px-4 py-3">
          <Sparkles className="h-4 w-4 shrink-0 text-primary" />
          <h2 className="flex-1 text-sm font-semibold">智能问答助手</h2>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onNewConversation}
            aria-label="新建会话"
            title="新建会话"
          >
            <MessagesSquare className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="关闭" title="关闭">
            <X className="h-4 w-4" />
          </Button>
        </header>

        {loadingHistory ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : isEmpty ? (
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            <div className="space-y-1 text-sm text-muted-foreground">
              <p>您好！我是智能问答助手。</p>
              <p>请输入您的问题，我会从知识库为您匹配答案。</p>
            </div>
            <SuggestedQuestions questions={suggestions} onSelect={onSend} />
          </div>
        ) : (
          <MessageList messages={messages} typing={typing} />
        )}

        <MessageInput onSend={onSend} disabled={typing} />
      </aside>
    </>
  );
}
