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

  useEffect(() => {
    const stepId = window.setInterval(() => {
      setStep((i) => (i + 1) % STEPS.length);
    }, 2400);
    return () => window.clearInterval(stepId);
  }, []);

  const ActiveIcon = STEPS[step].Icon;

  return (
    <div
      className="flex items-center gap-3 py-0.5"
      role="status"
      aria-live="polite"
      aria-label="Đang chờ phản hồi từ trợ lý AI"
    >
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
  );
}
