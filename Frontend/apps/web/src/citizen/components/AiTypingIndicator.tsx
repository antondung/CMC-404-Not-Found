import { useEffect, useState } from 'react';
import { BookOpen, MagnifyingGlass, PencilSimple } from '@phosphor-icons/react';

const STEPS = [
  { label: 'Đang tìm điều khoản liên quan…', Icon: MagnifyingGlass },
  { label: 'Đang đối chiếu căn cứ pháp lý…', Icon: BookOpen },
  { label: 'Đang soạn câu trả lời dễ hiểu…', Icon: PencilSimple },
] as const;

/** Minimal waiting state while BE2/QA is generating an answer. */
export function AiTypingIndicator() {
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(8);

  useEffect(() => {
    const stepId = window.setInterval(() => {
      setStep((i) => (i + 1) % STEPS.length);
    }, 2400);
    return () => window.clearInterval(stepId);
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => {
      setProgress((p) => {
        if (p >= 92) return 18 + Math.random() * 12;
        return Math.min(92, p + 3 + Math.random() * 5);
      });
    }, 420);
    return () => window.clearInterval(id);
  }, []);

  const ActiveIcon = STEPS[step].Icon;

  return (
    <div
      className="flex flex-col gap-2.5 py-1"
      role="status"
      aria-live="polite"
      aria-label="Đang chờ phản hồi từ trợ lý AI"
    >
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5" aria-hidden>
          <span className="ls-dot-bounce h-2 w-2 rounded-full bg-primary" />
          <span className="ls-dot-bounce h-2 w-2 rounded-full bg-primary" style={{ animationDelay: '0.16s' }} />
          <span className="ls-dot-bounce h-2 w-2 rounded-full bg-accent" style={{ animationDelay: '0.32s' }} />
        </div>
        <p key={step} className="ls-typing-status m-0 flex items-center gap-1.5 text-[15px] font-medium text-slate-600 sm:text-base">
          <ActiveIcon size={16} className="text-primary" weight="bold" aria-hidden />
          {STEPS[step].label}
        </p>
      </div>
      <div className="relative h-1 w-[200px] overflow-hidden rounded-full bg-slate-200/60 sm:w-[240px]" aria-hidden>
        <div
          className="ls-typing-progress h-full rounded-full bg-gradient-to-r from-primary via-[#4F7FE8] to-[#D97757] transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
