import { ArrowLeft, BookOpen, Clock, FilePdf, DownloadSimple, ShieldCheck, TreeStructure, BookmarkSimple } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';

export default function VanBanPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Header (Slim version for document viewer) */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-slate-500 hover:text-brand font-semibold text-sm transition-colors">
            <ArrowLeft size={16} weight="bold" /> Quay lại Trang chủ
          </Link>
          <div className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <BookOpen size={18} className="text-brand" weight="fill" />
            Tra cứu Văn bản
          </div>
          <div className="w-24"></div> {/* Spacer for centering */}
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-8">
        
        {/* Left Sidebar: TOC (SimpleVanBanTree) */}
        <aside className="w-full md:w-1/3 lg:w-1/4 shrink-0">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 sticky top-20 shadow-[0_2px_10px_rgb(0,0,0,0.02)]">
            <h3 className="font-bold text-slate-900 flex items-center gap-2 mb-4 pb-4 border-b border-slate-100">
              <TreeStructure size={20} className="text-brand" /> Cấu trúc văn bản
            </h3>
            
            <nav className="space-y-1">
              <div className="py-2 px-3 bg-brand/5 text-brand rounded-lg font-semibold text-sm cursor-pointer border border-brand/10">
                Chương I: Quy định chung
              </div>
              <div className="py-2 px-3 pl-6 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium cursor-pointer transition-colors">
                Điều 1. Phạm vi điều chỉnh
              </div>
              <div className="py-2 px-3 pl-6 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium cursor-pointer transition-colors">
                Điều 2. Đối tượng áp dụng
              </div>
              
              <div className="py-2 px-3 text-slate-700 hover:bg-slate-50 rounded-lg font-semibold text-sm cursor-pointer transition-colors mt-2">
                Chương II: Hành vi vi phạm
              </div>
              <div className="py-2 px-3 pl-6 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium cursor-pointer transition-colors">
                Điều 5. Xử phạt người điều khiển xe ô tô
              </div>
              <div className="py-2 px-3 pl-6 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium cursor-pointer transition-colors">
                Điều 6. Xử phạt người điều khiển xe máy
              </div>
            </nav>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 max-w-3xl">
          {/* Document Meta (Tên + Số hiệu + Tóm tắt) */}
          <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm mb-6">
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <span className="inline-flex items-center px-3 py-1 bg-red-50 text-brand text-xs font-bold rounded-lg uppercase tracking-wider border border-red-100">
                100/2019/NĐ-CP
              </span>
              <span className="inline-flex items-center px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-lg uppercase tracking-wider border border-emerald-100">
                <ShieldCheck size={14} className="mr-1" /> Còn hiệu lực
              </span>
            </div>
            
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-tight mb-4">
              Nghị định quy định xử phạt vi phạm hành chính trong lĩnh vực giao thông đường bộ và đường sắt
            </h1>
            
            <div className="flex flex-wrap gap-6 text-sm text-slate-500 font-medium mb-6 pb-6 border-b border-slate-100">
              <div className="flex items-center gap-1.5"><Clock size={16} /> Ban hành: 30/12/2019</div>
              <div className="flex items-center gap-1.5"><BookmarkSimple size={16} /> Cơ quan ban hành: Chính phủ</div>
            </div>
            
            <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
              <h4 className="font-bold text-slate-800 mb-2">Tóm tắt văn bản</h4>
              <p className="text-slate-600 leading-relaxed text-sm">
                Nghị định này quy định về hành vi vi phạm hành chính; hình thức, mức xử phạt, biện pháp khắc phục hậu quả đối với từng hành vi vi phạm hành chính; thẩm quyền lập biên bản, thẩm quyền xử phạt, mức phạt tiền cụ thể theo từng chức danh đối với hành vi vi phạm hành chính trong lĩnh vực giao thông đường bộ và đường sắt. Nổi bật là các quy định nghiêm ngặt về nồng độ cồn.
              </p>
            </div>
          </div>

          {/* Document Body View */}
          <div className="bg-white rounded-3xl p-8 sm:p-10 border border-slate-200 shadow-[0_8px_30px_rgb(0,0,0,0.02)] relative">
            <div className="absolute top-0 right-10 w-20 h-32 bg-brand/5 blur-3xl rounded-full pointer-events-none"></div>
            
            <article className="prose prose-slate max-w-none prose-headings:font-bold prose-headings:text-slate-900 prose-p:text-slate-700 prose-p:leading-loose">
              <h2 className="text-center text-xl border-b border-slate-200 pb-4 mb-8 uppercase tracking-wide">
                Chương I <br />
                <span className="text-lg text-slate-500 mt-2 block">Quy định chung</span>
              </h2>
              
              <h3 className="text-lg">Điều 1. Phạm vi điều chỉnh</h3>
              <p>
                1. Nghị định này quy định về hành vi vi phạm hành chính; hình thức, mức xử phạt, biện pháp khắc phục hậu quả đối với từng hành vi vi phạm hành chính; thẩm quyền lập biên bản, thẩm quyền xử phạt, mức phạt tiền cụ thể theo từng chức danh đối với hành vi vi phạm hành chính trong lĩnh vực giao thông đường bộ và đường sắt.
              </p>
              
              <h3 className="text-lg mt-8">Điều 2. Đối tượng áp dụng</h3>
              <p>
                1. Cá nhân, tổ chức có hành vi vi phạm hành chính trong lĩnh vực giao thông đường bộ, đường sắt trên lãnh thổ nước Cộng hòa xã hội chủ nghĩa Việt Nam.
              </p>
              <p>
                2. Người có thẩm quyền xử phạt vi phạm hành chính.
              </p>

              <hr className="my-10 border-slate-200 border-dashed" />

              <h2 className="text-center text-xl border-b border-slate-200 pb-4 mb-8 uppercase tracking-wide">
                Chương II <br />
                <span className="text-lg text-slate-500 mt-2 block">Hành vi vi phạm, hình thức và mức xử phạt</span>
              </h2>
              
              <h3 className="text-lg text-brand">Điều 6. Xử phạt người điều khiển xe mô tô, xe gắn máy</h3>
              <p className="font-medium bg-brand/5 p-4 rounded-lg border-l-4 border-brand">
                Phạt tiền từ 2.000.000 đồng đến 3.000.000 đồng đối với người điều khiển xe trên đường mà trong máu hoặc hơi thở có nồng độ cồn nhưng chưa vượt quá 50 miligam/100 mililít máu hoặc chưa vượt quá 0,25 miligam/1 lít khí thở.
              </p>
              
            </article>
          </div>
        </div>

        {/* Right Sidebar: FileAttachList */}
        <aside className="w-full md:w-1/4 shrink-0">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 sticky top-20 shadow-sm">
            <h3 className="font-bold text-slate-900 mb-4">Tải về máy</h3>
            <div className="space-y-3">
              <a href="#" className="flex items-center gap-3 p-3 rounded-xl border border-slate-100 hover:border-brand/30 hover:bg-brand/5 transition-all group">
                <div className="w-10 h-10 rounded-lg bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                  <FilePdf size={24} weight="fill" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-slate-800 group-hover:text-brand transition-colors">Bản gốc (PDF)</div>
                  <div className="text-xs text-slate-500">2.4 MB</div>
                </div>
                <DownloadSimple size={18} className="text-slate-400 group-hover:text-brand transition-colors" />
              </a>
              
              <a href="#" className="flex items-center gap-3 p-3 rounded-xl border border-slate-100 hover:border-blue-500/30 hover:bg-blue-50 transition-all group">
                <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <FilePdf size={24} weight="fill" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-bold text-slate-800 group-hover:text-blue-600 transition-colors">Bản Sửa đổi (PDF)</div>
                  <div className="text-xs text-slate-500">1.1 MB</div>
                </div>
                <DownloadSimple size={18} className="text-slate-400 group-hover:text-blue-600 transition-colors" />
              </a>
            </div>
          </div>
        </aside>

      </main>
    </div>
  );
}
