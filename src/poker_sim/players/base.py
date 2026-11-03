from __future__ import annotations
from typing import Protocol
from ..domain.actions import Action
from ..domain.models import PlayerContext

class Player(Protocol):
    name: str
    def decide(self, context: PlayerContext) -> Action: ...
