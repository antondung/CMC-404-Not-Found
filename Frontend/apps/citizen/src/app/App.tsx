import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from '../features/home/HomePage';
import AskPage from '../features/ask/AskPage';
import VanBanPage from '../features/van-ban/VanBanPage';

export default function App() {
  return (
    <BrowserRouter basename="/citizen">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/van-ban" element={<VanBanPage />} />
      </Routes>
    </BrowserRouter>
  );
}
