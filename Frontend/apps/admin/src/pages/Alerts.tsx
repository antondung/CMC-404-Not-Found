import React from 'react';
import { WarningCircle, CheckCircle, Question, Megaphone } from '@phosphor-icons/react';
import { RiskBadge } from '../../../../packages/ui-legal/src/components/RiskBadge';
import { CitationCard } from '../../../../packages/ui-legal/src/components/CitationCard';

const MOCK_ALERTS = [
  {
    id: '1',
    topic: 'Cấm xe máy vào nội đô 2026',
    platform: 'Facebook',
    postContent: 'Nghe nói từ 1/7/2026 nhà nước sẽ cấm toàn bộ xe máy vào trung tâm TP, anh em chuyển bị đi xe đạp hết đi.',
    riskLevel: 'mau_thuan',
    confidence: 0.95,
    citation: {
      soHieu: 'Luật Thủ đô 2024',
      dieuKhoan: 'Khoản 2 Điều 21',
      trichDan: 'Chỉ giới hạn phương tiện gây ô nhiễm ở vùng phát thải thấp, KHÔNG cấm toàn bộ xe máy.'
    }
  }
];

export default function AlertsPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <header className="mb-6">
        <h2 className="text-2xl font-bold text-primary tracking-tight">Radar Cảnh báo MXH</h2>
        <p className="text-muted font-medium mt-1">Hệ thống phát hiện mâu thuẫn thông tin và luật gốc</p>
      </header>

      <div className="space-y-6">
        {MOCK_ALERTS.map((alert) => (
          <div key={alert.id} className="bg-surface rounded-2xl p-8 shadow-card flex gap-8 items-start relative overflow-hidden animate-fade-in-up">
            {alert.riskLevel === 'mau_thuan' && (
              <div className="absolute top-0 left-0 bottom-0 w-2 bg-gradient-danger"></div>
            )}
            <div className="flex-1 space-y-6">
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="bg-primary text-white text-[10px] px-2.5 py-1 rounded-md font-bold uppercase tracking-wider">{alert.platform}</span>
                    <span className="text-muted text-sm font-bold">Chủ đề: <strong className="text-primary">{alert.topic}</strong></span>
                  </div>
                  <p className="text-primary text-lg font-medium mt-2 bg-background p-5 rounded-2xl border border-border/50 shadow-inner">
                    "{alert.postContent}"
                  </p>
                </div>
                <RiskBadge level={alert.riskLevel as any} confidence={alert.confidence} />
              </div>
              
              <div className="pt-2">
                <h4 className="text-xs font-bold text-muted mb-3 uppercase tracking-wider flex items-center gap-2">
                  <CheckCircle size={16} className="text-success" weight="fill" />
                  Đối chiếu Luật gốc
                </h4>
                <CitationCard {...alert.citation} />
              </div>
            </div>
            
            <div className="w-56 flex flex-col gap-4 shrink-0 pt-2 border-l border-border pl-8">
              <button className="w-full bg-gradient-danger text-white py-3 px-4 rounded-xl font-bold text-sm flex justify-center items-center gap-2 hover:shadow-lg shadow-destructive/30 transition-all">
                <Megaphone weight="fill" size={18} /> Đề xuất Đính chính
              </button>
              <button className="w-full bg-background border border-border text-primary py-3 px-4 rounded-xl font-bold text-sm flex justify-center items-center hover:bg-surface hover:shadow-soft transition-all">
                Bỏ qua
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
