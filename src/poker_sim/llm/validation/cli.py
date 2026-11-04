from __future__ import annotations
import argparse
import json
from pathlib import Path
from .validator import validate_analysis


def _read_jsonl(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            hand_id = item.get("hand_id")
            if not hand_id:
                raise ValueError(f"{path}:{line_no}: hand_id is required")
            if hand_id in records:
                raise ValueError(f"{path}:{line_no}: duplicate hand_id {hand_id}")
            records[str(hand_id)] = item
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate LLM hand recaps against source JSONL")
    parser.add_argument("--input", required=True, help="Original hand_history.jsonl")
    parser.add_argument("--analysis", required=True, help="Generated hand_analysis.jsonl")
    parser.add_argument("--output", default="hand_validation.jsonl")
    args = parser.parse_args()
    source = _read_jsonl(Path(args.input))
    analyses = _read_jsonl(Path(args.analysis))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for hand_id, analysis in analyses.items():
            if hand_id not in source:
                report = {"hand_id": hand_id, "checks": [{"field": "hand_id", "status": "fail",
                          "expected": "source hand exists", "actual": hand_id,
                          "message": "元履歴に該当するhand_idがありません"}],
                          "summary": {"pass": 0, "fail": 1, "not_reported": 0}}
            else:
                report = validate_analysis(source[hand_id], analysis)
            stream.write(json.dumps(report, ensure_ascii=False) + "\n")
            print(f"{hand_id}: {report['summary']}")
    missing = sorted(set(source) - set(analyses))
    if missing:
        print(f"未分析のハンド: {', '.join(missing)}")


if __name__ == "__main__":
    main()
