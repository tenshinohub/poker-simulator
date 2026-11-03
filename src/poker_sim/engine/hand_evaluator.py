from __future__ import annotations
from collections import Counter
from itertools import combinations
from ..domain.cards import Card

# Rank tuples compare lexicographically; category: 8 straight flush ... 0 high card.
def _straight_high(ranks: set[int]) -> int | None:
    vals = set(ranks)
    if 14 in vals:
        vals.add(1)  # Ace-low wheel
    for high in range(14, 4, -1):
        if all(r in vals for r in range(high - 4, high + 1)):
            return high
    return None

def evaluate_five(cards: tuple[Card, ...] | list[Card]) -> tuple[int, ...]:
    if len(cards) != 5:
        raise ValueError("evaluate_five requires exactly five cards")
    if len(set(cards)) != 5:
        raise ValueError("Duplicate cards")
    ranks = [c.rank for c in cards]
    counts = Counter(ranks)
    groups = sorted(((n, r) for r, n in counts.items()), reverse=True)
    flush = len({c.suit for c in cards}) == 1
    straight_high = _straight_high(set(ranks))

    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in ranks if r != quad)
        return (7, quad, kicker)
    if sorted(counts.values()) == [2, 3]:
        trip = max(r for r, n in counts.items() if n == 3)
        pair = max(r for r, n in counts.items() if n == 2)
        return (6, trip, pair)
    if flush:
        return (5, *sorted(ranks, reverse=True))
    if straight_high:
        return (4, straight_high)
    trips = sorted((r for r, n in counts.items() if n == 3), reverse=True)
    if trips:
        kickers = sorted((r for r, n in counts.items() if n == 1), reverse=True)
        return (3, trips[0], *kickers)
    pairs = sorted((r for r, n in counts.items() if n == 2), reverse=True)
    if len(pairs) >= 2:
        kicker = max(r for r, n in counts.items() if n == 1)
        return (2, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((r for r, n in counts.items() if n == 1), reverse=True)
        return (1, pair, *kickers)
    return (0, *sorted(ranks, reverse=True))

def evaluate_hand(cards: list[Card] | tuple[Card, ...]) -> tuple[int, ...]:
    if len(cards) < 5 or len(cards) > 7:
        raise ValueError("evaluate_hand requires 5, 6, or 7 cards")
    if len(set(cards)) != len(cards):
        raise ValueError("Duplicate cards")
    return max(evaluate_five(combo) for combo in combinations(cards, 5))
