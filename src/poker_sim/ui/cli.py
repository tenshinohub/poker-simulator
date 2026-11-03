from __future__ import annotations
import argparse
import json
from ..engine.game import GameConfig
from ..players.human import HumanCLIPlayer
from ..players.random_agent import RandomAgent
from ..players.rule_agent import RuleBasedAgent
from ..runner.match import MatchRunner
from ..evaluation.metrics import summarize_match
from ..storage.hand_history import write_jsonl

def build_player(spec: str, index: int):
    spec = spec.strip().lower()
    if spec == "human": return HumanCLIPlayer()
    if spec == "random": return RandomAgent(seed=1000 + index)
    if spec == "rule": return RuleBasedAgent()
    raise ValueError(f"Unknown player type {spec!r}; choose human, random, rule")

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Texas Hold'em cash-game simulator")
    parser.add_argument("--players", default="rule,random", help="comma-separated: human,rule,random")
    parser.add_argument("--hands", type=int, default=10)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--stack", type=int, default=1000)
    parser.add_argument("--small-blind", type=int, default=5)
    parser.add_argument("--big-blind", type=int, default=10)
    parser.add_argument("--history", default="hand_history.jsonl")
    args = parser.parse_args(argv)
    specs = [s.strip() for s in args.players.split(",") if s.strip()]
    players = [build_player(spec, i) for i, spec in enumerate(specs)]
    config = GameConfig(args.small_blind, args.big_blind, args.stack, args.hands, max(9, len(players)))
    runner = MatchRunner(players, config, args.seed)
    result = runner.run()
    summary = summarize_match(result)
    print(json.dumps(summary, indent=2))
    write_jsonl(args.history, result.hands)
    print(f"Hand history written to {args.history}")

if __name__ == "__main__":
    main()
