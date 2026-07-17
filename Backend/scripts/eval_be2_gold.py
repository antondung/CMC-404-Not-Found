from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intelligence.nli import nli_pair


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing gold file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Gold file must contain a list: {path}")
    return data


def precision_at_k(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    total = 0
    hit = 0
    for row in rows:
        expected = set(row.get("expected_khoan_ids") or row.get("khoan_ids") or [])
        predicted = list(row.get("predicted_khoan_ids") or [])[:k]
        if not expected:
            continue
        total += 1
        if expected.intersection(predicted):
            hit += 1
    return {"metric": f"precision@{k}", "total": total, "hits": hit, "value": hit / total if total else None}


async def eval_nli(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0
    correct = 0
    labels = {"khop", "mau_thuan", "khong_ro"}
    for row in rows:
        expected = row.get("label") or row.get("expected_label")
        if expected not in labels:
            continue
        premise = row.get("premise") or row.get("khoan_text") or ""
        hypothesis = row.get("hypothesis") or row.get("claim") or ""
        result = await nli_pair(premise, hypothesis)
        total += 1
        correct += int(result["label"] == expected)
    return {"metric": "nli_accuracy", "total": total, "correct": correct, "value": correct / total if total else None}


async def main() -> None:
    parser = argparse.ArgumentParser(description="BE2 gold evaluation. Reports only real metrics from provided gold files.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    root = Path(args.root)
    results: list[dict[str, Any]] = []
    links_path = root / "Data" / "gold" / "links.json"
    nli_path = root / "Data" / "gold" / "nli.json"
    if links_path.exists():
        results.append(precision_at_k(load_json(links_path), args.k))
    else:
        results.append({"metric": f"precision@{args.k}", "status": "missing_gold", "path": str(links_path)})
    if nli_path.exists():
        results.append(await eval_nli(load_json(nli_path)))
    else:
        results.append({"metric": "nli_accuracy", "status": "missing_gold", "path": str(nli_path)})
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
