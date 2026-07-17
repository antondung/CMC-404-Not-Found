import React from 'react';
import { ShieldWarning, CheckCircle, Warning } from '@phosphor-icons/react';

type RiskLevel = 'mau_thuan' | 'chua_du_can_cu' | 'khop';

interface RiskBadgeProps {
  level: RiskLevel;
  confidence: number;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, confidence }) => {
  const config = {
    mau_thuan: {
      color: 'text-red-700',
      bg: 'bg-red-50',
      border: 'border-red-200',
      icon: <ShieldWarning size={16} weight="fill" />,
      text: 'Có dấu hiệu mâu thuẫn'
    },
    chua_du_can_cu: {
      color: 'text-amber-700',
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      icon: <Warning size={16} weight="fill" />,
      text: 'Chưa đủ căn cứ'
    },
    khop: {
      color: 'text-emerald-700',
      bg: 'bg-emerald-50',
      border: 'border-emerald-200',
      icon: <CheckCircle size={16} weight="fill" />,
      text: 'Thông tin chính xác'
    }
  };

  const current = config[level];

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${current.bg} ${current.border} ${current.color}`}>
      {current.icon}
      <span className="text-xs font-bold tracking-wide uppercase">{current.text}</span>
      {confidence && (
        <span className="text-[10px] font-semibold opacity-70 border-l border-current pl-2 ml-1">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
};
