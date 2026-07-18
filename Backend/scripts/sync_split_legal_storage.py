from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_db_pool, get_minio, get_neo4j_driver
from app.pipelines.legal.normalize import normalize_so_hieu
from scripts.import_split_legal_txt import parse_file


async def _document_ids(driver: Any) -> dict[str, str]:
    query = """
    MATCH (v:VanBanPhapLuat)
    WHERE v.so_hieu IS NOT NULL AND v.vb_id IS NOT NULL
    RETURN v.so_hieu AS so_hieu, v.vb_id AS vb_id
    """
    result: dict[str, str] = {}
    async with driver.session() as session:
        records = await session.run(query)
        async for record in records:
            result[normalize_so_hieu(str(record["so_hieu"]))] = str(record["vb_id"])
    return result


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Đồng bộ TXT đã tách vào MinIO và PostgreSQL van_ban_files."
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("sync_split_storage_manifest.jsonl"))
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="0 = tất cả")
    args = parser.parse_args()

    files = sorted(args.folder.glob("*.txt"))[args.offset :]
    if args.limit > 0:
        files = files[: args.limit]

    driver = await get_neo4j_driver()
    pool = await get_db_pool()
    storage = await get_minio()
    if not driver or not pool or not storage:
        raise RuntimeError("Neo4j, PostgreSQL và MinIO phải sẵn sàng")

    ids = await _document_ids(driver)
    done = skipped = missing = failed = 0
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    with args.manifest.open("a", encoding="utf-8") as log:
        for index, path in enumerate(files, start=args.offset + 1):
            try:
                payload = parse_file(path)
                so_hieu = normalize_so_hieu(payload["so_hieu"])
                vb_id = ids.get(so_hieu)
                if not vb_id:
                    missing += 1
                    record = {"file": str(path), "so_hieu": so_hieu, "status": "missing_graph"}
                else:
                    data = await run_in_threadpool(path.read_bytes)
                    checksum = hashlib.sha256(data).hexdigest()
                    key = f"split-txt/{checksum[:2]}/{checksum}/{path.name}"
                    mime = mimetypes.guess_type(path.name)[0] or "text/plain"
                    async with pool.acquire() as conn:
                        exists = await conn.fetchval(
                            "SELECT EXISTS(SELECT 1 FROM van_ban_files WHERE van_ban_id=$1 AND checksum=$2)",
                            vb_id,
                            checksum,
                        )
                    if exists:
                        skipped += 1
                        record = {"file": str(path), "vb_id": vb_id, "status": "skipped_existing"}
                    else:
                        await run_in_threadpool(storage.put_bytes, key, data, mime)
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                INSERT INTO van_ban_files
                                    (van_ban_id, filename, mime, storage_key, checksum, visibility)
                                VALUES ($1, $2, $3, $4, $5, 'public'::visibility)
                                ON CONFLICT (van_ban_id, checksum) DO UPDATE
                                SET filename=EXCLUDED.filename, mime=EXCLUDED.mime,
                                    storage_key=EXCLUDED.storage_key, visibility=EXCLUDED.visibility
                                """,
                                vb_id,
                                path.name,
                                mime,
                                key,
                                checksum,
                            )
                        done += 1
                        record = {"file": str(path), "vb_id": vb_id, "storage_key": key, "status": "success"}
            except Exception as exc:  # noqa: BLE001
                failed += 1
                record = {"file": str(path), "status": "error", "error": str(exc)}

            log.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.flush()
            if index % 250 == 0 or record["status"] in {"error", "missing_graph"}:
                print(
                    f"[{index}] done={done} skipped={skipped} missing={missing} failed={failed}",
                    flush=True,
                )

    print(json.dumps({"selected": len(files), "done": done, "skipped": skipped, "missing_graph": missing, "failed": failed, "manifest": str(args.manifest)}, ensure_ascii=False, indent=2))
    await driver.close()
    await pool.close()
    return 0 if failed == 0 and missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
