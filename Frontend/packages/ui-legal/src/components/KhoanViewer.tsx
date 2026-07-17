import React from 'react';
import { FileText, BookmarkSimple } from '@phosphor-icons/react';

interface KhoanViewerProps {
  vanBanSoHieu: string;
  dieuKhoan: string;
  noiDung: string;
  highlightText?: string;
}

export const KhoanViewer: React.FC<KhoanViewerProps> = ({ vanBanSoHieu, dieuKhoan, noiDung, highlightText }) => {
  // Helper to highlight specific text inside the full content
  const renderContent = () => {
    if (!highlightText) return <p className="text-slate-700 leading-relaxed">{noiDung}</p>;

    const parts = noiDung.split(new RegExp(`(${highlightText})`, 'gi'));
    
    return (
      <p className="text-slate-700 leading-relaxed">
        {parts.map((part, i) => 
          part.toLowerCase() === highlightText.toLowerCase() 
            ? <mark key={i} className="bg-yellow-200/80 text-slate-900 rounded-sm px-1 font-medium">{part}</mark>
            : part
        )}
      </p>
    );
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
      <div className="bg-slate-50/80 border-b border-slate-100 px-5 py-3.5 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex items-center gap-2">
          <BookmarkSimple size={18} className="text-brand" weight="fill" />
          <span className="font-bold text-slate-800">{dieuKhoan}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-500 bg-white px-2.5 py-1 rounded-md border border-slate-200">
          <FileText size={14} /> {vanBanSoHieu}
        </div>
      </div>
      <div className="p-6">
        {renderContent()}
      </div>
    </div>
  );
};
