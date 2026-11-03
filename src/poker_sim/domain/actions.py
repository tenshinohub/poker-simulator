from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

ActionType = Literal["fold", "check", "call", "bet", "raise", "all_in"]

@dataclass(frozen=True)
class Action:
    type: ActionType
    amount: int | None = None

    def __post_init__(self) -> None:
        if self.type not in {"fold", "check", "call", "bet", "raise", "all_in"}:
            raise ValueError(f"Unknown action type: {self.type}")
        if self.type in {"bet", "raise"}:
            if self.amount is None or self.amount <= 0:
                raise ValueError(f"{self.type} requires a positive total street contribution")
        elif self.amount is not None:
            raise ValueError(f"{self.type} does not take an amount")

    @classmethod
    def fold(cls) -> "Action": return cls("fold")
    @classmethod
    def check(cls) -> "Action": return cls("check")
    @classmethod
    def call(cls) -> "Action": return cls("call")
    @classmethod
    def bet_to(cls, total: int) -> "Action": return cls("bet", total)
    @classmethod
    def raise_to(cls, total: int) -> "Action": return cls("raise", total)
    @classmethod
    def all_in(cls) -> "Action": return cls("all_in")
