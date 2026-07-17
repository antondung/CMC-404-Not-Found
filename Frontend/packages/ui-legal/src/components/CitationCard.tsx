import React from 'react';
import { BookOpen, ArrowSquareOut } from '@phosphor-icons/react';

export interface CitationCardProps {
  id?: string;
  soHieu: string;
  dieuKhoan: string;
  trichDan: string;
  onClick?: () => void;
}

export function CitationCard({ soHieu, dieuKhoan, trichDan, onClick }: CitationCardProps) {
  return (
    <div 
      onClick={onClick}
      className="bg-background border border-border p-4 rounded-xl cursor-pointer hover:border-accent/50 hover:shadow-card transition-all group"
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center space-x-2 text-sm font-semibold text-primary">
          <BookOpen size={18} className="text-accent" weight="fill" />
          <span>{dieuKhoan} - {soHieu}</span>
        </div>
        <ArrowSquareOut size={16} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      <p className="text-sm text-primary/80 line-clamp-3 leading-relaxed mt-2 bg-surface p-3 rounded-lg border border-border/50">
        "{trichDan}"
      </p>
    </div>
  );
}
