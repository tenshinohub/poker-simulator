from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from .prompt_builder import SYSTEM_PROMPT, build_request_payload
from .response_parser import parse_analysis
from .providers.base import LLMProvider, LLMRequest

@dataclass(frozen=True)
class AnalysisResult:
    hand_id: str
    created_at: str
    provider: str
    model: str
    analysis: dict[str, Any]
    usage: dict | None = None

class HandHistoryAnalyzer:
    """Produces a factual recap of a completed hand; it is not connected to Player/Game."""
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def analyze(self, record: dict[str, Any]) -> AnalysisResult:
        if not isinstance(record, dict) or not record.get("hand_id"):
            raise ValueError("A hand-history record with hand_id is required")
        response = self.provider.generate(LLMRequest(SYSTEM_PROMPT, build_request_payload(record)))
        analysis = parse_analysis(response.content)
        return AnalysisResult(
            hand_id=str(record["hand_id"]),
            created_at=datetime.now(timezone.utc).isoformat(),
            provider=response.provider,
            model=response.model,
            analysis=analysis,
            usage=response.usage,
        )

def result_to_dict(result: AnalysisResult) -> dict[str, Any]:
    return asdict(result)
