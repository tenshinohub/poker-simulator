from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from ..engine.game import Game, GameConfig

@dataclass
class MatchResult:
    hands_played: int
    hands: list[dict[str, Any]]
    final_stacks: dict[str, int]
    net_results: dict[str, int]

class MatchRunner:
    def __init__(self, players: list[Any], config: GameConfig | None = None, seed: int | None = None):
        self.game = Game(players, config, seed)

    def run(self, max_hands: int | None = None) -> MatchResult:
        limit = max_hands or self.game.config.max_hands
        for _ in range(limit):
            if sum(p.stack > 0 for p in self.game.players) < 2:
                break
            self.game.play_hand()
        final_stacks = {p.player_id: p.stack for p in self.game.players}
        initial = self.game.config.starting_stack
        net = {pid: stack - initial for pid, stack in final_stacks.items()}
        return MatchResult(len(self.game.history), self.game.history, final_stacks, net)
