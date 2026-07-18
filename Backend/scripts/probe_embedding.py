"""Quick probe: can we call the embedding API with Backend/.env?"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        print("NO .env")
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


async def main() -> None:
    load_dotenv()
    base = (os.getenv("BE2_EMBEDDING_BASE_URL") or os.getenv("BE2_OPENAI_BASE_URL") or "").rstrip("/")
    key = os.getenv("BE2_EMBEDDING_API_KEY") or os.getenv("BE2_OPENAI_API_KEY") or ""
    model = os.getenv("BE2_EMBEDDING_MODEL", "text-embedding-3-small")
    print(f"base={base}")
    print(f"model={model}")
    print(f"key_len={len(key)}")
    if not base:
        print("FAIL: no embedding base URL")
        return
    url = f"{base}/embeddings"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "input": ["thuế giá trị gia tăng khoản 1"]},
        )
        print(f"status={r.status_code}")
        print(f"body={(r.text or '')[:800]}")


if __name__ == "__main__":
    asyncio.run(main())
