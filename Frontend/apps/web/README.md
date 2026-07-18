# LexSocial AI — Frontend (`apps/web`)

Một Vite app phục vụ **hai phân hệ** trên cùng origin:

| Path | Phân hệ |
|------|---------|
| `/`, `/ask`, `/news`, `/van-ban` | Citizen (công khai) |
| `/admin/*` | Admin (RBAC, đăng nhập) |

## Dev

```bash
cd Frontend
npm install
npm run dev          # → http://localhost:5173
```

Hoặc từ root repo: `./run.ps1 -Frontend`

- Citizen: http://localhost:5173/
- Admin: http://localhost:5173/admin/ — seed `admin@local` / `admin123`

## Build / Railway

```bash
npm run build        # → apps/web/dist
```

- **Root Directory** trên Railway = `Frontend`
- **Node.js ≥ 22** (Vite 8 / Rolldown)
- **Không** đặt Build Command = `npm ci && …` (Railpack đã install)
- Biến bắt buộc: `VITE_API_URL=https://<backend-public>.up.railway.app`
- Chi tiết: `Frontend/nixpacks.toml`, `Frontend/SYSTEM_FRONTEND.md`

## Cấu trúc

```
src/
  app/App.tsx           # routes / + /admin/*
  lib/                  # api, apiBase, base
  admin/features/…      # dashboard, alerts, graph, …
  citizen/features/…    # home, ask, news, van-ban
packages/ui-legal/      # CitationCard, RiskBadge, …
```
