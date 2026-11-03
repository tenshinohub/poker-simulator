from __future__ import annotations
from ..domain.actions import Action
from ..domain.models import PlayerContext

class RuleBasedAgent:
    """A deliberately simple baseline, not a strong poker strategy."""
    def __init__(self, name: str = "Rule"):
        self.name = name

    def decide(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions
        if obs.street == "preflop":
            ranks = sorted((c.rank for c in obs.hole_cards), reverse=True)
            pair = ranks[0] == ranks[1]
            suited = obs.hole_cards[0].suit == obs.hole_cards[1].suit
            strength = pair or ranks[0] >= 13 or (ranks[0] >= 11 and ranks[1] >= 10) or (suited and ranks[0] >= 10)
            if strength and legal.can_raise:
                target = min(legal.max_raise_to, legal.min_raise_to or legal.max_raise_to)
                if target >= (legal.min_raise_to or target):
                    return Action.raise_to(target)
            if strength and legal.can_call:
                return Action.call()
        if legal.can_check:
            return Action.check()
        if legal.can_call and obs.to_call <= max(1, obs.pot // 4):
            return Action.call()
        if legal.can_fold:
            return Action.fold()
        return Action.all_in()

    def decide_showdown(self, context: dict) -> str:
        # Baseline disclosure policy: show a winning hand; muck a losing one.
        return "show" if context["won"] else "muck"
