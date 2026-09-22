import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

/** Chat composer — Enter sends, Shift+Enter inserts a newline. */
export function MessageInput({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex items-end gap-2 border-t bg-background p-3"
    >
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="请输入您的问题…"
        aria-label="消息输入框"
        disabled={disabled}
        className="max-h-32 min-h-[40px] flex-1 resize-none"
      />
      <Button type="submit" size="icon" disabled={disabled || !value.trim()} aria-label="发送">
        <Send className="h-4 w-4" />
      </Button>
    </form>
  );
}
