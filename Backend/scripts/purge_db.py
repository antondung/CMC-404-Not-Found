"""Purge the knowledge stores so you can reload clean data.

Clears data across ALL stores in one shot: Neo4j (graph), Qdrant (vectors), PostgreSQL
(jobs/files/lineage/content) and MinIO (raw files). It NEVER touches the `users` and
`system_config` tables, so you stay logged in after a purge.

SCOPES
  legal   (default)  Legal knowledge only: VanBanPhapLuat/Dieu/Khoan + NER entities,
                     the `khoan` vector collection, van_ban_files/lineage/legal jobs,
                     and the MinIO legal bucket.
  social             Social-listening data: BaiDang/YKien/AlertMeta/ChuDe, the
                     baidang/chude vector collections, alerts/suggestions + social jobs.
  all                Everything above + briefs + audit_log + every job (keeps users).

USAGE (from repo root, backend interpreter):
    python Backend/scripts/purge_db.py                 # legal, asks for confirmation
    python Backend/scripts/purge_db.py --scope all --yes
    python Backend/scripts/purge_db.py --scope legal --dry-run

Connection settings are read from Backend/.env (same as the app). Real env vars win.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# --------------------------------------------------------------------------------------
# .env loading (Backend/.env). Minimal parser so the script has no extra dependency.
# --------------------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _load_env() -> None:
    if not _ENV_PATH.exists():
        return
    for raw in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val


# What each scope clears.
_NEO4J_LABELS = {
    "legal": ["VanBanPhapLuat", "Dieu", "Khoan", "ChuThe", "NghiaVu", "QuyenLoi", "HanhViCam", "ThoiHan", "CheTai"],
    "social": ["BaiDang", "YKien", "AlertMeta", "ChuDe"],
}
_QDRANT_COLLECTIONS = {
    "legal": ["khoan"],
    "social": ["baidang", "chude"],
}


def _labels_for(scope: str) -> list[str]:
    if scope == "all":
        return _NEO4J_LABELS["legal"] + _NEO4J_LABELS["social"]
    return _NEO4J_LABELS.get(scope, [])


def _collections_for(scope: str) -> list[str]:
    if scope == "all":
        return _QDRANT_COLLECTIONS["legal"] + _QDRANT_COLLECTIONS["social"]
    return _QDRANT_COLLECTIONS.get(scope, [])


# --------------------------------------------------------------------------------------
# Neo4j
# --------------------------------------------------------------------------------------
async def purge_neo4j(scope: str, dry_run: bool) -> None:
    labels = _labels_for(scope)
    if not labels:
        return
    try:
        from neo4j import AsyncGraphDatabase
    except Exception:
        print("  [neo4j] SKIP - thiếu 'neo4j' package")
        return
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "neo4j")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, pwd))
    try:
        async with driver.session() as session:
            for label in labels:
                cnt_res = await session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c")
                rec = await cnt_res.single()
                total = int(rec["c"]) if rec else 0
                if dry_run:
                    print(f"  [neo4j] {label}: {total} node(s) -> would delete")
                    continue
                # Delete in batches to avoid a huge single transaction.
                deleted = 0
                while True:
                    res = await session.run(
                        f"MATCH (n:`{label}`) WITH n LIMIT 5000 DETACH DELETE n RETURN count(n) AS c"
                    )
                    r = await res.single()
                    n = int(r["c"]) if r else 0
                    deleted += n
                    if n == 0:
                        break
                print(f"  [neo4j] {label}: deleted {deleted} node(s)")
    finally:
        await driver.close()


# --------------------------------------------------------------------------------------
# Qdrant
# --------------------------------------------------------------------------------------
async def purge_qdrant(scope: str, dry_run: bool) -> None:
    collections = _collections_for(scope)
    if not collections:
        return
    try:
        from qdrant_client import AsyncQdrantClient, models
    except Exception:
        print("  [qdrant] SKIP - thiếu 'qdrant-client' package")
        return
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = AsyncQdrantClient(url=url)
    try:
        for col in collections:
            try:
                info = await client.get_collection(col)
                count = getattr(info, "points_count", None)
            except Exception:
                print(f"  [qdrant] {col}: không tồn tại - bỏ qua")
                continue
            if dry_run:
                print(f"  [qdrant] {col}: {count} point(s) -> would delete all points")
                continue
            # Delete every point but keep the collection (preserves vector size/distance config).
            await client.delete(
                collection_name=col,
                points_selector=models.FilterSelector(filter=models.Filter(must=[])),
            )
            print(f"  [qdrant] {col}: cleared all points")
    finally:
        await client.close()


# --------------------------------------------------------------------------------------
# PostgreSQL
# --------------------------------------------------------------------------------------
_PG_STATEMENTS = {
    "legal": [
        "DELETE FROM van_ban_files",
        "DELETE FROM lineage",
        "DELETE FROM jobs WHERE type ILIKE ANY (ARRAY['%legal%','parse','extract','diff'])",
    ],
    "social": [
        "DELETE FROM alerts",
        "DELETE FROM suggestions",
        "DELETE FROM jobs WHERE type ILIKE '%social%'",
    ],
    "all": [
        "TRUNCATE van_ban_files, lineage, job_events, jobs, briefs, suggestions, alerts, audit_log RESTART IDENTITY CASCADE",
    ],
}


async def purge_postgres(scope: str, dry_run: bool) -> None:
    statements = _PG_STATEMENTS.get(scope, [])
    if not statements:
        return
    try:
        import asyncpg
    except Exception:
        print("  [postgres] SKIP - thiếu 'asyncpg' package")
        return
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("  [postgres] SKIP - thiếu DATABASE_URL")
        return
    # asyncpg wants postgresql:// (not postgresql+asyncpg://)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        for stmt in statements:
            if dry_run:
                print(f"  [postgres] would run: {stmt}")
                continue
            status = await conn.execute(stmt)
            print(f"  [postgres] {stmt.split(' WHERE')[0][:48]}... -> {status}")
    finally:
        await conn.close()


# --------------------------------------------------------------------------------------
# MinIO
# --------------------------------------------------------------------------------------
async def purge_minio(scope: str, dry_run: bool) -> None:
    if scope not in ("legal", "all"):
        return
    try:
        from minio import Minio
        from minio.deleteobjects import DeleteObject
    except Exception:
        print("  [minio] SKIP - thiếu 'minio' package")
        return
    endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    parsed = urlparse(endpoint)
    secure = parsed.scheme == "https"
    host = parsed.netloc or parsed.path
    bucket = os.getenv("MINIO_BUCKET_LEGAL", "legal-raw")
    client = Minio(
        host,
        access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        secure=secure,
    )

    def _run() -> str:
        if not client.bucket_exists(bucket):
            return f"bucket '{bucket}' không tồn tại - bỏ qua"
        objects = list(client.list_objects(bucket, recursive=True))
        if dry_run:
            return f"bucket '{bucket}': {len(objects)} object(s) -> would delete"
        if not objects:
            return f"bucket '{bucket}': trống"
        errors = list(
            client.remove_objects(bucket, (DeleteObject(o.object_name) for o in objects))
        )
        for e in errors:
            print(f"    [minio] lỗi xóa {e.object_name}: {e}")
        return f"bucket '{bucket}': deleted {len(objects)} object(s)"

    msg = await asyncio.to_thread(_run)
    print(f"  [minio] {msg}")


async def main_async(scope: str, dry_run: bool) -> int:
    print(f"\n=== PURGE scope='{scope}'{' (DRY RUN)' if dry_run else ''} ===")
    print("[1/4] Neo4j");    await purge_neo4j(scope, dry_run)
    print("[2/4] Qdrant");   await purge_qdrant(scope, dry_run)
    print("[3/4] Postgres"); await purge_postgres(scope, dry_run)
    print("[4/4] MinIO");    await purge_minio(scope, dry_run)
    print("\nHoàn tất." + ("" if dry_run else " users/system_config được giữ nguyên."))
    return 0


def main() -> int:
    _load_env()
    ap = argparse.ArgumentParser(description="Purge knowledge stores (Neo4j/Qdrant/Postgres/MinIO).")
    ap.add_argument("--scope", choices=["legal", "social", "all"], default="legal")
    ap.add_argument("--yes", action="store_true", help="Bỏ qua xác nhận")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không xóa")
    args = ap.parse_args()

    if not args.dry_run and not args.yes:
        print(f"Sắp XÓA dữ liệu scope='{args.scope}' khỏi Neo4j/Qdrant/Postgres/MinIO.")
        print("users & system_config sẽ được giữ. Hành động KHÔNG THỂ hoàn tác.")
        if input(f"Gõ '{args.scope}' để xác nhận: ").strip() != args.scope:
            print("Đã hủy.")
            return 1

    try:
        return asyncio.run(main_async(args.scope, args.dry_run))
    except KeyboardInterrupt:
        print("\nĐã dừng.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
