import { useState } from 'react';
import { UploadSimple, CheckCircle, Spinner, FlowArrow } from '@phosphor-icons/react';

export default function IngestPage() {
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [success, setSuccess] = useState(false);

  const handleUpload = () => {
    setIsUploading(true);
    let current = 0;
    const interval = setInterval(() => {
      current += 20;
      setProgress(current);
      if (current >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          setIsUploading(false);
          setSuccess(true);
        }, 500);
      }
    }, 500);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <header className="mb-6">
        <h2 className="text-2xl font-bold text-primary tracking-tight">Số hóa Văn bản</h2>
        <p className="text-muted font-medium mt-1">Bóc tách tự động & Xây dựng Đồ thị Tri thức</p>
      </header>

      {!success ? (
        <div className="bg-surface rounded-2xl p-10 shadow-soft text-center animate-fade-in-up">
          <div className="max-w-md mx-auto space-y-8">
            <div className="w-24 h-24 bg-gradient-info rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-md shadow-secondaryAccent/30">
              <UploadSimple size={48} className="text-white" weight="duotone" />
            </div>
            
            <div>
              <h3 className="text-xl font-bold text-primary">Tải lên văn bản Pháp luật</h3>
              <p className="text-sm font-medium text-muted mt-2">Hỗ trợ định dạng: .PDF, .DOCX, .TXT</p>
            </div>

            <div className="border-2 border-dashed border-secondaryAccent/50 rounded-2xl p-10 bg-background hover:bg-secondaryAccent/5 transition-colors cursor-pointer group">
              <p className="text-primary font-bold group-hover:text-secondaryAccent transition-colors">
                Kéo thả file vào đây hoặc <span className="text-secondaryAccent underline">Chọn file</span>
              </p>
            </div>

            <button 
              onClick={handleUpload}
              disabled={isUploading}
              className="w-full bg-gradient-accent text-white py-4 rounded-xl font-bold hover:shadow-lg transition-all disabled:opacity-70 flex items-center justify-center gap-2"
            >
              {isUploading ? (
                <>
                  <Spinner size={20} className="animate-spin" /> Đang bóc tách ({progress}%)...
                </>
              ) : (
                <>Bắt đầu Số hóa <FlowArrow weight="bold" /></>
              )}
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-surface rounded-2xl p-10 shadow-soft animate-fade-in-up">
          <div className="flex items-center gap-5 mb-8 pb-8 border-b border-border">
            <div className="w-16 h-16 bg-gradient-success rounded-2xl flex items-center justify-center shadow-md shadow-success/30">
              <CheckCircle size={36} className="text-white" weight="fill" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-primary">Số hóa thành công!</h3>
              <p className="font-medium text-muted mt-1">Đã bóc tách Luật Giao thông đường bộ 2026</p>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-6 mb-10">
            <div className="bg-background p-6 rounded-2xl shadow-inner border border-border/50">
              <p className="text-xs text-muted font-bold uppercase tracking-wider mb-2">Số điều khoản</p>
              <p className="text-3xl font-bold text-primary">142</p>
            </div>
            <div className="bg-background p-6 rounded-2xl shadow-inner border border-border/50">
              <p className="text-xs text-muted font-bold uppercase tracking-wider mb-2">Thực thể (Entities)</p>
              <p className="text-3xl font-bold text-accent">583</p>
            </div>
            <div className="bg-background p-6 rounded-2xl shadow-inner border border-border/50">
              <p className="text-xs text-muted font-bold uppercase tracking-wider mb-2">Mối quan hệ (Edges)</p>
              <p className="text-3xl font-bold text-secondaryAccent">1,205</p>
            </div>
          </div>

          <div className="flex justify-end gap-4">
            <button onClick={() => setSuccess(false)} className="px-6 py-3.5 rounded-xl font-bold text-primary bg-background border border-border hover:bg-surface hover:shadow-soft transition-all">
              Số hóa file khác
            </button>
            <button className="px-6 py-3.5 rounded-xl font-bold text-white bg-gradient-info hover:shadow-lg shadow-secondaryAccent/30 transition-all">
              Xem trên Đồ thị Graph
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
