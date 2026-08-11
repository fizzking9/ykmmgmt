// ── Minimal safe markdown renderer for dashboard text tiles ──────────────
// Supports a practical subset (#/##/### headings, **bold**, *italic*,
// `code`, "- " bullet lists, blank-line paragraphs). Builds React nodes
// directly — no innerHTML, so content cannot inject markup.

import type { ReactNode } from "react";

/** Parse inline formatting (**bold**, *italic*, `code`) into React nodes. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Split keeping the markers: **bold**, *italic*, `code`
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  parts.forEach((part, idx) => {
    if (!part) return;
    const key = `${keyPrefix}-${idx}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      nodes.push(
        <strong key={key} className="font-semibold">
          {part.slice(2, -2)}
        </strong>,
      );
    } else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      nodes.push(
        <em key={key} className="italic">
          {part.slice(1, -1)}
        </em>,
      );
    } else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      nodes.push(
        <code key={key} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(part);
    }
  });
  return nodes;
}

export function TextTileMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let listItems: ReactNode[] = [];
  let key = 0;

  const flushList = () => {
    if (listItems.length) {
      blocks.push(
        <ul key={`ul-${key++}`} className="my-1 list-disc space-y-0.5 pl-5">
          {listItems}
        </ul>,
      );
      listItems = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(
        <li key={`li-${key++}-${listItems.length}`}>
          {renderInline(trimmed.slice(2), `li-${key}`)}
        </li>,
      );
      continue;
    }
    flushList();

    if (!trimmed) continue;

    if (trimmed.startsWith("### ")) {
      blocks.push(
        <h3 key={`h3-${key++}`} className="mt-2 text-base font-semibold first:mt-0">
          {renderInline(trimmed.slice(4), `h3-${key}`)}
        </h3>,
      );
    } else if (trimmed.startsWith("## ")) {
      blocks.push(
        <h2 key={`h2-${key++}`} className="mt-2 text-lg font-semibold first:mt-0">
          {renderInline(trimmed.slice(3), `h2-${key}`)}
        </h2>,
      );
    } else if (trimmed.startsWith("# ")) {
      blocks.push(
        <h1 key={`h1-${key++}`} className="mt-2 text-xl font-bold first:mt-0">
          {renderInline(trimmed.slice(2), `h1-${key}`)}
        </h1>,
      );
    } else {
      blocks.push(
        <p key={`p-${key++}`} className="my-1 text-sm leading-relaxed first:mt-0">
          {renderInline(trimmed, `p-${key}`)}
        </p>,
      );
    }
  }
  flushList();

  if (!blocks.length) {
    return <p className="text-sm text-muted-foreground">（空文本）</p>;
  }

  return <div className="h-full overflow-auto p-3">{blocks}</div>;
}
