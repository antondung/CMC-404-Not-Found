import { Link, useNavigate } from 'react-router-dom';
import { MagnifyingGlass, BookOpen, Article, Scales, ShieldCheck, ArrowRight, Sparkle, Clock, LockKey } from '@phosphor-icons/react';

function Header() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 bg-brand rounded-lg flex items-center justify-center text-white shadow-sm group-hover:bg-red-800 transition-colors">
            <Scales size={24} weight="fill" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight leading-none">LexSocial AI</h1>
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Cổng thông tin pháp luật</span>
          </div>
        </Link>
        <nav className="hidden md:flex items-center gap-8">
          <Link to="/" className="text-sm font-bold text-brand flex items-center gap-2">
            <MagnifyingGlass size={18} weight="bold" /> Trợ lý Pháp lý
          </Link>
          <Link to="/news" className="text-sm font-semibold text-slate-600 hover:text-brand transition-colors flex items-center gap-2">
            <Article size={18} /> Tin tức tóm tắt
          </Link>
          <Link to="/van-ban" className="text-sm font-semibold text-slate-600 hover:text-brand transition-colors flex items-center gap-2">
            <BookOpen size={18} /> Tra cứu Văn bản
          </Link>
        </nav>
      </div>
    </header>
  );
}

function HeroSection() {
  const navigate = useNavigate();

  return (
    <div className="relative overflow-hidden bg-slate-900 pt-6 pb-16 lg:pt-10 lg:pb-24">
      {/* Premium Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[25%] -left-[10%] w-[50%] h-[50%] rounded-full bg-brand/20 blur-[120px]" />
        <div className="absolute top-[20%] -right-[10%] w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[100px]" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMiIgY3k9IjIiIHI9IjEiIGZpbGw9InJnYmEoMjU1LDI1NSwyNTUsMC4wNSkiLz48L3N2Zz4=')] [mask-image:linear-gradient(to_bottom,white,transparent)]" />
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 relative z-10 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-white/90 text-sm font-semibold mb-8 backdrop-blur-md">
          <Sparkle size={16} weight="fill" className="text-brandLight" />
          <span>Phiên bản thử nghiệm AI 2026</span>
        </div>
        
        <h2 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight mb-8 leading-[1.15]">
          Tra cứu pháp luật <br className="hidden sm:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-brand">nhanh chóng & chính xác</span>
        </h2>
        
        <p className="text-lg sm:text-xl text-slate-300 mb-12 max-w-2xl mx-auto leading-relaxed">
          Hệ thống Trợ lý Ảo AI giải đáp thắc mắc dựa trên cơ sở dữ liệu chính thức, luôn đính kèm Căn cứ pháp lý nguyên văn.
        </p>
        
        <div className="relative max-w-2xl mx-auto group">
          <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none">
            <MagnifyingGlass size={24} className="text-slate-400 group-focus-within:text-brand transition-colors" />
          </div>
          <input 
            type="text" 
            placeholder="Ví dụ: Quy định thai sản cho lao động nam?"
            className="w-full bg-white/10 backdrop-blur-xl border border-white/20 text-white placeholder:text-slate-400 rounded-3xl py-6 pl-16 pr-40 text-lg font-medium shadow-2xl focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all focus:bg-white/15"
          />
          <div className="absolute inset-y-0 right-2 flex items-center">
            <button 
              onClick={() => navigate('/ask')}
              className="bg-brand hover:bg-red-600 text-white font-bold py-4 px-8 rounded-2xl transition-all shadow-lg hover:shadow-brand/25 flex items-center gap-2 hover:-translate-y-0.5"
            >
              Hỏi AI <ArrowRight size={18} weight="bold" />
            </button>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-6 sm:gap-10 text-sm text-slate-300 font-medium">
          <span className="flex items-center gap-2"><ShieldCheck size={20} className="text-emerald-400" /> Trả lời kèm Trích dẫn gốc</span>
          <span className="flex items-center gap-2"><Clock size={20} className="text-blue-400" /> Cập nhật thời gian thực</span>
          <span className="flex items-center gap-2"><LockKey size={20} className="text-purple-400" /> Bảo mật thông tin</span>
        </div>
      </div>
    </div>
  );
}

function NewsHighlight() {
  const news = [
    { id: 1, title: 'Hướng dẫn mới về xử phạt vi phạm giao thông nội đô áp dụng từ T7/2026', type: 'Giao thông', time: '2 giờ trước', readTime: '3 phút đọc' },
    { id: 2, title: 'Quy định quản lý dữ liệu cá nhân trên các nền tảng mạng xã hội xuyên biên giới', type: 'Công nghệ', time: '5 giờ trước', readTime: '5 phút đọc' },
    { id: 3, title: 'Thay đổi về mức đóng BHXH tự nguyện áp dụng cho người lao động tự do', type: 'Lao động', time: '1 ngày trước', readTime: '4 phút đọc' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 relative z-20 -mt-10">
      <div className="flex items-end justify-between mb-8 px-2">
        <div>
          <h3 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
            Điểm tin Pháp luật
          </h3>
          <p className="text-slate-500 font-medium mt-2">Các văn bản và chính sách mới nhất vừa được ban hành</p>
        </div>
        <Link to="/news" className="text-brand font-bold hover:text-red-800 transition-colors flex items-center gap-1 group">
          Xem tất cả <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {news.map(item => (
          <div key={item.id} className="bg-white p-8 rounded-3xl border border-slate-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_40px_rgb(0,0,0,0.08)] hover:-translate-y-1 transition-all cursor-pointer group flex flex-col justify-between h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-brand/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            
            <div>
              <div className="flex items-center justify-between mb-6">
                <span className="inline-flex items-center px-3 py-1 bg-slate-50 text-slate-600 text-xs font-bold rounded-lg uppercase tracking-wider border border-slate-100">
                  {item.type}
                </span>
                <span className="text-xs font-semibold text-slate-400 flex items-center gap-1">
                  <Clock size={14} /> {item.time}
                </span>
              </div>
              <h4 className="text-xl font-bold text-slate-800 leading-snug group-hover:text-brand transition-colors">
                {item.title}
              </h4>
            </div>
            
            <div className="mt-8 pt-6 border-t border-slate-50 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400">
                {item.readTime}
              </span>
              <div className="flex items-center text-sm font-bold text-brand opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all">
                Đọc tóm tắt <ArrowRight size={16} className="ml-1" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="flex-1">
        <HeroSection />
        <NewsHighlight />
      </main>
      <footer className="bg-white border-t border-slate-200 py-10 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-slate-500 text-sm font-medium">
          <p>© 2026 LexSocial AI - Cổng thông tin pháp luật.</p>
          <p className="mt-1">Dữ liệu được trích xuất tự động, mang tính chất tham khảo. Luôn đối chiếu với Văn bản gốc.</p>
        </div>
      </footer>
    </div>
  );
}
