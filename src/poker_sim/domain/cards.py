from __future__ import annotations
from dataclasses import dataclass
import random

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}

@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in range(2, 15):
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

    @classmethod
    def parse(cls, text: str) -> "Card":
        text = text.strip()
        if len(text) != 2 or text[0].upper() not in RANK_VALUE or text[1].lower() not in SUITS:
            raise ValueError(f"Invalid card: {text!r}; use e.g. As, Td, 2c")
        return cls(RANK_VALUE[text[0].upper()], text[1].lower())

    def __str__(self) -> str:
        return RANKS[self.rank - 2] + self.suit

def standard_deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in range(2, 15)]

def shuffled_deck(rng: random.Random) -> list[Card]:
    deck = standard_deck()
    rng.shuffle(deck)
    return deck
