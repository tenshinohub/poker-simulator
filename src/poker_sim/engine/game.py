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
from .pots import build_side_pots, distribute_pots

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
        self.active_seats: list[int] = []
        self.history: list[dict[str, Any]] = []

    def play_hand(self) -> HandResult:
        self.hand_number += 1
        hand_id = f"hand-{self.hand_number:06d}"
        active_seats = [i for i, p in enumerate(self.players) if p.stack > 0]
        self.active_seats = list(active_seats)
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
            # Betting requires at least two players who can still make decisions.
            # Exception: a lone actionable player must still respond to an outstanding bet.
            if self._should_run_betting_round(contenders, round_state):
                self._betting_loop(
                    round_state, round_order, hand_id, street, board, actions
                )

            # Refund an unmatched portion of the last aggressor's bet after
            # the betting round is complete, and record the state transition.
            aggressor_id = round_state.last_aggressor_id
            aggressor = (
                self._player(aggressor_id)
                if aggressor_id is not None
                else None
            )

            if aggressor is not None:
                stack_before = aggressor.stack
                street_bet_before = aggressor.street_bet
                contribution_before = aggressor.hand_contribution
                current_bet_before = round_state.current_bet

                refund = round_state.refund_uncalled_bet()

                if refund > 0:
                    actions.append({
                        "event": "refund_uncalled_bet",
                        "player_id": aggressor.player_id,
                        "street": street,
                        "amount": refund,
                        "stack_before": stack_before,
                        "stack_after": aggressor.stack,
                        "street_bet_before": street_bet_before,
                        "street_bet_after": aggressor.street_bet,
                        "hand_contribution_before": contribution_before,
                        "hand_contribution_after": aggressor.hand_contribution,
                        "current_bet_before": current_bet_before,
                        "current_bet_after": round_state.current_bet,
                    })

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
            awards = distribute_pots(pots, ranks, seat_ids)
            for award in awards:
                for pid, amount in award.payouts.items():
                    self._player(pid).stack += amount
                    payouts[pid] += amount
                pot_log.append({
                    "amount": award.amount, "eligible": list(award.eligible),
                    "winners": list(award.winners), "payouts": award.payouts,
                })
            result_reason = "showdown"
        # A winning hand must be tabled to claim the pot. Losing showdown
        # hands may be shown or mucked; this affects disclosure only, never
        # hand evaluation or pot distribution.
        revealed: dict[str, list[Card]] = {}
        if result_reason == "showdown":
            for player in contenders:
                won = payouts[player.player_id] > 0
                module = self.player_modules[player.player_id]
                decision = "show"
                decide_showdown = getattr(module, "decide_showdown", None)
                if not won and callable(decide_showdown):
                    decision = decide_showdown({
                        "hand_id": hand_id,
                        "player_id": player.player_id,
                        "won": won,
                        "hole_cards": tuple(player.hole_cards),
                        "board": tuple(board),
                        "hand_rank": ranks[player.player_id],
                    })
                if decision not in {"show", "muck"}:
                    raise ValueError(f"Invalid showdown decision from {player.player_id}: {decision!r}")
                if won and decision != "show":
                    raise ValueError("A winning hand must be shown to claim the pot")
                if decision == "show":
                    revealed[player.player_id] = list(player.hole_cards)
                actions.append({
                    "event": "showdown_decision",
                    "player_id": player.player_id,
                    "decision": decision,
                    "won": won,
                })
        starting = {p.player_id: p.starting_stack for p in self.players}
        ending = {p.player_id: p.stack for p in self.players}
        #result = HandResult(hand_id, [pid for pid, amount in payouts.items() if amount > 0],
        #                    payouts, starting, ending, board, revealed, actions, pot_log, result_reason)
        contributions = {
            p.player_id: p.hand_contribution
            for p in self.players
        }

        result = HandResult(
            hand_id=hand_id,
            winners=[pid for pid, amount in payouts.items() if amount > 0],
            payouts=payouts,
            starting_stacks=starting,
            ending_stacks=ending,
            contributions=contributions,
            board=board,
            revealed_hole_cards=revealed,
            actions=actions,
            pots=pot_log,
            reason=result_reason,
        )

        self.history.append(self._result_to_dict(result))
        return result

    @staticmethod
    def _should_run_betting_round(
        contenders: list[PlayerState],
        round_state: BettingRound,
    ) -> bool:
        actionable = [
            p for p in contenders
            if not p.folded and not p.all_in and p.stack > 0
        ]
        if len(actionable) >= 2:
            return True
        # Even when everyone else is all-in, a player who owes chips must
        # still be able to call or fold (for example, facing an all-in raise).
        return any(p.street_bet < round_state.current_bet for p in actionable)

    def _betting_loop(self, round_state: BettingRound, order: list[int], hand_id: str,
                      street: str, board: list[Card], actions: list[dict[str, Any]]) -> None:
        # Action loop continues until every non-folded, non-all-in player has matched current bet
        # and acted since the last full raise.
        pending = [i for i in order if not self.players[i].folded and not self.players[i].all_in]
        cursor = 0
        safety = 0
        while pending and safety < 1000:
            # A hand ends immediately when everyone but one player has folded.
            # Do not ask the remaining player to act (e.g. the BB after the SB folds).
            if sum(1 for player in self.players if not player.folded) <= 1:
                break
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
            requested_action = module.decide(context)

            # アクション直前の状態を保存
            stack_before = p.stack
            street_bet_before = p.street_bet
            current_bet_before = round_state.current_bet
            to_call_before = max(0, current_bet_before - street_bet_before)
            legal_before = round_state.legal_actions(p)

            action = requested_action
            invalid_reason = None
            fallback_type = None

            try:
                round_state.apply(p, action)
            except ValueError as exc:
                invalid_reason = str(exc)

                # 合法なアクションに置き換えて対戦を継続
                legal = round_state.legal_actions(p)
                if legal.can_check:
                    action = Action.check()
                elif legal.can_call:
                    action = Action.call()
                elif legal.can_fold:
                    action = Action.fold()
                else:
                    raise RuntimeError(
                        f"No legal fallback for player {p.player_id}"
                    ) from exc

                fallback_type = action.type
                round_state.apply(p, action)

            # 実行結果を1レコードにまとめて記録
            record = {
                "player_id": p.player_id,
                "street": street,
                "action": action.type,
                "amount": action.amount,
                "stack_before": stack_before,
                "stack_after": p.stack,
                "street_bet_before": street_bet_before,
                "street_bet_after": p.street_bet,
                "current_bet_before": current_bet_before,
                "current_bet_after": round_state.current_bet,
                "to_call_before": to_call_before,
                "legal_before": {
                    key: getattr(legal_before, key)
                    for key in legal_before.__dataclass_fields__
                },
            }

            if invalid_reason is not None:
                record["requested_action"] = repr(requested_action)
                record["invalid_reason"] = invalid_reason
                record["fallback"] = fallback_type

            actions.append(record)


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
                          legal, tuple(dict(a) for a in actions),
                          max(1, sum(
                              not other.folded
                              for other in self.players
                              if other.player_id != p.player_id
                          )))

    @staticmethod
    def position_names(player_count: int) -> list[str]:
        names = {
            2: ["BTN/SB", "BB"],
            3: ["BTN", "SB", "BB"],
            4: ["BTN", "SB", "BB", "CO"],
            5: ["BTN", "SB", "BB", "UTG", "CO"],
            6: ["BTN", "SB", "BB", "UTG", "MP", "CO"],
            7: ["BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"],
            8: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
            9: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"],
        }
        try:
            return names[player_count]
        except KeyError as exc:
            raise ValueError("player_count must be between 2 and 9") from exc

    def position_map(self) -> dict[int, str]:
        active = self.active_seats or [p.seat for p in self.players if p.stack > 0]
        if not active:
            return {}
        order = self._seat_order_from(self.button, active)
        names = self.position_names(len(order))
        return {seat: names[index] for index, seat in enumerate(order)}

    def _position(self, seat: int) -> str:
        return self.position_map().get(seat, f"Seat{seat+1}")

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
            "contributions": r.contributions,
            "board": [str(c) for c in r.board],
            "revealed_hole_cards": {k: [str(c) for c in v] for k, v in r.revealed_hole_cards.items()},
            "actions": r.actions, "pots": r.pots, "reason": r.reason,
        }
