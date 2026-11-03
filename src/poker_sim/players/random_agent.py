from __future__ import annotations
import random
from ..domain.actions import Action
from ..domain.models import PlayerContext

class RandomAgent:
    def __init__(self, name: str = "Random", seed: int | None = None):
        self.name = name
        self.rng = random.Random(seed)

    def decide(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions
        options = []
        if legal.can_check: options.append(Action.check())
        if legal.can_call: options.append(Action.call())
        # Folding while checking is free is strategically meaningless and can
        # leave side pots with no eligible player when all live players do so.
        if legal.can_fold and not legal.can_check:
            options.append(Action.fold())
        if legal.can_bet: options.append(Action.bet_to(legal.min_bet_to or obs.current_bet + 1))
        if legal.can_raise:
            options.append(Action.raise_to(min(legal.max_raise_to, legal.min_raise_to or legal.max_raise_to)))
        if legal.can_all_in and self.rng.random() < 0.03:
            return Action.all_in()
        return self.rng.choice(options) if options else Action.check()

    def decide_showdown(self, context: dict) -> str:
        # RandomAgent uses a simple default disclosure policy for now.
        #return "show" if context["won"] else "muck"
        if context["won"]:
            return "show"
        else:
            if self.rng.random() < 0.5:
                return "show"
            else:
                return "muck"
