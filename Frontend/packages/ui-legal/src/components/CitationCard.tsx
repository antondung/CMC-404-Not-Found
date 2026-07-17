import React from 'react';
import { Scales } from '@phosphor-icons/react';

interface CitationCardProps {
  soHieu: string;
  trichDan: string;
}

export const CitationCard: React.FC<CitationCardProps> = ({ soHieu, trichDan }) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
      <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex items-center gap-2">
        <Scales size={16} className="text-slate-500" weight="fill" />
        <span className="text-xs font-bold text-slate-700">{soHieu}</span>
      </div>
      <div className="p-4">
        <p className="text-sm font-medium text-slate-700 leading-relaxed">
          "{trichDan}"
        </p>
      </div>
    </div>
  );
};
