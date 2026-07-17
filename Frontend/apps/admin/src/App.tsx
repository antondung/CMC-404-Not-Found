import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ShieldCheck, SquaresFour, Bell, ListMagnifyingGlass, FileText, ShareNetwork } from '@phosphor-icons/react';
import DashboardPage from './pages/Dashboard';
import AlertsPage from './pages/Alerts';
import QAAdminPage from './pages/QAAdmin';
import IngestPage from './pages/Ingest';
import LoginPage from './pages/Login';

function Sidebar() {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  const navItemClass = (path: string) => `
    flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-semibold text-sm mb-1.5
    ${isActive(path) 
      ? 'bg-surface shadow-soft text-primary' 
      : 'text-muted hover:bg-surface/50 hover:text-primary'}
  `;

  const iconWrapperClass = (path: string) => `
    w-8 h-8 rounded-lg flex items-center justify-center shadow-sm
    ${isActive(path) ? 'bg-gradient-accent text-white' : 'bg-surface text-primary shadow-soft'}
  `;

  return (
    <aside className="w-[250px] h-[calc(100vh-2rem)] bg-background/50 backdrop-blur-xl border-r border-transparent fixed left-4 top-4 flex flex-col z-50">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 bg-gradient-dark rounded-lg flex items-center justify-center text-white shadow-soft">
          <ShieldCheck size={20} weight="fill" />
        </div>
        <span className="text-primary font-bold tracking-tight">LexSocial AI</span>
      </div>

      <div className="flex-1 px-4 overflow-y-auto mt-4 space-y-1">
        <Link to="/" className={navItemClass('/')}>
          <div className={iconWrapperClass('/')}><SquaresFour size={16} weight="fill" /></div>
          Tổng quan
        </Link>
        <Link to="/alerts" className={navItemClass('/alerts')}>
          <div className={iconWrapperClass('/alerts')}><Bell size={16} weight="fill" /></div>
          Cảnh báo rủi ro
        </Link>
        <Link to="/qa" className={navItemClass('/qa')}>
          <div className={iconWrapperClass('/qa')}><ListMagnifyingGlass size={16} weight="fill" /></div>
          Hỏi đáp Pháp lý
        </Link>
        
        <div className="pt-6 pb-2">
          <p className="px-4 text-xs font-bold text-muted uppercase tracking-wider">Quản trị Dữ liệu</p>
        </div>
        <Link to="/van-ban" className={navItemClass('/van-ban')}>
          <div className={iconWrapperClass('/van-ban')}><FileText size={16} weight="fill" /></div>
          Số hóa văn bản
        </Link>
        <Link to="/graph" className={navItemClass('/graph')}>
          <div className={iconWrapperClass('/graph')}><ShareNetwork size={16} weight="fill" /></div>
          Đồ thị Tri thức
        </Link>
      </div>
    </aside>
  );
}

function AppContent() {
  return (
    <div className="min-h-screen bg-background font-sans text-primary relative">
      <Sidebar />
      <main className="ml-[280px] p-8 min-h-screen">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/qa" element={<QAAdminPage />} />
          <Route path="/van-ban" element={<IngestPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  if (!isAuthenticated) {
    return <LoginPage onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;
