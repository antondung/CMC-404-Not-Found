from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.lawgic_quality import EvaluationError, evaluate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic LAWGIC quality gates from separated gold and prediction files."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--release",
        action="store_true",
        help="Fail unless every dataset is an independently reviewed holdout and all blocking gates pass.",
    )
    args = parser.parse_args()
    try:
        report = evaluate_manifest(args.manifest)
    except EvaluationError as exc:
        print(json.dumps({"status": "invalid_evidence", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["blocking_gates_passed"]:
        return 1
    if args.release and report["release_decision"] != "GO":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
