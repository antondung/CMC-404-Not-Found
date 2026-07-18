import { useState, useRef, useEffect, useCallback } from 'react';
import { PaperPlaneRight, User, Robot, Scales, ShieldCheck, ArrowLeft, Trash, Lightbulb, WarningCircle, CalendarBlank, ArrowSquareOut } from '@phosphor-icons/react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CitationCard } from '../../../../../packages/ui-legal/src/components/CitationCard';
import { GraphPathBreadcrumb } from '../../../../../packages/ui-legal/src/components/GraphPathBreadcrumb';
import { AnswerMarkdown } from '../../../../../packages/ui-legal/src/components/AnswerMarkdown';
import { apiPost } from '../../lib/api';


// graph_paths comes back as structured objects ({khoan_id, nodes, edges}); keep it loose here
// and let GraphPathBreadcrumb normalize it (string OR object) so rendering can't crash.
type GraphPath = unknown;

interface QAResponse {
  answer: string;
  citations: BackendCitation[];
  graph_paths: GraphPath[];
  confidence: 'high' | 'medium' | 'low';
  refuse_reason?: string[];
  as_of?: string;
  notices?: ChangeNotice[];
}

interface ChangeNotice {
  khoan_van_ban?: string;
  thay_the_boi?: string;
  tu_ngay: string;
  message: string;
}

// Tương thích hoàn toàn với Contract API Backend (Mục 6.4 SYSTEM_BACKEND.md)
export interface BackendCitation {
  khoan_id?: string;
  quote: string;
  van_ban: string;
  dieu: string;
  score?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  citations?: BackendCitation[];
  graphPaths?: GraphPath[];
  confidence?: 'high' | 'medium' | 'low';
  isTyping?: boolean;
  asOf?: string;
  notices?: ChangeNotice[];
}

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'ai',
  content:
    'Chào bạn, tôi là Trợ lý Pháp lý ảo của Cổng Thông tin Pháp luật. Tôi có thể giúp bạn giải đáp các quy định pháp luật hiện hành dựa trên cơ sở dữ liệu chính thức. \n\nBạn cần hỏi về vấn đề gì?',
};

