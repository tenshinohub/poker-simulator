from __future__ import annotations

import os
from .base import LLMRequest, LLMResponse


class OpenAIProvider:
    """OpenAI Responses API adapter. Requires OPENAI_API_KEY and the openai extra."""

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError('Install the optional dependency: pip install -e ".[llm]"') from exc

        client = OpenAI(api_key=self.api_key, timeout=30.0)
        response = client.responses.create(
            model=self.model,
            instructions=request.system_prompt,
            input=request.user_prompt,
            text={"format": {"type": "json_object"}},
        )
        usage_data = getattr(response, "usage", None)
        usage = None
        if usage_data is not None:
            usage = {
                "input_tokens": getattr(usage_data, "input_tokens", None),
                "output_tokens": getattr(usage_data, "output_tokens", None),
                "total_tokens": getattr(usage_data, "total_tokens", None),
            }
        return LLMResponse(
            content=getattr(response, "output_text", "") or "",
            provider="openai",
            model=self.model,
            usage=usage,
        )
