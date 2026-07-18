# Integration Notes — trạng thái ghép Backend ↔ Frontend ↔ Database

> Người ghi: DB / Data Platform. Cập nhật: **2026-07-18**.
> Mục đích: nêu rõ chỗ đã khớp và chỗ lệch giữa 3 phần.
> Quyết định contract: `TEAM_ASSIGNMENT.md` §3, `SYSTEM_DATA.md` §10.

---

## 0. Trạng thái hiện tại (2026-07-18)

| Hạng mục | Trạng thái |
|---|---|
| **FE** | ✅ Một app `Frontend/apps/web` — Citizen `/`, Admin `/admin/*`, cổng **5173**. Client API: `src/lib/api.ts` + `VITE_API_URL`. |
| **BE** | ✅ FastAPI :8000 + BE2 gateway :8002; pytest harness; OpenAI-compatible LLM/embedding (dim **1536**). |
| **DB** | ✅ Schema/seed/gold; Qdrant collections dim **1536**; seed/purge Railway (`load_seed_railway.py`, `purge_db_railway.py`). |
| **Deploy** | ✅ Railway: FE Root=`Frontend`, Node **22**, Build=`npm run build` (không `npm ci` trong build). Backend private DB URLs. |

Chạy local: `./run.ps1` · FE: `cd Frontend && npm run dev` · test: `cd Backend && pytest -vv`.

---

## 0b. Lịch sử 2026-07-17 (đợt rà soát P0/P1 — giữ để truy vết)

Đã sửa các lỗi chặn (P0) và nghiêm trọng (P1) từ báo cáo rà soát:

**Backend P0**
- ✅ **Bypass xác thực (L1)**: `role_checker` thiếu `Depends(get_current_user)` → đã thêm.
- ✅ **RAG / cheat / test**: đã harden; pytest chạy qua `tests/conftest.py` fakes.
- ✅ Embedding production: **OpenAI-compatible `text-embedding-3-small` (1536)** — không còn mặc định bge-m3/1024.

**Frontend**
- ✅ Gộp admin+citizen → `apps/web`; build `npm run build -w web` OK.
- ✅ Wire API thật qua `VITE_API_URL` / `public/config.js`.

---

## 1. Ma trận kết nối (cập nhật 2026-07-18)

| Cặp | Trạng thái | Ghi chú |
|---|---|---|
| DB ↔ BE — env/connection | ✅ Khớp | `DATABASE_URL`, `NEO4J_*`, `QDRANT_URL`, `REDIS_URL`. |
| DB ↔ BE — Neo4j / Postgres | ✅ Khớp | Schema + adapters đã align (xem lịch sử §2–3 bên dưới nếu cần). |
| DB ↔ BE — Qdrant | ✅ Khớp | `khoan` / `baidang` / `chude`, dim **1536**, Cosine. |
| BE ↔ FE | ✅ Nối | FE gọi BE3 envelope; CORS/`CORS_ALLOW_ALL` cho Railway. |
| Chạy chung | ✅ | `run.ps1` / Railway services. |

---

## 2–3. Postgres / Neo4j lệch lịch sử (đã xử lý 2026-07-17)

Chi tiết adapter cũ (`payload_json`, key `AlertMeta`) đã được sửa. Giữ phần dưới chỉ để audit trail — **không còn blocker**.

<details>
<summary>Chi tiết lịch sử (click để mở)</summary>

### Postgres (đã fix)
Adapter `briefs` / `suggestions` / `alerts` map đúng cột schema `003_content_publish.sql`.

### Neo4j keys (đã fix)
`AlertMeta {uuid}`, `YKien {uuid}` khớp constraints.

</details>

---

## 4. Frontend (cập nhật)

- App: `Frontend/apps/web` (không còn `apps/admin` / `apps/citizen` tách cổng).
- API: `src/lib/api.ts` — Bearer cho admin; citizen public.
- Dev: http://localhost:5173/ và http://localhost:5173/admin/
- Railway: xem `Frontend/nixpacks.toml` + `README.md` checklist.

---

## 5. Cách chạy 3 phần chung

1. **DB**: `docker compose -f Data/docker-compose.data.yml --env-file Data/.env up -d` → `Data/seed/load_seed.ps1` (hoặc Railway seed).
2. **Backend**: `./run.ps1 -Backend` (hoặc uvicorn :8000 + :8002).
3. **Frontend**: `./run.ps1 -Frontend` hoặc `cd Frontend && npm run dev`.

Thứ tự: **DB → BE → FE**.

---

## 6. Checklist nối thật

- [x] BE adapters khớp schema DB
- [x] FE một app + API client
- [x] Qdrant dim 1536
- [x] Seed/purge Railway
- [ ] E2E production: ingest → QA → FE trên Railway với `VITE_API_URL` + private DB

---

## 7. Backend boot

`uvicorn app.main:app --port 8000` và `uvicorn be2_service:app --port 8002` — OK khi env kết nối DB đúng.
