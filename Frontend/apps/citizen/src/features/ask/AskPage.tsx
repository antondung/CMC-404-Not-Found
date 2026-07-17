import { useState, useRef, useEffect } from 'react';
import { PaperPlaneRight, User, Robot, Scales, ShieldCheck, ArrowLeft, Trash, Lightbulb } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';
import { CitationCard } from '../../../../../packages/ui-legal/src/components/CitationCard';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  citations?: Array<{ soHieu: string; trichDan: string }>;
  isTyping?: boolean;
}

export default function AskPage() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'ai',
      content: 'Chào bạn, tôi là Trợ lý Pháp lý ảo của Cổng Thông tin Pháp luật. Tôi có thể giúp bạn giải đáp các quy định pháp luật hiện hành dựa trên cơ sở dữ liệu chính thức. Bạn cần hỏi về vấn đề gì?',
    }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    // Simulate AI typing
    const typingId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: typingId, role: 'ai', content: '', isTyping: true }]);

    setTimeout(() => {
      setMessages(prev => prev.map(msg => 
        msg.id === typingId 
        ? {
            id: typingId,
            role: 'ai',
            content: 'Theo quy định hiện hành, người điều khiển xe mô tô, xe gắn máy mà trong máu hoặc hơi thở có nồng độ cồn sẽ bị xử phạt hành chính từ 2.000.000 VNĐ đến 8.000.000 VNĐ tùy mức độ vi phạm, đồng thời tước quyền sử dụng Giấy phép lái xe từ 10 tháng đến 24 tháng.',
            citations: [
              { soHieu: 'Điểm c Khoản 6 Điều 6 - Nghị định 100/2019/NĐ-CP (Sửa đổi bởi NĐ 123/2021)', trichDan: 'Phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng đối với người điều khiển xe trên đường mà trong máu hoặc hơi thở có nồng độ cồn nhưng chưa vượt quá 50 miligam/100 mililít máu hoặc chưa vượt quá 0,25 miligam/1 lít khí thở.' }
            ]
          }
        : msg
      ));
    }, 1500);
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shrink-0 z-10 shadow-sm relative">
        <div className="h-16 max-w-5xl mx-auto px-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-slate-500 hover:text-brand transition-colors font-semibold text-sm">
            <ArrowLeft size={18} weight="bold" /> Quay lại Trang chủ
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand rounded flex items-center justify-center text-white">
              <Scales size={18} weight="fill" />
            </div>
            <h1 className="font-bold text-slate-800">Trợ lý Pháp lý AI</h1>
          </div>
          <button 
            onClick={() => setMessages([messages[0]])}
            className="flex items-center gap-2 text-slate-400 hover:text-red-500 transition-colors font-semibold text-sm"
          >
            <Trash size={18} /> Xóa hội thoại
          </button>
        </div>
      </header>

      {/* Chat Stream */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 pb-32">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`}>
              {msg.role === 'ai' && (
                <div className="w-10 h-10 rounded-full bg-brandLight flex items-center justify-center text-brand shrink-0 border border-brand/10 shadow-sm">
                  <Robot size={24} weight="fill" />
                </div>
              )}
              
              <div className={`max-w-[85%] rounded-2xl p-5 ${
                msg.role === 'user' 
                  ? 'bg-slate-900 text-white shadow-md rounded-tr-sm' 
                  : 'bg-white border border-slate-200 shadow-sm rounded-tl-sm'
              }`}>
                {msg.isTyping ? (
                  <div className="flex items-center gap-1.5 h-6">
                    <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  </div>
                ) : (
                  <>
                    <p className="text-[15px] leading-relaxed whitespace-pre-wrap font-medium">
                      {msg.content}
                    </p>
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-6 pt-4 border-t border-slate-100">
                        <div className="flex items-center gap-2 mb-3 text-xs font-bold text-emerald-600 uppercase tracking-wider">
                          <ShieldCheck size={16} weight="fill" /> Căn cứ pháp lý (Đã kiểm chứng)
                        </div>
                        <div className="space-y-3">
                          {msg.citations.map((cit, idx) => (
                            <CitationCard key={idx} soHieu={cit.soHieu} trichDan={cit.trichDan} />
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 shrink-0">
                  <User size={24} weight="fill" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Box - Fixed at bottom */}
      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-background via-background to-transparent pb-6 pt-10 px-4">
        <div className="max-w-3xl mx-auto">
          {messages.length === 1 && (
             <div className="flex flex-wrap gap-2 mb-4 justify-center">
               {["Mức phạt nồng độ cồn 2026?", "Quy định về nghỉ thai sản?", "Thủ tục làm CCCD gắn chip?"].map((suggestion, idx) => (
                 <button 
                   key={idx} 
                   onClick={() => setInput(suggestion)}
                   className="bg-white border border-slate-200 text-slate-600 px-4 py-2 rounded-full text-sm font-semibold hover:border-brand hover:text-brand transition-colors flex items-center gap-2 shadow-sm"
                 >
                   <Lightbulb size={16} weight="fill" className="text-amber-500" />
                   {suggestion}
                 </button>
               ))}
             </div>
          )}
          
          <form onSubmit={handleSend} className="relative group shadow-xl rounded-2xl">
            <input 
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Hỏi trợ lý pháp lý..."
              className="w-full bg-white border-2 border-slate-200 text-slate-900 rounded-2xl py-4 pl-6 pr-16 text-lg font-medium focus:outline-none focus:border-brand transition-colors"
            />
            <button 
              type="submit"
              disabled={!input.trim()}
              className="absolute right-2 top-2 bottom-2 bg-brand hover:bg-red-800 disabled:bg-slate-300 disabled:cursor-not-allowed text-white w-12 rounded-xl flex items-center justify-center transition-colors"
            >
              <PaperPlaneRight size={20} weight="fill" />
            </button>
          </form>
          <div className="text-center mt-3">
            <span className="text-[11px] font-medium text-slate-400">
              AI có thể mắc lỗi. Vui lòng luôn kiểm tra lại dựa trên các Căn cứ pháp lý đính kèm.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
