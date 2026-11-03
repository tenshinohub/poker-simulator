from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from ..domain.actions import Action
from ..domain.models import PlayerContext


class RuleBasedAgent:
    """A conservative, explainable baseline agent.

    This is intentionally a simple rule-based policy, not a GTO strategy.
    Bet/raise amounts are total street contributions, matching Action's API.
    """

    def __init__(self, name: str = "Rule"):
        self.name = name

    def decide(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions

        if obs.street == "preflop":
            return self._decide_preflop(context)
        return self._decide_postflop(context)

    def _decide_preflop(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions
        strength = self._evaluate_preflop(obs.hole_cards)
        raises = self._count_raises(obs.action_history, obs.street)
        position_bonus = self._position_bonus(obs.position)
        effective_strength = min(1.0, strength + position_bonus)

        # Re-raises require progressively stronger starting hands.
        raise_threshold = (0.67, 0.82, 0.93)[min(raises, 2)]
        if legal.can_raise and effective_strength >= raise_threshold:
            target = self._minimum_raise_target(legal)
            if target is not None:
                return Action.raise_to(target)

        # A call is based on pot odds and hand strength, not a fixed chip amount.
        if legal.can_call:
            pot_odds = self._pot_odds(obs.pot, obs.to_call)
            call_threshold = 0.08 + 0.55 * effective_strength
            # Facing multiple raises, tighten the calling range.
            call_threshold += min(0.18, raises * 0.06)
            if pot_odds <= call_threshold:
                return Action.call()

        return self._passive_fallback(context)

    def _decide_postflop(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions
        hand_class = self._evaluate_postflop(
            tuple(obs.hole_cards) + tuple(obs.community_cards)
        )
        raises = self._count_raises(obs.action_history, obs.street)

        # Only value-raise with a made hand. Re-raises need a stronger hand.
        if legal.can_raise:
            threshold = 4 if raises == 0 else 5
            if hand_class >= threshold:
                target = self._minimum_raise_target(legal)
                if target is not None:
                    return Action.raise_to(target)

        if legal.can_bet and hand_class >= 4:
            target = legal.min_bet_to
            if target is not None and target <= legal.max_raise_to:
                return Action.bet_to(target)

        if legal.can_call:
            # Approximate strength-to-equity mapping; deliberately conservative.
            estimated_strength = self._postflop_strength(hand_class)
            pot_odds = self._pot_odds(obs.pot, obs.to_call)
            if pot_odds <= estimated_strength * 0.85:
                return Action.call()

        return self._passive_fallback(context)

    @staticmethod
    def _evaluate_preflop(cards: Iterable[Any]) -> float:
        """Return a coarse 0..1 starting-hand score for two hole cards."""
        cards = tuple(cards)
        if len(cards) != 2:
            return 0.0

        ranks = sorted((int(card.rank) for card in cards), reverse=True)
        high, low = ranks
        pair = high == low
        suited = cards[0].suit == cards[1].suit
        gap = high - low

        if pair:
            # Small pairs remain playable, but premium pairs score much higher.
            return min(0.98, 0.58 + (high - 2) * 0.035)

        score = 0.18 + (high - 2) * 0.035 + (low - 2) * 0.012
        if suited:
            score += 0.07
        if gap == 1:
            score += 0.06
        elif gap == 2:
            score += 0.025
        elif gap >= 5:
            score -= 0.06
        if high >= 13 and low >= 10:
            score += 0.10
        if high == 14 and low >= 12:
            score += 0.08
        return max(0.05, min(0.95, score))

    @staticmethod
    def _evaluate_postflop(cards: Iterable[Any]) -> int:
        """Return a made-hand category: 0 high card .. 8 straight flush.

        This evaluates the best category available from the supplied 5-7 cards.
        It intentionally does not compare kickers or calculate draw equity.
        """
        cards = tuple(cards)
        if len(cards) < 5:
            return 0

        ranks = [int(card.rank) for card in cards]
        counts = Counter(ranks)
        groups = sorted(counts.values(), reverse=True)
        flush_suits = {
            suit for suit in {card.suit for card in cards}
            if sum(card.suit == suit for card in cards) >= 5
        }

        def has_straight(values: Iterable[int]) -> bool:
            unique = set(values)
            if 14 in unique:
                unique.add(1)  # wheel: A-2-3-4-5
            ordered = sorted(unique)
            run = 1
            for i in range(1, len(ordered)):
                run = run + 1 if ordered[i] == ordered[i - 1] + 1 else 1
                if run >= 5:
                    return True
            return False

        if flush_suits:
            for suit in flush_suits:
                suited_ranks = [card.rank for card in cards if card.suit == suit]
                if has_straight(suited_ranks):
                    return 8
        if groups[0] == 4:
            return 7
        if groups[0] == 3 and len(groups) > 1 and groups[1] >= 2:
            return 6
        if flush_suits:
            return 5
        if has_straight(ranks):
            return 4
        if groups[0] == 3:
            return 3
        if groups[0] == 2 and groups.count(2) >= 2:
            return 2
        if groups[0] == 2:
            return 1
        return 0

    @staticmethod
    def _postflop_strength(hand_class: int) -> float:
        # Heuristic values, not statistically calibrated equities.
        return (0.12, 0.28, 0.48, 0.62, 0.76, 0.84, 0.92, 0.97, 0.99)[
            max(0, min(8, hand_class))
        ]

    @staticmethod
    def _count_raises(history: Iterable[dict[str, Any]], street: str) -> int:
        count = 0
        for item in history:
            if item.get("street") != street:
                continue
            action = item.get("action")
            if action in {"bet", "raise"}:
                count += 1
            elif action == "all_in":
                before = item.get("current_bet_before")
                after = item.get("current_bet_after")
                if isinstance(before, int) and isinstance(after, int) and after > before:
                    count += 1
        return count

    @staticmethod
    def _position_bonus(position: str) -> float:
        normalized = position.upper()
        if normalized == "BTN":
            return 0.08
        if normalized == "BTN/SB":
            return 0.04
        if normalized in {"SB", "BB"}:
            return 0.0
        # SeatN values are unknown relative to the button; don't guess.
        return 0.02

    @staticmethod
    def _pot_odds(pot: int, to_call: int) -> float:
        if to_call <= 0:
            return 0.0
        denominator = max(1, pot + to_call)
        return to_call / denominator

    @staticmethod
    def _minimum_raise_target(legal: Any) -> int | None:
        minimum = legal.min_raise_to
        if minimum is None:
            return None
        if minimum <= legal.max_raise_to:
            return minimum
        return None

    @staticmethod
    def _passive_fallback(context: PlayerContext) -> Action:
        legal = context.observation.legal_actions
        if legal.can_check:
            return Action.check()
        if legal.can_call:
            return Action.call()
        if legal.can_fold:
            return Action.fold()
        # In the current engine can_all_in is generally true for any active player,
        # but don't choose it merely as a fallback: a no-opponent-chip state should
        # normally expose check/call/fold instead.
        if legal.can_all_in:
            return Action.all_in()
        raise RuntimeError("No legal action is available to RuleBasedAgent")

    def decide_showdown(self, context: dict) -> str:
        # Show a winning hand; muck a losing one.
        #return "show" if context["won"] else "muck"
        # Always show for now.
        return "show"