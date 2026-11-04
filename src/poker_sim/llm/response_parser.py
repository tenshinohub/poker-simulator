from __future__ import annotations
import json
from typing import Any

REQUIRED = {"summary", "timeline", "observations", "limitations"}

def parse_analysis(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    data = json.loads(text.strip())
    if not isinstance(data, dict) or not REQUIRED.issubset(data):
        raise ValueError(f"Analysis JSON must contain: {', '.join(sorted(REQUIRED))}")
    if not isinstance(data["summary"], str):
        raise ValueError("summary must be a string")
    for key in ("timeline", "observations", "limitations"):
        if not isinstance(data[key], list) or not all(isinstance(x, str) for x in data[key]):
            raise ValueError(f"{key} must be a list of strings")
    return {key: data[key] for key in sorted(REQUIRED)}
