from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str

@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: dict | None = None

class LLMProvider(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...
