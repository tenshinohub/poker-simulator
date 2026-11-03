from __future__ import annotations

from dataclasses import asdict
from queue import Queue, Empty
from threading import Event, Lock, Thread
from typing import Any
import uuid

from ..domain.actions import Action
from ..engine.game import Game, GameConfig
from ..players.random_agent import RandomAgent
from ..players.rule_agent import RuleBasedAgent


class BrowserHumanPlayer:
    def __init__(self, session: "GameSession") -> None:
        self.name = "あなた"
        self.session = session

    def decide(self, context):
        self.session.publish_turn(context)
        return self.session.actions.get()

    def decide_showdown(self, context: dict) -> str:
        self.session.publish_showdown_decision(context)
        return self.session.showdown_decisions.get()


class GameSession:
    def __init__(self, player_count: int, starting_stack: int, small_blind: int,
                 big_blind: int, seed: int | None = None) -> None:
        if not 2 <= player_count <= 9:
            raise ValueError("player_count must be between 2 and 9")
        if starting_stack <= 0 or small_blind <= 0 or big_blind < small_blind:
            raise ValueError("Invalid stack or blind configuration")
        self.id = str(uuid.uuid4())
        self.events: Queue[dict[str, Any]] = Queue()
        self.actions: Queue[Action] = Queue()
        self.showdown_decisions: Queue[str] = Queue()
        self.next_hand = Event()
        self.lock = Lock()
        self.latest_state: dict[str, Any] = {"status": "starting"}
        self.game: Game | None = None
        players = [BrowserHumanPlayer(self)]
        for i in range(player_count - 1):
            players.append(RuleBasedAgent(f"AI {i + 1}") if i % 2 == 0
                           else RandomAgent(f"AI {i + 1}", seed=(seed or 0) + i + 1))
        config = GameConfig(small_blind, big_blind, starting_stack, 1000, 9)
        self.game = Game(players, config, seed)
        # Start the first six-max hand with the human in MP, as requested.
        # For tables without an MP seat, keep the first hand on the button.
        positions = self.game.position_names(player_count)
        desired_position = "MP" if "MP" in positions else positions[0]
        human_offset = positions.index(desired_position)
        first_button = (-human_offset) % player_count
        self.game.button = (first_button - 1) % player_count
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def emit(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.latest_state = event
        self.events.put(event)

    def _player_snapshots(self, *, hand_complete: bool = False) -> list[dict[str, Any]]:
        game = self.game
        assert game is not None
        positions = game.position_map()
        snapshots = []
        for p in game.players:
            if p.folded:
                action_status = "FOLD"
            elif p.all_in:
                action_status = "ALL IN"
            else:
                action_status = "HAND COMPLETE" if hand_complete else "WAITING"
            snapshots.append({
                "player_id": p.player_id,
                "name": p.name,
                "seat": p.seat,
                "position": positions.get(p.seat, f"Seat{p.seat+1}"),
                "is_button": p.seat == game.button,
                "stack": p.stack,
                "street_bet": p.street_bet,
                "folded": p.folded,
                "all_in": p.all_in,
                "is_human": p.player_id == "p1",
                "action_status": action_status,
                "last_action": None,
            })
        return snapshots

    def publish_turn(self, context) -> None:
        game = self.game
        assert game is not None
        obs = context.observation
        legal = asdict(obs.legal_actions)
        street_actions = [a for a in obs.action_history if a.get("street") == obs.street]
        last_actions = {a["player_id"]: a for a in street_actions}
        players = self._player_snapshots()
        for player in players:
            pid = player["player_id"]
            if player["folded"]:
                player["action_status"] = "FOLD"
            elif player["all_in"]:
                player["action_status"] = "ALL IN"
            elif player["is_human"]:
                player["action_status"] = "YOUR TURN"
            elif pid in last_actions:
                player["action_status"] = "ACTED"
            elif player["street_bet"] > 0:
                player["action_status"] = "BLIND"
            else:
                player["action_status"] = "WAITING"
            player["last_action"] = last_actions.get(pid, {}).get("action")
        self.emit({
            "type": "your_turn", "session_id": self.id,
            "hand_id": obs.hand_id, "street": obs.street,
            "human_player_id": context.player_id,
            "button_seat": game.button,
            "human_position": obs.position,
            "hole_cards": [str(c) for c in obs.hole_cards],
            "board": [str(c) for c in obs.community_cards],
            "players": players, "pot": obs.pot,
            "current_bet": obs.current_bet, "to_call": obs.to_call,
            "legal_actions": legal,
            "action_history": list(obs.action_history),
        })


    def publish_showdown_decision(self, context: dict) -> None:
        game = self.game
        assert game is not None
        human = next(p for p in game.players if p.player_id == context["player_id"])
        self.emit({
            "type": "showdown_decision", "session_id": self.id,
            "hand_id": context["hand_id"], "human_player_id": human.player_id,
            "human_name": human.name, "hole_cards": [str(c) for c in human.hole_cards],
            "board": [str(c) for c in context["board"]],
            "hand_rank": str(context["hand_rank"]),
            "message": "ショーダウンです。手札を公開するか、マックするか選択してください。",
        })

    def _run(self) -> None:
        assert self.game is not None
        try:
            while sum(p.stack > 0 for p in self.game.players) >= 2:
                result = self.game.play_hand()
                player_snapshots = self._player_snapshots(hand_complete=True)
                player_names = {p["player_id"]: p["name"] for p in player_snapshots}
                human = next((p for p in self.game.players if p.player_id == "p1"), None)
                self.emit({
                    "type": "hand_complete", "session_id": self.id,
                    "hand_id": result.hand_id, "winners": result.winners,
                    "winner_names": [player_names[pid] for pid in result.winners],
                    "payouts": result.payouts,
                    "ending_stacks": result.ending_stacks,
                    "players": player_snapshots,
                    "human_player_id": "p1",
                    "human_position": self.game.position_map().get(human.seat) if human else None,
                    "hole_cards": [str(c) for c in human.hole_cards] if human else [],
                    "pot": sum(result.payouts.values()),
                    "board": [str(c) for c in result.board],
                    "revealed_hole_cards": {
                        pid: [str(c) for c in cards]
                        for pid, cards in result.revealed_hole_cards.items()
                    },
                    "reason": result.reason,
                })
                if sum(p.stack > 0 for p in self.game.players) < 2:
                    break
                self.next_hand.wait()
                self.next_hand.clear()
            self.emit({"type": "game_over", "session_id": self.id,
                       "players": [{"player_id": p.player_id, "name": p.name,
                                    "stack": p.stack} for p in self.game.players]})
        except Exception as exc:
            self.emit({"type": "error", "session_id": self.id,
                       "message": f"Game engine error: {exc}"})

    def submit_action(self, payload: dict[str, Any]) -> None:
        kind = payload.get("type")
        if kind in {"fold", "check", "call", "all_in"}:
            action = {"fold": Action.fold, "check": Action.check,
                      "call": Action.call, "all_in": Action.all_in}[kind]()
        elif kind in {"bet", "raise"}:
            amount = payload.get("amount")
            if not isinstance(amount, int) or isinstance(amount, bool):
                raise ValueError("bet/raise amount must be an integer")
            action = Action.bet_to(amount) if kind == "bet" else Action.raise_to(amount)
        else:
            raise ValueError("Unknown action type")
        self.actions.put(action)

    def submit_showdown_decision(self, decision: str) -> None:
        if decision not in {"show", "muck"}:
            raise ValueError("decision must be 'show' or 'muck'")
        self.showdown_decisions.put(decision)

    def start_next_hand(self) -> None:
        self.next_hand.set()

    def get_event(self, timeout: float = 15.0) -> dict[str, Any]:
        try:
            return self.events.get(timeout=timeout)
        except Empty:
            return {"type": "waiting", "session_id": self.id}
