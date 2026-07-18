import { WarningCircle, ShieldCheck } from '@phosphor-icons/react';

type HonestyBannerProps = {
  unverified?: boolean;
  degraded?: boolean;
  confidence?: 'high' | 'medium' | 'low';
  citationCount?: number;
  className?: string;
};

/**
 * Surfaces backend honesty signals that were previously dropped by the UI.
 */
export function HonestyBanner({
  unverified,
  degraded,
  confidence,
  citationCount = 0,
  className = '',
}: HonestyBannerProps) {
  const showUnverified = Boolean(unverified) || (citationCount === 0 && confidence === 'low');
  if (!showUnverified && confidence !== 'low' && !degraded) {
    return null;
  }

  if (showUnverified) {
    return (
      <div
        className={`mt-3 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-amber-950 ${className}`.trim()}
        role="status"
      >
        <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0 text-amber-600" aria-hidden />
        <p className="text-xs font-semibold leading-relaxed sm:text-sm">
          Chưa gắn căn cứ Điều/Khoản đã số hóa — câu trả lời mang tính định hướng theo nguyên tắc chung.
          Hãy đối chiếu văn bản gốc hoặc hỏi lại với số hiệu cụ thể.
        </p>
      </div>
    );
  }

  if (degraded) {
    return (
      <div
        className={`mt-3 flex gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5 text-sky-950 ${className}`.trim()}
        role="status"
      >
        <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0 text-sky-600" aria-hidden />
        <p className="text-xs font-semibold leading-relaxed sm:text-sm">
          Chế độ dự phòng: câu trả lời có thể thiếu một phần kiểm chứng tự động.
        </p>
      </div>
    );
  }

  if (confidence === 'low') {
    return (
      <div
        className={`mt-3 inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-slate-600 ${className}`.trim()}
      >
        <ShieldCheck size={14} weight="bold" aria-hidden /> Độ tin cậy: thấp
      </div>
    );
  }

  return null;
}
