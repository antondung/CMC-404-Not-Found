"""Purge knowledge stores on Railway via public TCP proxies.

Does NOT load Backend/.env (avoids localhost / wrong Neo4j password).

Env (same as Data/seed/load_seed_railway.py):
  DATABASE_PUBLIC_URL   required  postgresql://...@*.proxy.rlwy.net:.../railway
  NEO4J_PASSWORD        required
  NEO4J_BOLT_HOST       default tokaido.proxy.rlwy.net
  NEO4J_BOLT_PORT       default 20113
  NEO4J_USER            default neo4j
  QDRANT_URL            default http://tokaido.proxy.rlwy.net:30541
  REDIS_URL             optional (needed for --redis / --scope all)
  EMBEDDING_DIM         default 1536
  PURGE_MINIO=1         optional — only if MinIO endpoint is reachable from laptop

Usage (from repo root, after setting env vars):
  python Backend/scripts/purge_db_railway.py --scope legal --yes
  python Backend/scripts/purge_db_railway.py --scope all --yes --redis
  python Backend/scripts/purge_db_railway.py --scope legal --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Import purge helpers without running its main / loading Backend/.env
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import purge_db as _purge  # noqa: E402


def _require(name: str) -> str:
    val = (os.environ.get(name) or "").strip()
    if not val:
        raise SystemExit(f"Set {name} first (Railway public proxy).")
    return val


def _apply_railway_env() -> None:
    pg = _require("DATABASE_PUBLIC_URL")
    if pg.startswith("postgres://"):
        pg = "postgresql://" + pg[len("postgres://") :]
    os.environ["DATABASE_URL"] = pg
    os.environ["DATABASE_SSL"] = os.environ.get("DATABASE_SSL") or "require"

    host = os.environ.get("NEO4J_BOLT_HOST", "tokaido.proxy.rlwy.net").strip()
    port = os.environ.get("NEO4J_BOLT_PORT", "20113").strip()
    os.environ["NEO4J_URI"] = f"bolt://{host}:{port}"
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ["NEO4J_PASSWORD"] = _require("NEO4J_PASSWORD")

    os.environ.setdefault("QDRANT_URL", "http://tokaido.proxy.rlwy.net:30541")
    dim = os.environ.get("EMBEDDING_DIM") or os.environ.get("BE2_EMBEDDING_DIMENSION") or "1536"
    os.environ.setdefault("BE2_EMBEDDING_DIMENSION", dim)
    os.environ.setdefault("EMBEDDING_DIM", dim)

    redis = (os.environ.get("REDIS_URL") or os.environ.get("REDIS_PUBLIC_URL") or "").strip()
    if redis:
        os.environ["REDIS_URL"] = redis
        os.environ["BE2_REDIS_URL"] = redis

    # Avoid accidental localhost MinIO wipe unless explicitly enabled.
    if os.environ.get("PURGE_MINIO", "").strip().lower() not in {"1", "true", "yes"}:
        os.environ["MINIO_ENDPOINT"] = ""


async def _purge_minio_guarded(scope: str, dry_run: bool) -> None:
    if not (os.environ.get("MINIO_ENDPOINT") or "").strip():
        print("  [minio] skipped (set PURGE_MINIO=1 + MINIO_ENDPOINT for Railway MinIO)")
        return
    await _purge.purge_minio(scope, dry_run)


async def main_async(scope: str, dry_run: bool, do_redis: bool) -> int:
    print(f"\n=== PURGE RAILWAY scope='{scope}'{' (DRY RUN)' if dry_run else ''} ===")
    print(f"  Neo4j  {os.environ.get('NEO4J_URI')}")
    print(f"  Qdrant {os.environ.get('QDRANT_URL')}")
    print(f"  PG     {os.environ.get('DATABASE_URL', '')[:48]}…")
    print("[1/5] Neo4j")
    await _purge.purge_neo4j(scope, dry_run)
    print("[2/5] Qdrant")
    await _purge.purge_qdrant(scope, dry_run)
    print("[3/5] Postgres")
    await _purge.purge_postgres(scope, dry_run)
    print("[4/5] MinIO")
    await _purge_minio_guarded(scope, dry_run)
    print("[5/5] Redis")
    if do_redis or scope == "all":
        if not (os.environ.get("REDIS_URL") or os.environ.get("BE2_REDIS_URL")):
            print("  [redis] SKIP - set REDIS_URL / REDIS_PUBLIC_URL")
        else:
            await _purge.purge_redis(dry_run)
    else:
        print("  [redis] skipped (pass --redis or --scope all)")
    print("\nHoàn tất." + ("" if dry_run else " users/system_config được giữ nguyên."))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Purge Railway stores via public TCP proxy.")
    ap.add_argument("--scope", choices=["legal", "social", "content", "all"], default="legal")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--redis", action="store_true")
    args = ap.parse_args()

    _apply_railway_env()

    if not args.dry_run and not args.yes:
        print(f"Sắp XÓA dữ liệu Railway scope='{args.scope}' (Neo4j/Qdrant/Postgres).")
        print("users & system_config sẽ được giữ. Hành động KHÔNG THỂ hoàn tác.")
        if input(f"Gõ '{args.scope}' để xác nhận: ").strip() != args.scope:
            print("Đã hủy.")
            return 1

    try:
        return asyncio.run(main_async(args.scope, args.dry_run, args.redis))
    except KeyboardInterrupt:
        print("\nĐã dừng.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