export default function AskPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isTypingComplete, setIsTypingComplete] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isLoadingRef = useRef(false);
  const asOfRef = useRef(asOf);
  const autoSentRef = useRef(false);

  useEffect(() => {
    asOfRef.current = asOf;
  }, [asOf]);

  const scrollToBottom = () => {
    const mainEl = document.querySelector('main');
    if (mainEl) {
      mainEl.scrollTo({ top: mainEl.scrollHeight, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendQuestion = useCallback(async (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question || isLoadingRef.current) return;

    isLoadingRef.current = true;
    setIsLoading(true);
    setInput('');

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: question };
    const typingId = (Date.now() + 1).toString();
    setMessages((prev) => [...prev, userMsg, { id: typingId, role: 'ai', content: '', isTyping: true }]);

    const asOfVal = asOfRef.current;
    try {
      const data = await apiPost<QAResponse>('/citizen/qa/ask', { question, as_of: asOfVal });
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === typingId
            ? {
                id: typingId,
                role: 'ai',
                content: data.answer,
                citations: data.citations ?? [],
                graphPaths: data.graph_paths ?? [],
                confidence: data.confidence,
                asOf: data.as_of ?? asOfVal,
                notices: data.notices ?? [],
              }
            : msg,
        ),
      );
      setIsTypingComplete((prev) => ({ ...prev, [typingId]: true }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Lỗi không xác định';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === typingId
            ? {
                id: typingId,
                role: 'ai',
                content: `Xin lỗi, hiện chưa thể kết nối tới máy chủ trợ lý pháp lý (${message}). Vui lòng thử lại sau.`,
                confidence: 'low',
              }
            : msg,
        ),
      );
      setIsTypingComplete((prev) => ({ ...prev, [typingId]: true }));
    } finally {
      isLoadingRef.current = false;
      setIsLoading(false);
    }
  }, []);

  // Home → /ask?q=... : keep the question and auto-submit once.
  useEffect(() => {
    const q = searchParams.get('q')?.trim();
    if (!q || autoSentRef.current) return;
    autoSentRef.current = true;
    navigate('/ask', { replace: true });
    void sendQuestion(q);
  }, [searchParams, navigate, sendQuestion]);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    await sendQuestion(input);
  };

  const handleSuggestion = (suggestion: string) => {
    void sendQuestion(suggestion);
  };

  const clearChat = () => {
    setMessages([WELCOME_MESSAGE]);
    setIsTypingComplete({});
    setInput('');
  };

  return (
    <div className="flex flex-col h-screen bg-[#f8fafc] font-sans selection:bg-brand selection:text-white">
      {/* Header - Glassmorphism */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-slate-200/80 shrink-0 z-20 sticky top-0">
        <div className="h-[72px] max-w-5xl mx-auto px-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-colors font-bold text-sm bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-full">
            <ArrowLeft size={16} weight="bold" /> Trang chủ
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-brand to-red-800 rounded-xl flex items-center justify-center text-white shadow-md shadow-brand/20">
              <Scales size={22} weight="fill" />
            </div>
            <div className="flex flex-col">
              <h1 className="font-black text-slate-900 tracking-tight leading-tight">Trợ lý AI</h1>
              <span className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span> Sẵn sàng
              </span>
            </div>
          </div>
          <button 
            onClick={clearChat}
            className="flex items-center gap-2 text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all font-bold text-sm px-4 py-2 rounded-full group"
          >
            <Trash size={16} weight="bold" className="group-hover:scale-110 transition-transform" /> <span className="hidden sm:inline">Xóa hội thoại</span>
          </button>
        </div>
      </header>

      {/* Chat Stream */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 pb-40 scroll-smooth">
        <div className="max-w-4xl mx-auto space-y-8">
          {messages.map((msg, index) => (
            <div key={msg.id} className={`flex gap-3 sm:gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`} style={{ animationDelay: `${index * 0.05}s` }}>
              {msg.role === 'ai' && (
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-gradient-to-br from-brandLight to-white flex items-center justify-center text-brand shrink-0 border border-brand/10 shadow-sm shadow-brand/5">
                  <Robot size={24} weight="fill" />
                </div>
              )}
              
              <div className={`max-w-[90%] sm:max-w-[80%] rounded-[24px] p-5 sm:p-6 ${
                msg.role === 'user' 
                  ? 'bg-gradient-to-br from-slate-800 to-slate-900 text-white shadow-xl shadow-slate-900/10 rounded-tr-[8px]' 
                  : 'bg-white border border-slate-200/60 shadow-lg shadow-slate-200/40 rounded-tl-[8px]'
              }`}>
                {msg.isTyping ? (
                  <div className="flex items-center gap-2 h-6 px-2">
                    <div className="w-2.5 h-2.5 bg-brand/40 rounded-full animate-bounce"></div>
                    <div className="w-2.5 h-2.5 bg-brand/60 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-2.5 h-2.5 bg-brand/80 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  </div>
                ) : (
                  <>
                    {msg.role === 'ai' ? (
                      <AnswerMarkdown content={msg.content} />
                    ) : (
                      <p className="text-[15px] sm:text-[16px] leading-relaxed whitespace-pre-wrap font-medium">
                        {msg.content}
                      </p>
                    )}

                    {msg.role === 'ai' && msg.asOf && (
                      <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600">
                        <CalendarBlank size={15} weight="bold" /> Áp dụng pháp luật tại ngày {new Date(`${msg.asOf}T00:00:00`).toLocaleDateString('vi-VN')}
                      </div>
                    )}

                    {msg.notices?.map((notice, idx) => (
                      <div key={`${notice.tu_ngay}-${idx}`} className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950">
                        <div className="flex gap-3">
                          <WarningCircle size={22} weight="fill" className="mt-0.5 shrink-0 text-amber-500" />
                          <div>
                            <p className="font-black">Quy định này thay đổi từ {new Date(`${notice.tu_ngay}T00:00:00`).toLocaleDateString('vi-VN')}</p>
                            <p className="mt-1 text-sm leading-relaxed">{notice.message}</p>
                            <a href="/admin/diff" target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-bold text-amber-800 hover:underline">
                              Xem thay đổi <ArrowSquareOut size={15} weight="bold" />
                            </a>
                          </div>
                        </div>
                      </div>
                    ))}
                    
                    {msg.citations && msg.citations.length > 0 && (msg.role === 'user' || isTypingComplete[msg.id] || msg.id === 'welcome') && (
                      <div className="mt-8 pt-6 border-t border-slate-100 animate-fade-in-up">
                        <div className="flex items-center gap-2 mb-4 text-xs font-bold text-emerald-600 uppercase tracking-widest bg-emerald-50 w-fit px-3 py-1.5 rounded-lg border border-emerald-100">
                          <ShieldCheck size={16} weight="fill" /> Đã xác thực căn cứ pháp lý
                        </div>
                        <div className="space-y-3">
                          {msg.citations.map((cit, idx) => (
                            <CitationCard key={idx} van_ban={cit.van_ban} dieu={cit.dieu} quote={cit.quote} khoan_id={cit.khoan_id} />
                          ))}
                        </div>
                      </div>
                    )}

                    {msg.graphPaths && (msg.role === 'user' || isTypingComplete[msg.id] || msg.id === 'welcome') && (
                      <div className="animate-fade-in-up">
                        <GraphPathBreadcrumb paths={msg.graphPaths} />
                      </div>
                    )}
                  </>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-slate-200 flex items-center justify-center text-slate-600 shrink-0 shadow-sm">
                  <User size={24} weight="fill" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} className="h-32 sm:h-40 shrink-0" />
        </div>
      </main>

      {/* Input Box - Floating fixed at bottom */}
      <div className="fixed bottom-0 inset-x-0 bg-gradient-to-t from-[#f8fafc] via-[#f8fafc]/90 to-transparent pb-6 pt-12 px-4 z-20 pointer-events-none">
        <div className="max-w-4xl mx-auto pointer-events-auto">
          {messages.length === 1 && (
             <div className="flex flex-wrap gap-2 sm:gap-3 mb-6 justify-center">
               {["Mức phạt nồng độ cồn 2026?", "Quy định về nghỉ thai sản?", "Thủ tục làm CCCD gắn chip?"].map((suggestion, idx) => (
                 <button 
                   key={idx} 
                   onClick={() => handleSuggestion(suggestion)}
                   className="bg-white/80 backdrop-blur border border-slate-200/80 text-slate-700 px-5 py-2.5 rounded-full text-sm font-semibold hover:border-brand/50 hover:bg-brandLight hover:text-brand transition-all flex items-center gap-2 shadow-sm hover:shadow-md hover:-translate-y-0.5"
                 >
                   <Lightbulb size={16} weight="fill" className="text-amber-500" />
                   {suggestion}
                 </button>
               ))}
             </div>
          )}
          
          <form id="chat-form" onSubmit={handleSend} className="relative group shadow-2xl shadow-slate-200/50 rounded-[28px] flex items-end bg-white border border-slate-200/80 p-2 transition-all focus-within:border-brand/50 focus-within:ring-4 focus-within:ring-brand/10">
            <label className="absolute -top-11 left-2 flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 shadow-sm">
              <CalendarBlank size={16} className="text-brand" weight="bold" />
              Thời điểm áp dụng
              <input
                type="date"
                value={asOf}
                onChange={(event) => setAsOf(event.target.value)}
                className="bg-transparent font-bold text-slate-900 outline-none"
                aria-label="Thời điểm áp dụng pháp luật"
              />
            </label>
            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Nhập câu hỏi pháp lý của bạn..."
              className="w-full bg-transparent text-slate-900 py-4 pl-6 pr-16 text-lg font-medium focus:outline-none resize-none max-h-32 min-h-[60px]"
              rows={1}
            />
            <button 
              type="submit"
              disabled={!input.trim()}
              className="absolute right-3 bottom-3 bg-brand hover:bg-red-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed text-white w-12 h-12 rounded-2xl flex items-center justify-center transition-all disabled:shadow-none shadow-lg shadow-brand/30 hover:scale-105 active:scale-95"
            >
              <PaperPlaneRight size={22} weight="fill" />
            </button>
          </form>
          
          <div className="text-center mt-4 flex items-center justify-center gap-1.5 opacity-60">
            <WarningCircle size={14} className="text-slate-500" />
            <span className="text-xs font-semibold text-slate-500">
              AI có thể trả lời không chính xác. Hãy luôn đối chiếu với Căn cứ pháp lý nguyên văn đính kèm.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
