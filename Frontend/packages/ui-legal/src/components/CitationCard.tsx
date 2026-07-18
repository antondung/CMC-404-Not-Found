import React from 'react';
import { Scales, ArrowSquareOut } from '@phosphor-icons/react';

interface CitationCardProps {
  khoan_id?: string;
  van_ban: string;
  dieu: string;
  quote?: string;
  url?: string;
}

function documentKind(text: string): string {
  const normalized = text.toLowerCase();
  if (normalized.includes('nghị định') || normalized.includes('/nd-cp') || normalized.includes('/nđ-cp')) return 'Nghị định';
  if (normalized.includes('luật') || normalized.includes('/qh')) return 'Luật';
  if (normalized.includes('thông tư') || normalized.includes('/tt-')) return 'Thông tư';
  if (normalized.includes('quyết định') || normalized.includes('/qd-') || normalized.includes('/qđ-')) return 'Quyết định';
  return 'Văn bản';
}

function extractDocumentNumber(khoanId: string | undefined, vanBan: string): string {
  const fromId = khoanId?.split('::')[0]?.trim();
  if (fromId) return fromId;

  const match = vanBan.match(/\b\d+\s*\/\s*\d{4}\s*\/\s*[A-ZĐĐa-zđ\-]+\b/u);
  return match?.[0]?.replace(/\s+/g, '') ?? vanBan;
}

function extractArticle(khoanId: string | undefined, dieu: string): string {
  const fromId = khoanId?.match(/::D(\d+)/i)?.[1];
  if (fromId) return `Điều ${fromId}`;
  const fromText = dieu.match(/Điều\s*\d+/i)?.[0];
  return fromText ?? (dieu || 'Chưa rõ điều');
}

function extractClause(khoanId: string | undefined, quote: string | undefined): string {
  const fromId = khoanId?.match(/\.K(\d+)/i)?.[1];
  if (fromId) return `Khoản ${fromId}`;
  const fromQuote = quote?.match(/(?:^|\s)(\d+)\s*[.)]\s+/)?.[1];
  return fromQuote ? `Khoản ${fromQuote}` : '—';
}

/** Compact legal ref card: số hiệu · Điều · Khoản only (no long quote body). */
export const CitationCard: React.FC<CitationCardProps> = ({ khoan_id, van_ban, dieu, quote, url }) => {
  const kind = documentKind(`${van_ban} ${khoan_id ?? ''}`);
  const documentNumber = extractDocumentNumber(khoan_id, van_ban);
  const article = extractArticle(khoan_id, dieu);
  const clause = extractClause(khoan_id, quote);
  const showQuote = Boolean(quote?.trim());

  return (
    <div className="group relative flex flex-col justify-center overflow-hidden rounded-[12px] border border-slate-200/70 bg-white/80 p-2 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-300 hover:bg-white hover:shadow-md">
      <div className="absolute bottom-0 left-0 top-0 w-1 bg-gradient-to-b from-emerald-500 via-cyan-500 to-blue-500 opacity-80 transition-all duration-300 group-hover:w-1.5 group-hover:opacity-100" />

      <div className="flex items-center gap-2.5 pl-3 pr-1">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100 transition-transform duration-300 group-hover:scale-110 group-hover:bg-emerald-500 group-hover:text-white group-hover:ring-emerald-500">
          <Scales size={16} weight="fill" />
        </div>

        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="shrink-0 rounded-[4px] bg-slate-800 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white shadow-sm">
            {kind}
          </span>
          <span className="truncate text-sm font-bold text-slate-800 transition-colors duration-300 group-hover:text-emerald-700">
            {documentNumber}
          </span>
          <span className="text-slate-300" aria-hidden>•</span>
          <span className="shrink-0 text-[13px] font-semibold text-slate-600">
            {article}
          </span>
          {clause !== '—' && (
            <>
              <span className="text-slate-300" aria-hidden>•</span>
              <span className="shrink-0 text-[13px] font-semibold text-slate-600">
                {clause}
              </span>
            </>
          )}
          {showQuote && (
            <>
              <span className="hidden text-slate-300 sm:inline" aria-hidden>—</span>
              <span className="truncate text-[13px] text-slate-400 sm:flex-1" title={quote}>
                {quote}
              </span>
            </>
          )}
        </div>

        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400 transition-all duration-300 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-600"
            title="Mở chi tiết văn bản"
          >
            <ArrowSquareOut size={16} weight="bold" />
          </a>
        ) : null}
      </div>
    </div>
  );
};
