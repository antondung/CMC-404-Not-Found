import React from 'react';

/** Insert newlines before section labels / bullets when the model smashes them onto one line. */
export function normalizeAnswerMarkdown(content: string): string {
  let text = (content || '').replace(/\r\n/g, '\n').trim();

  // Protect "1. **Title:**" / "- **Title:**" so smash-fix does not orphan the marker.
  const protectedBlocks: string[] = [];
  const protect = (full: string) => {
    const key = `\uE000${protectedBlocks.length}\uE001`;
    protectedBlocks.push(full);
    return key;
  };
  text = text.replace(/\d+\.\s*\*\*[^*]{1,80}?:\*\*/g, (m) => protect(m));
  text = text.replace(/(?:^|\n)-\s*\*\*[^*]{1,80}?:\*\*/g, (m) => protect(m));

  // BE2 style: **Kết luận ngắn:**  (colon inside the bold markers)
  text = text.replace(/(?!^)(?=\*\*[^*]{1,80}?:\*\*)/g, '\n\n');
  // Alternate: **Kết luận ngắn**:  (colon after closing **)
  text = text.replace(/(?!^)(?=\*\*[^*]{1,80}\*\*\s*:)/g, '\n\n');
  // Smash-fix bullets: "...text. - [id] ..."
  text = text.replace(/\s+(-\s+)/g, '\n$1');

  protectedBlocks.forEach((block, i) => {
    text = text.replace(`\uE000${i}\uE001`, block);
  });

  return text.replace(/\n{3,}/g, '\n\n').trim();
}

/** Turn every **bold** span into <strong>; leaves surrounding text untouched. */
export function renderInlineMarkdown(text: string): React.ReactNode {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+?\*\*)/g);
  return parts.map((part, idx) => {
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-bold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

type AnswerMarkdownProps = {
  content: string;
  className?: string;
  /** Slightly denser styling for the admin console. */
  density?: 'comfortable' | 'compact';
};

type SectionParts = { title: string; rest: string; number?: string };

function matchSectionHeader(line: string): SectionParts | null {
  // "1. **Title:** rest"  or  "1. **Title**: rest"
  const numbered =
    line.match(/^(\d+)\.\s*\*\*([^*]+?):\*\*\s*(.*)$/) ||
    line.match(/^(\d+)\.\s*\*\*([^*]+?)\*\*\s*:\s*(.*)$/);
  if (numbered) {
    return {
      number: numbered[1],
      title: numbered[2].replace(/:$/, '').trim(),
      rest: (numbered[3] || '').trim(),
    };
  }
  // **Heading:** rest…  OR  **Heading**: rest…
  const plain =
    line.match(/^\*\*([^*]+?):\*\*\s*(.*)$/) ||
    line.match(/^\*\*([^*]+?)\*\*\s*:\s*(.*)$/);
  if (plain) {
    return {
      title: plain[1].replace(/:$/, '').trim(),
      rest: (plain[2] || '').trim(),
    };
  }
  return null;
}

/**
 * Renders LLM answers that use light Markdown (**bold**, - bullets, --- rules).
 * Used by both citizen Ask and admin QA so ** markers never show raw.
 */
export function AnswerMarkdown({ content, className, density = 'comfortable' }: AnswerMarkdownProps) {
  const normalized = normalizeAnswerMarkdown(content);
  const lines = normalized.split('\n').map((line) => line.trim()).filter(Boolean);

  const bodyClass =
    density === 'compact'
      ? 'text-sm leading-7 text-slate-700'
      : 'text-[15px] sm:text-[16px] leading-relaxed text-slate-700';
  const bulletTextClass =
    density === 'compact'
      ? 'text-sm leading-6 text-slate-700'
      : 'text-[15px] leading-relaxed text-slate-700';

  if (lines.length === 0) {
    return null;
  }

  const hasStructure = lines.some(
    (line) => line.startsWith('- ') || line.includes('**') || line === '---' || /^\d+\.\s/.test(line),
  );

  if (!hasStructure) {
    return (
      <p className={`${bodyClass} whitespace-pre-wrap ${className || ''}`.trim()}>
        {normalized}
      </p>
    );
  }

  return (
    <div className={`space-y-3 ${className || ''}`.trim()}>
      {lines.map((line, idx) => {
        if (line === '---') {
          return (
            <div
              key={idx}
              className="my-3 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent"
            />
          );
        }

        if (line.startsWith('- ')) {
          return (
            <div
              key={idx}
              className="flex gap-3 rounded-xl bg-slate-50/90 px-3.5 py-2.5 ring-1 ring-slate-100/90 transition-colors duration-200"
            >
              <div className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
              <p className={bulletTextClass}>{renderInlineMarkdown(line.slice(2))}</p>
            </div>
          );
        }

        const section = matchSectionHeader(line);
        if (section) {
          const { title, rest, number } = section;
          const label = number ? `${number}. ${title}` : title;
          // If the remainder still has another section header, render inline (normalize should have split).
          if (rest.includes('**:') || /\*\*[^*]+?:\*\*/.test(rest)) {
            return (
              <p key={idx} className={bodyClass}>
                {renderInlineMarkdown(line)}
              </p>
            );
          }
          return (
            <div key={idx} className="space-y-2">
              <div className="mt-1 flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-50 to-sky-50/80 px-3.5 py-2 text-blue-900 ring-1 ring-blue-100/80 first:mt-0">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" aria-hidden />
                <h3 className="text-sm font-bold tracking-wide">{label}</h3>
              </div>
              {rest ? <p className={bodyClass}>{renderInlineMarkdown(rest)}</p> : null}
            </div>
          );
        }

        // Orphan list marker left by older smash-fix — skip empty "1." / "2." lines
        if (/^\d+\.$/.test(line)) {
          return null;
        }

        return (
          <p key={idx} className={bodyClass}>
            {renderInlineMarkdown(line)}
          </p>
        );
      })}
    </div>
  );
}
