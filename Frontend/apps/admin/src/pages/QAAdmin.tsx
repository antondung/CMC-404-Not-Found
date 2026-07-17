import React, { useState } from 'react';
import { PaperPlaneRight, User, Robot } from '@phosphor-icons/react';
import { CitationCard } from '../../../../packages/ui-legal/src/components/CitationCard';

export default function QAAdminPage() {
  const [messages, setMessages] = useState<any[]>([
    { role: 'assistant', content: 'Chào bạn, tôi là trợ lý LexSocial. Tôi có thể giải đáp các quy định pháp luật dựa trên dữ liệu đã số hóa.' }
  ]);
  const [input, setInput] = useState('');

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setInput('');
    
    setTimeout(() => {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Theo dữ liệu hiện tại, quy định bạn hỏi đã được cập nhật.',
        citation: {
          soHieu: 'Nghị định XYZ/2026',
          dieuKhoan: 'Điểm a Khoản 1 Điều 5',
          trichDan: 'Phạt tiền từ 2.000.000 đến 3.000.000 đồng đối với hành vi vi phạm...'
        }
      } as any]);
    }, 1000);
  };

  return (
    <div className="max-w-4xl mx-auto h-[85vh] flex flex-col bg-surface rounded-2xl overflow-hidden shadow-card">
      <header className="p-6 border-b border-border bg-surface flex items-center justify-between z-10 shadow-sm relative">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-info"></div>
        <div>
          <h2 className="text-xl font-bold text-primary flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-info flex items-center justify-center text-white shadow-md">
              <Robot size={24} weight="fill" />
            </div>
            QA Bot (Kiểm thử Nội bộ)
          </h2>
          <p className="text-xs text-muted mt-2 font-medium">Bắt buộc trích dẫn (Evidence over answer)</p>
        </div>
      </header>
      
      <div className="flex-1 p-8 overflow-y-auto space-y-8 bg-background">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-4 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-md ${msg.role === 'user' ? 'bg-gradient-dark text-white' : 'bg-gradient-info text-white'}`}>
              {msg.role === 'user' ? <User size={20} weight="fill" /> : <Robot size={20} weight="fill" />}
            </div>
            <div className={`space-y-4 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`p-5 rounded-2xl text-sm font-medium shadow-soft ${msg.role === 'user' ? 'bg-primary text-white rounded-tr-none' : 'bg-surface text-primary rounded-tl-none border border-border'}`}>
                {msg.content}
              </div>
              {msg.citation && (
                <div className="w-[500px]">
                  <CitationCard {...msg.citation} />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      
      <form onSubmit={handleSend} className="p-6 bg-surface border-t border-border flex gap-4">
        <input 
          type="text" 
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Nhập tình huống pháp lý..."
          className="flex-1 bg-background border border-border text-primary rounded-xl px-5 py-4 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-secondaryAccent/30 focus:border-secondaryAccent transition-all shadow-inner"
        />
        <button type="submit" className="bg-gradient-accent text-white px-8 py-4 rounded-xl hover:shadow-lg transition-all flex items-center gap-2 font-bold">
          Gửi <PaperPlaneRight size={18} weight="bold" />
        </button>
      </form>
    </div>
  );
}
