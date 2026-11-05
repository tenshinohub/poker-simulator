from __future__ import annotations

from hashlib import sha256
import random
from typing import Any, Iterable

from ..domain.actions import Action
from ..domain.cards import standard_deck
from ..domain.models import PlayerContext
from ..engine.hand_evaluator import evaluate_hand


class RuleBasedAgent:
    """An explainable agent that estimates showdown equity by simulation.

    This is a heuristic policy, not a GTO strategy. Bet/raise amounts are
    total street contributions, matching Action's API.
    """

    _EQUITY_SAMPLES = 256

    def __init__(self, name: str = "Rule"):
        self.name = name

    def decide(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions

        equity = self._estimate_equity(context)
        raises = self._count_raises(obs.action_history, obs.street)
        opponents = max(1, obs.opponent_count)
        position_adjustment = self._position_adjustment(obs.position)

        if legal.can_raise:
            threshold = min(
                0.92,
                0.65 + 0.025 * (opponents - 1) + 0.065 * raises
                + position_adjustment,
            )
            target = self._raise_target(legal, obs.pot, obs.to_call)
            if target is not None and equity >= threshold:
                return Action.raise_to(target)

        if legal.can_bet:
            threshold = min(0.82, 0.60 + 0.025 * (opponents - 1))
            target = self._bet_target(legal, obs.pot)
            if target is not None and equity >= threshold:
                return Action.bet_to(target)

        if legal.can_call:
            required_equity = self._pot_odds(obs.pot, legal.call_amount)
            required_equity += min(0.16, 0.025 + 0.04 * raises)
            if equity >= required_equity:
                return Action.call()
            if legal.can_fold:
                return Action.fold()

        return self._passive_fallback(context)

    @classmethod
    def _estimate_equity(cls, context: PlayerContext) -> float:
        """Estimate share of the pot against uniformly random live hands."""
        obs = context.observation
        known_cards = tuple(obs.hole_cards) + tuple(obs.community_cards)
        if len(obs.hole_cards) != 2 or len(obs.community_cards) > 5:
            raise ValueError("Equity estimation requires two hole cards and at most five board cards")

        deck = [card for card in standard_deck() if card not in known_cards]
        opponents = max(1, obs.opponent_count)
        cards_needed = opponents * 2 + 5 - len(obs.community_cards)
        if cards_needed > len(deck):
            raise ValueError("Not enough cards to estimate showdown equity")

        seed_input = "|".join((
            obs.hand_id,
            obs.player_id,
            obs.street,
            str(opponents),
            str(obs.pot),
            str(obs.to_call),
            ",".join(str(card) for card in known_cards),
            str(len(obs.action_history)),
        ))
        seed = int.from_bytes(sha256(seed_input.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        wins = 0.0

        for _ in range(cls._EQUITY_SAMPLES):
            sampled = rng.sample(deck, cards_needed)
            opponent_cards = [
                sampled[index * 2:index * 2 + 2]
                for index in range(opponents)
            ]
            board = tuple(obs.community_cards) + tuple(sampled[opponents * 2:])
            hero_rank = evaluate_hand(tuple(obs.hole_cards) + board)
            opponent_ranks = [
                evaluate_hand(tuple(cards) + board)
                for cards in opponent_cards
            ]
            best_rank = max(hero_rank, *opponent_ranks)
            winners = 1 + sum(rank == best_rank for rank in opponent_ranks)
            if hero_rank == best_rank:
                wins += 1.0 / winners

        return wins / cls._EQUITY_SAMPLES

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
    def _position_adjustment(position: str) -> float:
        normalized = position.upper()
        if normalized in {"BTN", "BTN/SB", "CO"}:
            return -0.02
        if normalized.startswith("UTG"):
            return 0.025
        return 0.0

    @staticmethod
    def _pot_odds(pot: int, to_call: int) -> float:
        if to_call <= 0:
            return 0.0
        denominator = max(1, pot + to_call)
        return to_call / denominator

    @staticmethod
    def _raise_target(legal: Any, pot: int, to_call: int) -> int | None:
        minimum = legal.min_raise_to
        if minimum is None or minimum > legal.max_raise_to:
            return None
        target = max(minimum, round((pot + to_call) * 0.66))
        return min(legal.max_raise_to, target)

    @staticmethod
    def _bet_target(legal: Any, pot: int) -> int | None:
        minimum = legal.min_bet_to
        if minimum is None or minimum > legal.max_raise_to:
            return None
        return min(legal.max_raise_to, max(minimum, round(pot * 0.66)))

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