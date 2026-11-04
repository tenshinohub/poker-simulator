from __future__ import annotations
import os
from .base import LLMRequest, LLMResponse

class GeminiProvider:
    """Gemini adapter. Requires the optional google-genai package and GEMINI_API_KEY."""
    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError('Install the optional dependency: pip install -e ".[llm]"') from exc
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=request.user_prompt,
            config={"system_instruction": request.system_prompt},
        )
        usage = None
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = {
                "prompt_token_count": getattr(meta, "prompt_token_count", None),
                "candidates_token_count": getattr(meta, "candidates_token_count", None),
                "total_token_count": getattr(meta, "total_token_count", None),
            }
        return LLMResponse(
            content=response.text or "", provider="gemini", model=self.model, usage=usage
        )
