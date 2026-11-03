from __future__ import annotations
from dataclasses import dataclass
import random
from itertools import cycle
from typing import Any
from ..domain.cards import Card, shuffled_deck
from ..domain.actions import Action
from ..domain.models import PlayerState, PlayerView, PlayerContext, HandResult, STREETS
from .betting import BettingRound
from .hand_evaluator import evaluate_hand
from .pots import build_side_pots, split_amount

@dataclass(frozen=True)
class GameConfig:
    small_blind: int = 5
    big_blind: int = 10
    starting_stack: int = 1000
    max_hands: int = 100
    max_players: int = 9

    def __post_init__(self):
        if self.small_blind <= 0 or self.big_blind < self.small_blind:
            raise ValueError("Require 0 < small_blind <= big_blind")
        if self.starting_stack <= 0 or self.max_hands <= 0:
            raise ValueError("Starting stack and max_hands must be positive")
        if not 2 <= self.max_players <= 9:
            raise ValueError("max_players must be between 2 and 9")

class Game:
    def __init__(self, players: list[Any], config: GameConfig | None = None, seed: int | None = None):
        self.config = config or GameConfig()
        if not 2 <= len(players) <= self.config.max_players:
            raise ValueError("Player count must be 2..max_players")
        self.rng = random.Random(seed)
        self.players = []
        for i, player in enumerate(players):
            name = getattr(player, "name", f"Player{i+1}")
            self.players.append(PlayerState(f"p{i+1}", name, self.config.starting_stack, i))
        self.player_modules = {f"p{i+1}": p for i, p in enumerate(players)}
        self.button = -1
        self.hand_number = 0
        self.history: list[dict[str, Any]] = []

    def play_hand(self) -> HandResult:
        self.hand_number += 1
        hand_id = f"hand-{self.hand_number:06d}"
        active_seats = [i for i, p in enumerate(self.players) if p.stack > 0]
        if len(active_seats) < 2:
            raise RuntimeError("Fewer than two players have chips")
        self.button = self._next_seat(self.button, active_seats)
        # Reset hand fields. Bust players remain seated but are not dealt cards.
        for p in self.players:
            p.hole_cards = []
            p.folded = p.stack == 0
            p.all_in = False
            p.street_bet = 0
            p.hand_contribution = 0
            p.starting_stack = p.stack
        seat_order = self._seat_order_from(self.button, active_seats)
        deck = shuffled_deck(self.rng)
        for _ in range(2):
            for seat in seat_order:
                self.players[seat].hole_cards.append(deck.pop())
        board: list[Card] = []
        actions: list[dict[str, Any]] = []
        payouts = {p.player_id: 0 for p in self.players}
        pot_log: list[dict[str, Any]] = []

        if len(active_seats) == 2:
            sb_seat, bb_seat = self.button, self._next_seat(self.button, active_seats)
        else:
            sb_seat = self._next_seat(self.button, active_seats)
            bb_seat = self._next_seat(sb_seat, active_seats)
        self._post_blind(self.players[sb_seat], self.config.small_blind)
        self._post_blind(self.players[bb_seat], self.config.big_blind)
        current_bet = max(p.street_bet for p in self.players)
        preflop_order = self._seat_order_from(bb_seat, active_seats, include_start=False)
        # Start action at seat after BB; in heads-up, button/SB acts first preflop.
        preflop_order = self._seat_order_from(bb_seat, active_seats, include_start=False)
        result_reason = "showdown"
        for street_index, street in enumerate(STREETS):
            if street_index == 0:
                round_order = preflop_order
                current_bet = max(p.street_bet for p in self.players)
            else:
                for p in self.players:
                    p.street_bet = 0
                current_bet = 0
                self._deal_board(deck, board, street_index)
                round_order = self._seat_order_from(self.button, active_seats, include_start=False)
            contenders = [p for p in self.players if not p.folded]
            if len(contenders) <= 1:
                break
            round_state = BettingRound(self.players, self.config.big_blind, current_bet)
            # A player who is all-in cannot act; if no one can act, skip betting.
            if sum(1 for p in contenders if not p.all_in) >= 2:
                self._betting_loop(round_state, round_order, hand_id, street, board, actions)
            contenders = [p for p in self.players if not p.folded]
            if len(contenders) <= 1:
                result_reason = "everyone_else_folded"
                break
            if all(p.all_in or p.folded for p in self.players):
                # no more betting; remaining streets dealt by next iterations
                continue

        # Ensure full board for showdown when all players are all-in.
        if len([p for p in self.players if not p.folded]) > 1 and len(board) < 5:
            while len(board) < 5:
                self._deal_board(deck, board, 1 if len(board) == 0 else (2 if len(board) == 3 else 3))
        contenders = [p for p in self.players if not p.folded]
        if len(contenders) == 1:
            winner = contenders[0]
            total = sum(p.hand_contribution for p in self.players)
            winner.stack += total
            payouts[winner.player_id] += total
            pot_log.append({"amount": total, "eligible": [winner.player_id], "winners": [winner.player_id]})
            result_reason = "everyone_else_folded"
        else:
            pots = build_side_pots({p.player_id: p.hand_contribution for p in self.players},
                                   {p.player_id for p in self.players if p.folded})
            ranks = {p.player_id: evaluate_hand(p.hole_cards + board) for p in contenders}
            seat_ids = [p.player_id for p in self.players]
            for pot in pots:
                eligible = [self._player(pid) for pid in pot.eligible if pid in ranks]
                if not eligible:
                    # This can occur only if malformed contributions/folds; fail loudly.
                    raise RuntimeError("Pot has no eligible player")
                best = max(ranks[p.player_id] for p in eligible)
                winners = [p.player_id for p in eligible if ranks[p.player_id] == best]
                shares = split_amount(pot.amount, winners, seat_ids)
                for pid, amount in shares.items():
                    self._player(pid).stack += amount
                    payouts[pid] += amount
                pot_log.append({"amount": pot.amount, "eligible": list(pot.eligible),
                                "winners": winners, "payouts": shares})
            result_reason = "showdown"
        revealed = {p.player_id: list(p.hole_cards) for p in contenders}
        starting = {p.player_id: p.starting_stack for p in self.players}
        ending = {p.player_id: p.stack for p in self.players}
        result = HandResult(hand_id, [pid for pid, amount in payouts.items() if amount > 0],
                            payouts, starting, ending, board, revealed, actions, pot_log, result_reason)
        self.history.append(self._result_to_dict(result))
        return result

    def _betting_loop(self, round_state: BettingRound, order: list[int], hand_id: str,
                      street: str, board: list[Card], actions: list[dict[str, Any]]) -> None:
        # Action loop continues until every non-folded, non-all-in player has matched current bet
        # and acted since the last full raise.
        pending = [i for i in order if not self.players[i].folded and not self.players[i].all_in]
        cursor = 0
        safety = 0
        while pending and safety < 1000:
            safety += 1
            seat = pending.pop(0)
            p = self.players[seat]
            if p.folded or p.all_in:
                continue
            # If no outstanding bet and player already acted, no need to act again.
            if p.street_bet == round_state.current_bet and p.player_id in round_state.acted_since_full_raise:
                continue
            view = self._observation(p, hand_id, street, board, actions, round_state)
            context = PlayerContext(hand_id, p.player_id, view)
            module = self.player_modules[p.player_id]
            action = module.decide(context)
            try:
                round_state.apply(p, action)
            except ValueError as exc:
                # Invalid agent output is recorded and safely converted to check/call/fold.
                legal = round_state.legal_actions(p)
                fallback = Action.check() if legal.can_check else (Action.fold() if legal.can_fold else Action.call())
                actions.append({"player_id": p.player_id, "street": street, "action": repr(action),
                                "invalid_reason": str(exc), "fallback": fallback.type})
                round_state.apply(p, fallback)
                action = fallback
            actions.append({"player_id": p.player_id, "street": street,
                            "action": action.type, "amount": action.amount})
            if action.type in {"bet", "raise", "all_in"} and p.street_bet == round_state.current_bet:
                # After a raise, everyone who owes chips must act again; raise rights are handled by round state.
                pending = [i for i in order if not self.players[i].folded and not self.players[i].all_in
                           and (self.players[i].street_bet < round_state.current_bet
                                or self.players[i].player_id not in round_state.acted_since_full_raise)]
            else:
                # Continue with players still owing chips or who have not acted.
                pending.extend(i for i in order if i not in pending and not self.players[i].folded
                               and not self.players[i].all_in
                               and (self.players[i].street_bet < round_state.current_bet
                                    or self.players[i].player_id not in round_state.acted_since_full_raise))
            # Avoid duplicate queue entries.
            pending = list(dict.fromkeys(pending))
        if safety >= 1000:
            raise RuntimeError("Betting loop safety limit exceeded")

    def _observation(self, p: PlayerState, hand_id: str, street: str, board: list[Card],
                     actions: list[dict[str, Any]], round_state: BettingRound) -> PlayerView:
        legal = round_state.legal_actions(p)
        return PlayerView(hand_id, p.player_id, street, self._position(p.seat),
                          tuple(p.hole_cards), tuple(board), p.stack,
                          sum(x.hand_contribution for x in self.players),
                          round_state.current_bet, max(0, round_state.current_bet - p.street_bet),
                          legal, tuple(dict(a) for a in actions))

    def _position(self, seat: int) -> str:
        active = [p.seat for p in self.players if p.stack > 0 or p.seat == seat]
        if len(active) == 2:
            return "BTN/SB" if seat == self.button else "BB"
        if seat == self.button: return "BTN"
        if seat == self._next_seat(self.button, active): return "SB"
        if seat == self._next_seat(self._next_seat(self.button, active), active): return "BB"
        return f"Seat{seat+1}"

    def _post_blind(self, p: PlayerState, amount: int) -> None:
        actual = min(amount, p.stack)
        p.stack -= actual
        p.street_bet += actual
        p.hand_contribution += actual
        if p.stack == 0: p.all_in = True

    def _deal_board(self, deck: list[Card], board: list[Card], street_index: int) -> None:
        deck.pop()  # burn card
        if street_index == 1:
            board.extend([deck.pop(), deck.pop(), deck.pop()])
        else:
            board.append(deck.pop())

    def _next_seat(self, seat: int, active_seats: list[int]) -> int:
        ordered = sorted(active_seats)
        for offset in range(1, len(self.players) + 1):
            candidate = (seat + offset) % len(self.players)
            if candidate in ordered:
                return candidate
        raise RuntimeError("No active seat")

    def _seat_order_from(self, seat: int, active_seats: list[int], include_start: bool = True) -> list[int]:
        start = seat if include_start else (seat + 1) % len(self.players)
        return [((start + i) % len(self.players)) for i in range(len(self.players))
                if ((start + i) % len(self.players)) in active_seats]

    def _player(self, player_id: str) -> PlayerState:
        return next(p for p in self.players if p.player_id == player_id)

    @staticmethod
    def _result_to_dict(r: HandResult) -> dict[str, Any]:
        return {
            "hand_id": r.hand_id, "winners": r.winners, "payouts": r.payouts,
            "starting_stacks": r.starting_stacks, "ending_stacks": r.ending_stacks,
            "board": [str(c) for c in r.board],
            "revealed_hole_cards": {k: [str(c) for c in v] for k, v in r.revealed_hole_cards.items()},
            "actions": r.actions, "pots": r.pots, "reason": r.reason,
        }
