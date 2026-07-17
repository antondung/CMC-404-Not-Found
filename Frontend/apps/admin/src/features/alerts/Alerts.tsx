import React from 'react';
import { CheckCircle, ChatCircle, BookBookmark } from '@phosphor-icons/react';
import { RiskBadge } from '../../../../../packages/ui-legal/src/components/RiskBadge';
import { CitationCard } from '../../../../../packages/ui-legal/src/components/CitationCard';

const MOCK_ALERTS = [
  {
    id: '1',
    topic: 'Cấm xe máy vào nội đô 2026',
    platform: 'Facebook',
    postContent: 'Nghe nói từ 1/7/2026 nhà nước sẽ cấm toàn bộ xe máy vào trung tâm TP, anh em chuyển bị đi xe đạp hết đi.',
    riskLevel: 'mau_thuan',
    confidence: 0.95,
    citation: {
      soHieu: 'Khoản 2 Điều 21 - Luật Thủ đô 2024',
      trichDan: 'Chỉ giới hạn phương tiện gây ô nhiễm ở vùng phát thải thấp, KHÔNG cấm toàn bộ xe máy.'
    }
  }
];

export default function AlertsPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <header className="mb-8">
        <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Radar Giám sát Mạng xã hội</h2>
        <p className="text-slate-500 font-medium mt-2 text-lg">Phân tích chéo và phát hiện mâu thuẫn với cơ sở dữ liệu Luật gốc</p>
      </header>

      <div className="space-y-6">
        {MOCK_ALERTS.map((alert) => (
          <div key={alert.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden animate-fade-in-up">
            
            {/* Header / Meta */}
            <div className="bg-slate-50/80 px-6 py-4 border-b border-slate-100 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#1877F2]/10 text-[#1877F2]">
                  <ChatCircle size={18} weight="fill" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">{alert.platform}</div>
                  <div className="text-sm font-semibold text-slate-700">Chủ đề: {alert.topic}</div>
                </div>
              </div>
              <RiskBadge level={alert.riskLevel as any} confidence={alert.confidence} />
            </div>

            {/* Body */}
            <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
              
              {/* Cột trái: Thông tin MXH */}
              <div>
                <h4 className="text-xs font-bold text-slate-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                  Nội dung thu thập
                </h4>
                <div className="relative">
                  <div className="absolute top-0 left-0 w-1 h-full bg-slate-200 rounded-full"></div>
                  <p className="pl-5 text-slate-700 text-lg font-medium italic leading-relaxed">
                    "{alert.postContent}"
                  </p>
                </div>
              </div>

              {/* Cột phải: Đối chiếu Luật */}
              <div className="bg-blue-50/50 rounded-xl p-5 border border-blue-100">
                <h4 className="text-xs font-bold text-blue-600 mb-3 uppercase tracking-wider flex items-center gap-2">
                  <BookBookmark size={16} weight="fill" />
                  Đối chiếu cơ sở dữ liệu Luật
                </h4>
                <CitationCard {...alert.citation} />
              </div>

            </div>

            {/* Actions */}
            <div className="bg-white px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
              <button className="px-5 py-2.5 rounded-lg font-semibold text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 transition-colors text-sm">
                Đánh dấu an toàn
              </button>
              <button className="px-5 py-2.5 rounded-lg font-bold text-white bg-red-600 hover:bg-red-700 shadow-sm transition-colors text-sm flex items-center gap-2">
                Tạo báo cáo đính chính
              </button>
            </div>
            
          </div>
        ))}
      </div>
    </div>
  );
}
