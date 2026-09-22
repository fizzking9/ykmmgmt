import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { useAskChat, useChatMessages, useChatSuggestions } from "@/hooks/useChat";
import { ChatPanel } from "./ChatPanel";
import { ChatToggleButton } from "./ChatToggleButton";
import type { UiMessage } from "./MessageList";

const LS_SESSION = "ykmmgmt.chat.sessionId";
const LS_SEEN = "ykmmgmt.chat.seenHint";

function readLS(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Floating FAQ assistant. Mounted once in AppLayout so it is reachable from
 * every authenticated page. The active session id is kept in localStorage so
 * the transcript is restored across refreshes; the transcript itself is
 * hydrated from the server once per session, then maintained locally for
 * instant feedback.
 */
export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() => readLS(LS_SESSION));
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [showHint, setShowHint] = useState(() => !readLS(LS_SEEN));
  const [hydratedSession, setHydratedSession] = useState<string | null>(null);

  const ask = useAskChat();
  const { data: history, isLoading: historyLoading } = useChatMessages(sessionId);
  const { data: suggestions = [] } = useChatSuggestions();

  useEffect(() => {
    try {
      if (sessionId) localStorage.setItem(LS_SESSION, sessionId);
      else localStorage.removeItem(LS_SESSION);
    } catch {
      /* ignore private-mode failures */
    }
  }, [sessionId]);

  // Hydrate the transcript once per session from server history.
  useEffect(() => {
    if (sessionId && history && hydratedSession !== sessionId) {
      setMessages(
        history.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        })),
      );
      setHydratedSession(sessionId);
    }
  }, [history, sessionId, hydratedSession]);

  const handleSend = useCallback(
    async (text: string) => {
      const uid = `tmp-${Date.now()}`;
      setMessages((prev) => [...prev, { id: uid, role: "user", content: text }]);
      setAsking(true);
      try {
        const resp = await ask.mutateAsync({ message: text, sessionId });
        if (!sessionId) {
          setSessionId(resp.session_id);
          setHydratedSession(resp.session_id); // keep local transcript, skip re-hydration
        }
        setMessages((prev) => [
          ...prev,
          { id: `ans-${Date.now()}`, role: "assistant", content: resp.answer },
        ]);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "提问失败");
        setMessages((prev) => prev.filter((m) => m.id !== uid));
      } finally {
        setAsking(false);
      }
    },
    [ask, sessionId],
  );

  function handleNewConversation() {
    setSessionId(null);
    setMessages([]);
    setHydratedSession(null);
    setAsking(false);
  }

  function toggle() {
    setOpen((prev) => {
      const next = !prev;
      if (next) {
        setShowHint(false);
        try {
          localStorage.setItem(LS_SEEN, "1");
        } catch {
          /* ignore */
        }
      }
      return next;
    });
  }

  const loadingHistory = !!sessionId && hydratedSession !== sessionId && historyLoading;

  return (
    <>
      <ChatPanel
        open={open}
        messages={messages}
        typing={asking}
        suggestions={suggestions}
        loadingHistory={loadingHistory}
        onSend={handleSend}
        onNewConversation={handleNewConversation}
        onClose={() => setOpen(false)}
      />
      <ChatToggleButton open={open} onClick={toggle} showHint={showHint} />
    </>
  );
}
