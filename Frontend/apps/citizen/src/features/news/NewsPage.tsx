import { ArrowLeft, Article, PlayCircle, ShieldCheck, Tag, CaretRight, Scales, Clock } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';

export default function NewsPage() {
  const newsItems = [
    {
      id: 1,
      title: "Luật Đất đai (sửa đổi) chính thức thông qua: 5 điểm mới người dân cần biết",
      summary: "Bỏ khung giá đất, cấp sổ đỏ cho đất không giấy tờ trước ngày 01/7/2014, quy định chặt chẽ hơn về thu hồi đất...",
      date: "Vừa xong",
      category: "Bất động sản",
      isHot: true,
      mediaType: "text",
      color: "from-brand to-red-900"
    },
    {
      id: 2,
      title: "Tăng lương cơ sở lên 2,34 triệu đồng từ ngày 01/7/2024",
      summary: "Chi tiết các đối tượng được áp dụng mức lương cơ sở mới và cách tính các khoản phụ cấp đi kèm...",
      date: "2 giờ trước",
      category: "Lao động",
      isHot: false,
      mediaType: "video",
      color: "from-indigo-600 to-blue-800"
    },
    {
      id: 3,
      title: "Cảnh báo: Thủ đoạn lừa đảo giả danh công an gọi điện yêu cầu cài app VNeID",
      summary: "Công an các địa phương phát đi cảnh báo khẩn về tình trạng đối tượng giả danh công an yêu cầu người dân cài đặt ứng dụng giả mạo...",
      date: "4 giờ trước",
      category: "An ninh mạng",
      isHot: true,
      mediaType: "text",
      color: "from-amber-500 to-orange-700"
    },
    {
      id: 4,
      title: "Giảm 2% thuế GTGT (VAT) đến hết năm 2024 đối với nhiều mặt hàng",
      summary: "Quốc hội đồng ý kéo dài thời gian giảm thuế giá trị gia tăng để kích cầu tiêu dùng và hỗ trợ doanh nghiệp...",
      date: "Hôm qua",
      category: "Thuế",
      isHot: false,
      mediaType: "text",
      color: "from-emerald-500 to-teal-700"
    },
    {
      id: 5,
      title: "Quy định mới về cấp biển số xe định danh từ năm 2024",
      summary: "Biển số xe gắn liền với mã định danh cá nhân, người dân được phép giữ lại biển số khi bán xe...",
      date: "2 ngày trước",
      category: "Giao thông",
      isHot: false,
      mediaType: "text",
      color: "from-slate-700 to-slate-900"
    }
  ];

  return (
    <div className="min-h-screen bg-[#f8fafc] font-sans">
      {/* Glassmorphism Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-slate-200/80 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-slate-500 hover:text-slate-900 font-bold text-sm bg-slate-100 hover:bg-slate-200 px-4 py-2 rounded-full transition-all">
            <ArrowLeft size={16} weight="bold" /> Trang chủ
          </Link>
          <div className="flex flex-col items-center">
            <div className="font-black text-slate-900 flex items-center gap-2 text-lg">
              <Article size={22} className="text-brand" weight="fill" /> Tin tức & Cảnh báo
            </div>
          </div>
          <div className="w-[110px]"></div> {/* Spacer for symmetry */}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16">
        <div className="flex flex-col items-center text-center mb-16 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand/10 border border-brand/20 text-brand text-xs font-bold uppercase tracking-widest mb-6">
            <ShieldCheck size={16} weight="fill" /> Đã kiểm chứng pháp lý
          </div>
          <h1 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight mb-4">
            Cập nhật Pháp luật <br /> <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand to-red-800">Nhanh & Chính xác nhất</span>
          </h1>
          <p className="text-slate-500 font-medium max-w-2xl text-lg">
            Các tin tức, tóm tắt điểm mới và cảnh báo đều được tổng hợp tự động, đối chiếu nguyên văn với Cơ sở dữ liệu Quốc gia.
          </p>
        </div>

        {/* Bento Grid Gallery */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(180px,auto)]">
          {/* Featured Hero Card (Span 8) */}
          <Link to="/news/1" className="group md:col-span-8 row-span-2 relative bg-slate-900 rounded-[32px] overflow-hidden shadow-xl shadow-slate-900/10 border border-slate-200/50 flex flex-col justify-end p-8 sm:p-12 hover:shadow-2xl hover:shadow-brand/20 transition-all duration-500 hover:-translate-y-1">
            <div className="absolute inset-0 bg-gradient-to-br from-brand to-slate-900 opacity-90 group-hover:opacity-100 transition-opacity duration-500"></div>
            {/* Ambient glows */}
            <div className="absolute -top-32 -right-32 w-96 h-96 bg-brand blur-[128px] opacity-40 rounded-full"></div>
            
            <div className="relative z-10 flex flex-col h-full justify-between">
              <div className="flex justify-between items-start mb-16">
                <div className="flex gap-2">
                  <span className="bg-white/20 backdrop-blur-md text-white text-xs font-bold px-4 py-1.5 rounded-full uppercase tracking-wider border border-white/20">
                    Bất động sản
                  </span>
                  <span className="bg-red-500/20 text-red-100 text-xs font-bold px-4 py-1.5 rounded-full flex items-center gap-1.5 backdrop-blur-md border border-red-500/30">
                    <div className="w-1.5 h-1.5 bg-red-400 rounded-full animate-pulse"></div>
                    Nổi bật
                  </span>
                </div>
                <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-white/80 group-hover:bg-white group-hover:text-brand transition-colors">
                  <ArrowLeft size={24} className="rotate-135" weight="bold" />
                </div>
              </div>
              
              <div>
                <h2 className="text-3xl sm:text-4xl font-black text-white leading-tight mb-4 drop-shadow-lg">
                  Luật Đất đai (sửa đổi) chính thức thông qua: 5 điểm mới cực kỳ quan trọng
                </h2>
                <p className="text-slate-200 text-lg font-medium leading-relaxed max-w-3xl drop-shadow-md line-clamp-2">
                  Bỏ khung giá đất, cấp sổ đỏ cho đất không giấy tờ trước ngày 01/7/2014, quy định chặt chẽ hơn về thu hồi đất và bồi thường tái định cư...
                </p>
                <div className="mt-6 flex items-center gap-4 text-sm font-semibold text-slate-300">
                  <span className="flex items-center gap-1.5"><Clock size={16} /> Vừa xong</span>
                  <span className="flex items-center gap-1.5"><Scales size={16} /> Quốc hội ban hành</span>
                </div>
              </div>
            </div>
          </Link>

          {/* Secondary Card (Span 4) */}
          <Link to="/news/2" className="group md:col-span-4 row-span-1 bg-white rounded-[32px] p-6 sm:p-8 shadow-sm hover:shadow-xl border border-slate-200 transition-all duration-300 hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-50 rounded-bl-[100px] -z-0 transition-transform group-hover:scale-110"></div>
            <div className="relative z-10">
              <div className="flex justify-between items-start mb-6">
                <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-3 py-1 rounded-full border border-indigo-100 flex items-center gap-1.5">
                  <PlayCircle size={16} weight="fill" /> Video Tóm tắt
                </span>
              </div>
              <h3 className="text-xl font-bold text-slate-900 leading-snug mb-3 group-hover:text-brand transition-colors line-clamp-3">
                Tăng lương cơ sở lên 2,34 triệu đồng từ ngày 01/7/2024
              </h3>
            </div>
            <div className="relative z-10 flex items-center justify-between text-xs font-semibold text-slate-500 mt-4">
              <span>Lao động</span>
              <span className="flex items-center gap-1">Xem chi tiết <CaretRight size={14} weight="bold" /></span>
            </div>
          </Link>

          {/* Alert Card (Span 4) */}
          <Link to="/news/3" className="group md:col-span-4 row-span-1 bg-gradient-to-br from-amber-50 to-orange-50 rounded-[32px] p-6 sm:p-8 shadow-sm hover:shadow-xl border border-amber-200/60 transition-all duration-300 hover:-translate-y-1 relative overflow-hidden flex flex-col justify-between">
            <div className="absolute -bottom-4 -right-4 text-amber-500/10 group-hover:scale-110 transition-transform duration-500">
              <ShieldCheck size={120} weight="fill" />
            </div>
            <div className="relative z-10">
              <div className="flex justify-between items-start mb-4">
                <span className="bg-amber-100 text-amber-800 text-xs font-bold px-3 py-1 rounded-full border border-amber-200 flex items-center gap-1.5">
                  Cảnh báo rủi ro
                </span>
              </div>
              <h3 className="text-xl font-bold text-slate-900 leading-snug mb-3 line-clamp-3">
                Thủ đoạn lừa đảo giả danh công an yêu cầu cài app VNeID giả mạo
              </h3>
            </div>
            <div className="relative z-10 flex items-center justify-between text-xs font-semibold text-slate-500 mt-4">
              <span>An ninh mạng</span>
              <span className="flex items-center gap-1 text-amber-700">Đọc ngay <CaretRight size={14} weight="bold" /></span>
            </div>
          </Link>

          {/* Standard cards */}
          {newsItems.slice(3).map((item) => (
            <Link key={item.id} to={`/news/${item.id}`} className="group md:col-span-6 row-span-1 bg-white rounded-[32px] p-6 sm:p-8 shadow-sm hover:shadow-xl border border-slate-200 transition-all duration-300 hover:-translate-y-1 flex flex-col justify-between">
               <div className="flex justify-between items-start mb-6">
                <span className="bg-slate-100 text-slate-600 text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5">
                  <Tag size={14} weight="fill" /> {item.category}
                </span>
                <span className="text-xs font-medium text-slate-400">{item.date}</span>
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900 leading-snug mb-3 group-hover:text-brand transition-colors line-clamp-2">
                  {item.title}
                </h3>
                <p className="text-sm font-medium text-slate-500 line-clamp-2 leading-relaxed">
                  {item.summary}
                </p>
              </div>
              <div className="flex items-center gap-1 text-sm font-bold text-brand mt-6 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all">
                Đọc toàn văn <CaretRight size={16} weight="bold" />
              </div>
            </Link>
          ))}

        </div>
      </main>
    </div>
  );
}
