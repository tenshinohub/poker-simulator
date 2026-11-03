from __future__ import annotations
from dataclasses import dataclass, field
from ..domain.actions import Action
from ..domain.models import PlayerState, LegalActions

@dataclass
class BettingRound:
    players: list[PlayerState]
    big_blind: int
    current_bet: int = 0
    last_full_raise: int = 0
    acted_since_full_raise: set[str] | None = None
    last_aggressor_id: str | None = None
    street_bets_at_start: dict[str, int] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )
    last_action_bet: dict[str, int] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.acted_since_full_raise is None:
            self.acted_since_full_raise = set()
        if self.last_full_raise == 0:
            self.last_full_raise = self.big_blind
        # ブラインドなど、ラウンド開始時点のベット額を保存
        self.street_bets_at_start = {
            p.player_id: p.street_bet
            for p in self.players
        }
        # Track the bet level each player had most recently responded to.
        # This lets cumulative short all-in raises reopen action correctly.
        self.last_action_bet = {
            p.player_id: p.street_bet
            for p in self.players
        }

    def legal_actions(self, p: PlayerState) -> LegalActions:
        to_call = max(0, self.current_bet - p.street_bet)
        max_to = p.street_bet + p.stack
        can_act = not p.folded and not p.all_in and p.stack > 0
        has_acted = p.player_id in (self.acted_since_full_raise or set())
        last_action_bet = self.last_action_bet.get(p.player_id, p.street_bet)
        can_raise_right = (
            not has_acted
            or self.current_bet - last_action_bet >= self.last_full_raise
        )
        #can_raise = can_act and can_raise_right and max_to > self.current_bet
        can_raise = (
            can_act
            and can_raise_right
            and self.current_bet > 0
            and max_to > self.current_bet
        )
        can_bet = can_act and self.current_bet == 0
        min_bet_to = self.big_blind if can_bet else None
        min_raise_to = (self.current_bet + self.last_full_raise) if can_raise and self.current_bet > 0 else None
        # If all-in is below minimum raise, it is still legal as an all-in action.
        return LegalActions(
            can_fold=can_act,
            can_check=can_act and to_call == 0,
            can_call=can_act and to_call > 0,
            call_amount=min(to_call, p.stack),
            can_bet=can_bet and max_to >= self.big_blind,
            min_bet_to=min_bet_to,
            can_raise=can_raise and max_to >= (min_raise_to or self.current_bet + self.last_full_raise),
            min_raise_to=min_raise_to,
            max_raise_to=max_to,
            can_all_in=can_act,
        )

    def apply(self, p: PlayerState, action: Action) -> None:
        legal = self.legal_actions(p)
        if action.type == "fold":
            if not legal.can_fold: raise ValueError("Fold is not legal")
            p.folded = True
            self.acted_since_full_raise.add(p.player_id)
            self.last_action_bet[p.player_id] = self.current_bet
            return
        if action.type == "check":
            if not legal.can_check: raise ValueError("Check is not legal")
            self.acted_since_full_raise.add(p.player_id)
            self.last_action_bet[p.player_id] = self.current_bet
            return
        if action.type == "call":
            if not legal.can_call: raise ValueError("Call is not legal")
            self._put_chips(p, min(self.current_bet - p.street_bet, p.stack))
            self.acted_since_full_raise.add(p.player_id)
            self.last_action_bet[p.player_id] = self.current_bet
            return
        if action.type == "all_in":
            if not legal.can_all_in: raise ValueError("All-in is not legal")
            old_bet = self.current_bet
            target = p.street_bet + p.stack
            self._put_chips(p, p.stack)
            if target > old_bet:
                raise_size = target - old_bet
                self.current_bet = target
                self.last_aggressor_id = p.player_id
                if raise_size >= self.last_full_raise:
                    self.last_full_raise = raise_size
                    self.acted_since_full_raise = {p.player_id}
                else:
                    self.acted_since_full_raise.add(p.player_id)
            else:
                self.acted_since_full_raise.add(p.player_id)
            self.last_action_bet[p.player_id] = self.current_bet
            return
        if action.type in {"bet", "raise"}:
            target = action.amount
            if target is None or target > p.street_bet + p.stack:
                raise ValueError("Bet target exceeds stack")
            if self.current_bet == 0:
                if action.type != "bet" or not legal.can_bet or target < self.big_blind:
                    raise ValueError("Invalid bet")
                old_bet = self.current_bet
            else:
                if action.type != "raise" or not legal.can_raise or target <= self.current_bet:
                    raise ValueError("Invalid raise")
                min_to = self.current_bet + self.last_full_raise
                if target < min_to and target != p.street_bet + p.stack:
                    raise ValueError("Raise is below the minimum")
                old_bet = self.current_bet
            delta = target - p.street_bet
            if delta <= 0: raise ValueError("Bet/raise must add chips")
            self._put_chips(p, delta)
            raise_size = target - old_bet
            self.last_aggressor_id = p.player_id
            self.current_bet = target
            if raise_size >= self.last_full_raise:
                self.last_full_raise = raise_size
                self.acted_since_full_raise = {p.player_id}
            else:
                self.acted_since_full_raise.add(p.player_id)
            self.last_action_bet[p.player_id] = self.current_bet
            return
        raise ValueError(f"Unsupported action: {action.type}")

    @staticmethod
    def _put_chips(p: PlayerState, amount: int) -> None:
        if amount < 0 or amount > p.stack:
            raise ValueError("Invalid chip amount")
        p.stack -= amount
        p.street_bet += amount
        p.hand_contribution += amount
        if p.stack == 0:
            p.all_in = True

    def refund_uncalled_bet(self) -> int:
        """Refund the unmatched portion of the last aggressor's bet."""
        if self.last_aggressor_id is None:
            return 0

        aggressor = next(
            (
                p for p in self.players
                if p.player_id == self.last_aggressor_id
            ),
            None,
        )

        if aggressor is None or aggressor.folded:
            return 0

        highest_other_bet = max(
            (
                p.street_bet
                for p in self.players
                if p.player_id != aggressor.player_id
            ),
            default=0,
        )

        # ラウンド開始時の強制ベットなどは返金対象にしない
        initial_bet = self.street_bets_at_start.get(
            aggressor.player_id, 0
        )
        matched_amount = max(highest_other_bet, initial_bet)

        refund = aggressor.street_bet - matched_amount
        if refund <= 0:
            return 0

        aggressor.stack += refund
        aggressor.street_bet -= refund
        aggressor.hand_contribution -= refund

        if aggressor.stack > 0:
            aggressor.all_in = False

        self.current_bet = max(
            (p.street_bet for p in self.players),
            default=0,
        )

        return refund
