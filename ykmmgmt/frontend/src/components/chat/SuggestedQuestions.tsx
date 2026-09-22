import { MessageCircleQuestion } from "lucide-react";

/** Clickable question chips for the widget's empty state. */
export function SuggestedQuestions({
  questions,
  onSelect,
}: {
  questions: string[];
  onSelect: (q: string) => void;
}) {
  if (!questions.length) return null;

  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <MessageCircleQuestion className="h-3.5 w-3.5" />
        您可以试试以下问题：
      </p>
      <div className="flex flex-wrap gap-2">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onSelect(q)}
            className="touch-manipulation max-w-full truncate rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-left text-xs text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            title={q}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
