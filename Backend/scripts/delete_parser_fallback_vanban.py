"""Xóa văn bản parser-fallback (1 Điều «Nội dung văn bản» / 1 Khoản) trên Neo4j (+ Qdrant/PG).

Khi parser không tách được Điều, nó lưu cả file vào Điều 1/Khoản 1 với
``tieu_de = "Nội dung văn bản"``. Script này tìm và xóa đúng nhóm đó.

Railway (public proxy) — set env rồi chạy từ repo root:

  $env:DATABASE_PUBLIC_URL = "postgresql://..."
  $env:DATABASE_SSL = "require"
  $env:NEO4J_BOLT_HOST = "....proxy.rlwy.net"
  $env:NEO4J_BOLT_PORT = "20113"
  $env:NEO4J_PASSWORD = "..."
  $env:QDRANT_URL = "http://....proxy.rlwy.net:...."

  # Chỉ liệt kê
  python Backend/scripts/delete_parser_fallback_vanban.py --railway --dry-run

  # Xóa thật
  python Backend/scripts/delete_parser_fallback_vanban.py --railway --yes

  # Xóa một số hiệu cụ thể (vd. từ log import)
  python Backend/scripts/delete_parser_fallback_vanban.py --railway --yes --so-hieu "4919/BCT-XNK"

Local (dùng Backend/.env): bỏ ``--railway``.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

FALLBACK_TITLE = "Nội dung văn bản"


def _load_dotenv() -> None:
    env_path = _BACKEND / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _apply_railway_env() -> None:
    """Same public-proxy wiring as purge_db_railway.py (does not load localhost .env)."""
    pg = (os.environ.get("DATABASE_PUBLIC_URL") or "").strip()
    if not pg:
        raise SystemExit("Set DATABASE_PUBLIC_URL (Railway Postgres public URL).")
    if pg.startswith("postgres://"):
        pg = "postgresql://" + pg[len("postgres://") :]
    os.environ["DATABASE_URL"] = pg
    os.environ["DATABASE_SSL"] = os.environ.get("DATABASE_SSL") or "require"

    host = os.environ.get("NEO4J_BOLT_HOST", "tokaido.proxy.rlwy.net").strip()
    port = os.environ.get("NEO4J_BOLT_PORT", "20113").strip()
    pwd = (os.environ.get("NEO4J_PASSWORD") or "").strip()
    if not pwd:
        raise SystemExit("Set NEO4J_PASSWORD.")
    os.environ["NEO4J_URI"] = f"bolt://{host}:{port}"
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ["NEO4J_PASSWORD"] = pwd
    os.environ.setdefault("QDRANT_URL", "http://tokaido.proxy.rlwy.net:30541")


async def _list_fallback(driver: Any, so_hieu: str | None) -> list[dict[str, str]]:
    query = """
    MATCH (v:VanBanPhapLuat)-[:CO_DIEU]->(d:Dieu)
    WHERE d.tieu_de = $title
      AND ($so_hieu IS NULL OR v.so_hieu = $so_hieu OR v.vb_id = $so_hieu)
    WITH v, count(d) AS fallback_dieu
    OPTIONAL MATCH (v)-[:CO_DIEU]->(alld:Dieu)
    WITH v, fallback_dieu, count(alld) AS dieu_count
    WHERE dieu_count = 1 AND fallback_dieu = 1
    RETURN coalesce(v.vb_id, v.so_hieu) AS id,
           v.so_hieu AS so_hieu,
           coalesce(v.ten, '') AS ten,
           coalesce(v.source_filename, '') AS source_filename
    ORDER BY so_hieu
    """
    rows: list[dict[str, str]] = []
    async with driver.session() as session:
        res = await session.run(query, title=FALLBACK_TITLE, so_hieu=so_hieu)
        async for r in res:
            rows.append(
                {
                    "id": str(r["id"] or ""),
                    "so_hieu": str(r["so_hieu"] or ""),
                    "ten": str(r["ten"] or ""),
                    "source_filename": str(r["source_filename"] or ""),
                }
            )
    return rows


async def main_async(args: argparse.Namespace) -> int:
    if args.railway:
        _apply_railway_env()
    else:
        _load_dotenv()

    from app.api.deps import get_db_pool, get_neo4j_driver, get_qdrant_client
    from app.services.diff_facade import LegalDiffFacade

    driver = await get_neo4j_driver()
    if not driver:
        raise SystemExit("Neo4j unavailable — check NEO4J_URI / password.")

    pool = await get_db_pool()
    qdrant = await get_qdrant_client()
    facade = LegalDiffFacade(pool=pool, neo4j_driver=driver, qdrant=qdrant)

    targets = await _list_fallback(driver, args.so_hieu)
    print(f"Tìm thấy {len(targets)} văn bản fallback (tieu_de = «{FALLBACK_TITLE}», đúng 1 Điều).")
    for i, t in enumerate(targets[:50], 1):
        print(f"  [{i}] {t['so_hieu'] or t['id']} | {t['ten'][:80]} | {t['source_filename']}")
    if len(targets) > 50:
        print(f"  … và {len(targets) - 50} nữa")

    if args.dry_run or not args.yes:
        print("\nDry-run / chưa --yes → không xóa. Chạy lại với --yes để xóa.")
        return 0

    deleted = 0
    for t in targets:
        key = t["so_hieu"] or t["id"]
        res = await facade.delete_van_ban(key)
        deleted += 1
        print(f"  DELETED {key} graph={res.get('deleted_graph_nodes')} files={res.get('deleted_files')}")

    print(f"\nĐã xóa {deleted}/{len(targets)} văn bản.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Xóa văn bản parser-fallback trên Neo4j/Qdrant/PG")
    p.add_argument("--railway", action="store_true", help="Dùng DATABASE_PUBLIC_URL + Neo4j/Qdrant public proxy")
    p.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không xóa")
    p.add_argument("--yes", action="store_true", help="Xác nhận xóa thật")
    p.add_argument("--so-hieu", default=None, help="Chỉ xóa một số hiệu (vd. 4919/BCT-XNK)")
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
