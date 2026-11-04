from __future__ import annotations
import json
from typing import Any
import re

REQUIRED = {"summary", "timeline", "observations", "limitations"}

# def parse_analysis(content: str) -> dict[str, Any]:
#     text = content.strip()
#     if text.startswith("```json"):
#         text = text[7:]
#     elif text.startswith("```"):
#         text = text[3:]
#     if text.endswith("```"):
#         text = text[:-3]
#     data = json.loads(text.strip())
#     if not isinstance(data, dict) or not REQUIRED.issubset(data):
#         raise ValueError(f"Analysis JSON must contain: {', '.join(sorted(REQUIRED))}")
#     if not isinstance(data["summary"], str):
#         raise ValueError("summary must be a string")
#     for key in ("timeline", "observations", "limitations"):
#         if not isinstance(data[key], list) or not all(isinstance(x, str) for x in data[key]):
#             raise ValueError(f"{key} must be a list of strings")
#     return {key: data[key] for key in sorted(REQUIRED)}

def parse_analysis(content: str) -> dict:
    content = content.strip()

    # Markdownコードブロックを除去
    match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        content,
        re.DOTALL,
    )

    if match:
        content = match.group(1)

    data = json.loads(content)

    if not isinstance(data, dict):
        raise ValueError("Analysis response must be a JSON object")

    missing = REQUIRED - data.keys()

    if missing:
        raise ValueError(
            f"Analysis JSON missing keys: {', '.join(sorted(missing))}"
        )

    if not isinstance(data["summary"], str):
        raise ValueError("summary must be a string")

    for key in ("observations", "timeline", "limitations"):
        if not isinstance(data[key], list):
            raise ValueError(f"{key} must be an array")

    return data