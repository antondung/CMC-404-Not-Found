import React from 'react';
import { CheckCircle, WarningCircle, Question } from '@phosphor-icons/react';

export type RiskLevel = 'khop' | 'mau_thuan' | 'khong_ro';

export interface RiskBadgeProps {
  level: RiskLevel;
  confidence?: number;
}

export function RiskBadge({ level, confidence }: RiskBadgeProps) {
  const config = {
    khop: {
      color: 'text-success',
      bg: 'bg-success/10',
      border: 'border-success/20',
      icon: <CheckCircle size={16} weight="fill" />,
      label: 'Khớp với quy định đã liên kết'
    },
    mau_thuan: {
      color: 'text-destructive',
      bg: 'bg-destructive/10',
      border: 'border-destructive/20',
      icon: <WarningCircle size={16} weight="fill" />,
      label: 'Có dấu hiệu mâu thuẫn — cần kiểm chứng'
    },
    khong_ro: {
      color: 'text-warning',
      bg: 'bg-warning/10',
      border: 'border-warning/20',
      icon: <Question size={16} weight="fill" />,
      label: 'Chưa đủ căn cứ để kết luận'
    }
  };

  const { color, bg, border, icon, label } = config[level];

  return (
    <div className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${bg} ${border} ${color}`}>
      {icon}
      <span>{label}</span>
      {confidence && <span className="opacity-75 font-normal ml-1">{(confidence * 100).toFixed(0)}%</span>}
    </div>
  );
}
