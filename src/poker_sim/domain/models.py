from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .cards import Card
from .actions import Action

STREETS = ("preflop", "flop", "turn", "river")

@dataclass
class PlayerState:
    player_id: str
    name: str
    stack: int
    seat: int
    hole_cards: list[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    street_bet: int = 0
    hand_contribution: int = 0
    starting_stack: int = 0

    def __post_init__(self) -> None:
        if self.stack < 0:
            raise ValueError("Stack cannot be negative")
        if self.starting_stack == 0:
            self.starting_stack = self.stack

@dataclass(frozen=True)
class LegalActions:
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int
    can_bet: bool
    min_bet_to: int | None
    can_raise: bool
    min_raise_to: int | None
    max_raise_to: int
    can_all_in: bool

@dataclass(frozen=True)
class PlayerView:
    hand_id: str
    player_id: str
    street: str
    position: str
    hole_cards: tuple[Card, ...]
    community_cards: tuple[Card, ...]
    stack: int
    pot: int
    current_bet: int
    to_call: int
    legal_actions: LegalActions
    action_history: tuple[dict[str, Any], ...]

@dataclass(frozen=True)
class PlayerContext:
    hand_id: str
    player_id: str
    observation: PlayerView

@dataclass
class HandResult:
    hand_id: str
    winners: list[str]
    payouts: dict[str, int]
    starting_stacks: dict[str, int]
    ending_stacks: dict[str, int]
    contributions: dict[str, int]
    board: list[Card]
    revealed_hole_cards: dict[str, list[Card]]
    actions: list[dict[str, Any]]
    pots: list[dict[str, Any]]
    reason: str
