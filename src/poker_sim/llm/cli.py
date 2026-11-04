from __future__ import annotations
import argparse
import json
from pathlib import Path
from .analyzer import HandHistoryAnalyzer, result_to_dict
from .providers.gemini import GeminiProvider

def main() -> None:
    parser = argparse.ArgumentParser(description="Create factual LLM recaps from completed hand-history JSONL")
    parser.add_argument("--input", required=True, help="Input hand_history.jsonl")
    parser.add_argument("--output", default="hand_analysis.jsonl")
    parser.add_argument("--model", required=True, help="Gemini model identifier")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of hands to analyze",)
    args = parser.parse_args()
    analyzer = HandHistoryAnalyzer(GeminiProvider(model=args.model))
    source, target = Path(args.input), Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
        # for line_no, line in enumerate(src, 1):
        #     if not line.strip():
        #         continue
        #     try:
        #         record = json.loads(line)
        #         result = analyzer.analyze(record)
        #         dst.write(json.dumps(result_to_dict(result), ensure_ascii=False) + "\n")
        #         dst.flush()
        #     except Exception as exc:
        #         raise RuntimeError(f"Failed at input line {line_no}: {exc}") from exc
        
        processed_count = 0
        #limit = 3

        for line_no, line in enumerate(src, 1):
            if not line.strip():
                continue

            if args.limit is not None and processed_count >= args.limit:
                break

            try:
                record = json.loads(line)
                result = analyzer.analyze(record)
                dst.write(json.dumps(result_to_dict(result), ensure_ascii=False) + "\n")
                dst.flush()

                processed_count += 1

            except Exception as exc:
                raise RuntimeError(
                    f"Failed at input line {line_no}: {exc}"
                ) from exc

if __name__ == "__main__":
    main()
