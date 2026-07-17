import { useState, useRef, useEffect } from 'react';
import { PaperPlaneRight, User, Robot, ShieldCheck, WarningCircle, CaretRight, Path } from '@phosphor-icons/react';
import { CitationCard } from '../../../../../packages/ui-legal/src/components/CitationCard';
import { apiPost } from '../../lib/api';

interface BackendCitation {
  khoan_id?: string;
  quote: string;
  van_ban: string;
  dieu: string;
  score?: number;
}

interface QAResponse {
  answer: string;
  citations: BackendCitation[];
  graph_paths: string[];
  confidence: 'high' | 'medium' | 'low';
  refuse_reason?: string[];
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: BackendCitation[];
  confidence?: 'high' | 'medium' | 'low';
  isTyping?: boolean;
  graphPaths?: string[];
}

function GraphPathBreadcrumb({ paths }: { paths: string[] }) {
  if (!paths || paths.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3 text-xs font-mono text-slate-500 bg-slate-100/50 p-2.5 rounded-xl border border-slate-200/50">
      <Path size={14} className="text-brand mr-1" />
      <span className="font-bold text-slate-700">Graph Paths:</span>
      {paths.map((p, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <CaretRight size={10} />}
          <span className="bg-white border border-slate-200 shadow-sm px-1.5 py-0.5 rounded-md text-slate-600">{p}</span>
        </span>
      ))}
    </div>
  );
}

const generateId = () => crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);

export default function QAAdminPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'assistant', content: 'Chào bạn, tôi là trợ lý LexSocial. Tôi trả lời các quy định pháp luật dựa trên dữ liệu đã số hóa, luôn kèm trích dẫn nguyên văn.' },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || isLoading) return;

    const userMsgId = generateId();
    setMessages((prev) => [...prev, { id: userMsgId, role: 'user', content: question }]);
    setInput('');
    setIsLoading(true);

    const typingId = generateId();
    setMessages((prev) => [...prev, { id: typingId, role: 'assistant', content: '', isTyping: true }]);

    try {
      const data = await apiPost<QAResponse>('/admin/qa/ask', { question, graph_paths_enabled: true, audience: 'admin' });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { id: typingId, role: 'assistant', content: data.answer, citations: data.citations ?? [], confidence: data.confidence, graphPaths: data.graph_paths }
            : m,
        ),
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Lỗi không xác định';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { id: typingId, role: 'assistant', content: `Không thể kết nối máy chủ QA (${message}).`, confidence: 'low' }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
    }
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
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-4 max-w-[90%] md:max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm border ${msg.role === 'user' ? 'bg-primary text-white border-primary/20' : 'bg-white text-primary border-slate-200'}`}>
              {msg.role === 'user' ? <User size={20} weight="fill" /> : <Robot size={20} weight="fill" className="text-secondaryAccent" />}
            </div>
            <div className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'} max-w-[100%]`}>
              <div className={`p-5 rounded-2xl text-sm font-medium shadow-soft whitespace-pre-wrap ${msg.role === 'user' ? 'bg-primary text-white rounded-tr-none' : 'bg-surface text-primary rounded-tl-none border border-border'}`}>
                {msg.isTyping ? (
                  <div className="flex items-center gap-1.5 h-5">
                    <span className="w-2 h-2 rounded-full bg-secondaryAccent/50 animate-bounce"></span>
                    <span className="w-2 h-2 rounded-full bg-secondaryAccent/70 animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-2 h-2 rounded-full bg-secondaryAccent/90 animate-bounce [animation-delay:-0.3s]"></span>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="w-full md:min-w-[450px] space-y-3 mt-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-600 uppercase tracking-widest">
                    <ShieldCheck size={16} weight="fill" /> Căn cứ pháp lý đã xác thực
                  </div>
                  {msg.citations.map((cit, idx) => (
                    <CitationCard key={idx} van_ban={cit.van_ban} dieu={cit.dieu} quote={cit.quote} khoan_id={cit.khoan_id} />
                  ))}
                </div>
              )}
              {msg.graphPaths && msg.graphPaths.length > 0 && (
                <GraphPathBreadcrumb paths={msg.graphPaths} />
              )}
              {msg.role === 'assistant' && !msg.isTyping && (!msg.citations || msg.citations.length === 0) && msg.id !== 'welcome' && (
                <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600">
                  <WarningCircle size={14} weight="fill" /> Không có căn cứ nào được xác thực cho câu trả lời này.
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="p-6 bg-surface border-t border-border flex gap-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhập tình huống pháp lý hoặc câu hỏi..."
          className="flex-1 bg-white border border-slate-200 text-slate-800 rounded-xl px-5 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-sm"
        />
        <button type="submit" disabled={isLoading || !input.trim()} className="bg-primary text-white px-6 py-4 rounded-xl hover:bg-primary/90 transition-all flex items-center gap-2 font-bold disabled:opacity-50 disabled:cursor-not-allowed shadow-sm">
          Gửi <PaperPlaneRight size={18} weight="bold" />
        </button>
      </form>
    </div>
  );
}
