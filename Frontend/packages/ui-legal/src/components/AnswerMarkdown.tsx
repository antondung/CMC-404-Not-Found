import React from 'react';
import { ListChecks } from '@phosphor-icons/react';

/** Insert newlines before section labels / bullets when the model smashes them onto one line. */
export function normalizeAnswerMarkdown(content: string): string {
  let text = (content || '').replace(/\r\n/g, '\n').trim();
  text = text.replace(/\s*(\*\*[^*]+?\*\*:)/g, '\n\n$1');
  text = text.replace(/\s+(-\s+(?:\[[^\]]+\]|[A-Za-zÀ-ỹ]))/g, '\n$1');
  return text.replace(/^\n+/, '').trim();
}

export function renderInlineMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
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

/**
 * Renders LLM answers that use light Markdown (**bold**, - bullets, --- rules).
 * Does not pull in a full Markdown library — only the patterns BE2 actually emits.
 */
export function AnswerMarkdown({ content, className, density = 'comfortable' }: AnswerMarkdownProps) {
  const normalized = normalizeAnswerMarkdown(content);
  const lines = normalized.split('\n').map((line) => line.trim()).filter(Boolean);
  const hasStructure = lines.some(
    (line) => line.startsWith('- ') || line.includes('**') || line === '---',
  );

  const bodyClass = density === 'compact' ? 'text-sm leading-7 text-slate-700' : 'text-[15px] sm:text-[16px] leading-relaxed text-slate-700';
  const bulletTextClass = density === 'compact' ? 'text-sm leading-6 text-slate-700' : 'text-[15px] leading-relaxed text-slate-700';

  if (!hasStructure) {
    return <p className={`${bodyClass} whitespace-pre-wrap ${className || ''}`.trim()}>{normalized}</p>;
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
              className="flex gap-3 rounded-2xl bg-slate-50/80 px-4 py-2.5 ring-1 ring-slate-100"
            >
              <div className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
              <p className={bulletTextClass}>{renderInlineMarkdown(line.slice(2))}</p>
            </div>
          );
        }

        // **Heading:** optional body on the same line
        const headingMatch = line.match(/^\*\*([^*]+?)\*\*:?\s*(.*)$/);
        if (headingMatch && !headingMatch[2].includes('**')) {
          const title = headingMatch[1].replace(/:$/, '').trim();
          const rest = headingMatch[2].trim();
          return (
            <div key={idx} className="space-y-2">
              <div className="mt-1 flex items-center gap-2 rounded-2xl bg-blue-50 px-4 py-2.5 text-blue-900 ring-1 ring-blue-100 first:mt-0">
                <ListChecks size={17} weight="fill" className="shrink-0 text-blue-600" />
                <h3 className="text-sm font-black uppercase tracking-wide">{title}</h3>
              </div>
              {rest ? <p className={bodyClass}>{renderInlineMarkdown(rest)}</p> : null}
            </div>
          );
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
