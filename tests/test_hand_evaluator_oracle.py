"""Differential tests against a deliberately independent reference evaluator.

The reference implementation uses rank/suit counts and explicit category
construction. It does not call production evaluator helpers.
"""
import itertools
import random
import unittest
from collections import Counter

from poker_sim.domain.cards import Card, standard_deck
from poker_sim.engine.hand_evaluator import evaluate_five, evaluate_hand


def reference_five(cards):
    ranks = [c.rank for c in cards]
    counts = Counter(ranks)
    by_count = sorted(((n, r) for r, n in counts.items()), reverse=True)
    flush = len({c.suit for c in cards}) == 1
    unique = sorted(set(ranks), reverse=True)
    straight_high = None
    if len(unique) == 5:
        if unique[0] - unique[-1] == 4:
            straight_high = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight_high = 5

    if flush and straight_high is not None:
        return (8, straight_high)
    if by_count[0][0] == 4:
        quad = by_count[0][1]
        return (7, quad, next(r for r in unique if r != quad))
    if by_count[0][0] == 3 and by_count[1][0] == 2:
        return (6, by_count[0][1], by_count[1][1])
    if flush:
        return (5, *unique)
    if straight_high is not None:
        return (4, straight_high)
    if by_count[0][0] == 3:
        trip = by_count[0][1]
        kickers = sorted((r for r, n in counts.items() if n == 1), reverse=True)
        return (3, trip, *kickers)
    pairs = sorted((r for r, n in counts.items() if n == 2), reverse=True)
    if len(pairs) == 2:
        kicker = next(r for r, n in counts.items() if n == 1)
        return (2, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        kickers = sorted((r for r, n in counts.items() if n == 1), reverse=True)
        return (1, pairs[0], *kickers)
    return (0, *unique)


def reference_hand(cards):
    return max(reference_five(combo) for combo in itertools.combinations(cards, 5))


class HandEvaluatorOracleTests(unittest.TestCase):
    def test_random_five_card_hands(self):
        # Deterministic differential sample against the independent reference.
        rng = random.Random(20261030)
        deck = standard_deck()
        for sample in range(20000):
            hand = rng.sample(deck, 5)
            self.assertEqual(
                evaluate_five(hand), reference_five(hand),
                f"Mismatch at five-card sample {sample}: {hand}",
            )

    def test_random_six_and_seven_card_hands(self):
        rng = random.Random(20261031)
        deck = standard_deck()
        for size in (6, 7):
            for sample in range(2000):
                hand = rng.sample(deck, size)
                self.assertEqual(
                    evaluate_hand(hand), reference_hand(hand),
                    f"Mismatch size={size} sample={sample}: {hand}",
                )

    def test_random_pairwise_comparisons_preserve_order(self):
        rng = random.Random(314159)
        deck = standard_deck()
        for sample in range(2000):
            left = rng.sample(deck, 7)
            remaining = [c for c in deck if c not in left]
            right = rng.sample(remaining, 7)
            actual = (evaluate_hand(left) > evaluate_hand(right)) - (
                evaluate_hand(left) < evaluate_hand(right)
            )
            expected = (reference_hand(left) > reference_hand(right)) - (
                reference_hand(left) < reference_hand(right)
            )
            self.assertEqual(actual, expected, f"Pair mismatch at sample {sample}")


if __name__ == "__main__":
    unittest.main()
