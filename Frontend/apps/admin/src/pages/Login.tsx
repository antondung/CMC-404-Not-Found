import React, { useState } from 'react';
import { ShieldCheck, Eye, EyeSlash, ArrowRight, Spinner } from '@phosphor-icons/react';

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      onLogin();
    }, 1200);
  };

  return (
    <div className="min-h-screen flex bg-background relative overflow-hidden">
      {/* Background Shapes for Soft UI Aesthetic */}
      <div className="absolute top-0 left-0 w-full h-1/2 bg-gradient-info skew-y-6 -translate-y-20 transform-gpu z-0 rounded-b-[80px]"></div>

      <div className="relative z-10 flex w-full max-w-6xl mx-auto items-center justify-center min-h-screen p-6 gap-12">
        {/* Left Side: Soft UI Branding Card */}
        <div className="hidden lg:flex flex-col w-1/2 animate-fade-in-up">
          <h1 className="text-white text-5xl font-bold tracking-tight leading-tight mb-4 drop-shadow-md">
            LexSocial AI
          </h1>
          <p className="text-white/80 text-lg mb-8 font-medium">
            Hệ thống Trung tâm Chỉ huy số hóa văn bản & giám sát thông tin đa nền tảng.
          </p>
        </div>

        {/* Right Side: Login Card */}
        <div className="w-full lg:w-5/12 bg-surface p-10 rounded-[30px] shadow-card animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-primary mb-2">Đăng nhập</h2>
            <p className="text-muted font-medium">Truy cập vào hệ thống quản trị</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-bold text-primary ml-1">Tài khoản Cán bộ</label>
              <input 
                type="text" 
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Tên đăng nhập"
                className="w-full px-5 py-3.5 bg-background border border-border rounded-xl text-primary font-medium focus:outline-none focus:ring-2 focus:ring-secondaryAccent/30 focus:border-secondaryAccent transition-all"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-bold text-primary ml-1">Mật khẩu</label>
              <div className="relative">
                <input 
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-5 py-3.5 bg-background border border-border rounded-xl text-primary font-medium focus:outline-none focus:ring-2 focus:ring-secondaryAccent/30 focus:border-secondaryAccent transition-all pr-12"
                />
                <button 
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-muted hover:text-primary transition-colors"
                >
                  {showPassword ? <EyeSlash size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                <input type="checkbox" id="remember" className="w-4 h-4 rounded text-secondaryAccent focus:ring-secondaryAccent border-border cursor-pointer" />
                <label htmlFor="remember" className="text-sm font-medium text-muted cursor-pointer">Ghi nhớ</label>
              </div>
              <a href="#" className="text-sm font-bold text-secondaryAccent hover:text-blue-700 transition-colors">Quên mật khẩu?</a>
            </div>

            <button 
              type="submit" 
              disabled={isLoading || !email || !password}
              className="w-full bg-gradient-info text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 hover:shadow-lg focus:ring-4 focus:ring-secondaryAccent/20 transition-all disabled:opacity-70 disabled:cursor-not-allowed mt-4 group"
            >
              {isLoading ? (
                <><Spinner size={20} className="animate-spin" /> Đang xác thực...</>
              ) : (
                <>Đăng nhập <ArrowRight size={20} weight="bold" className="group-hover:translate-x-1 transition-transform" /></>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
