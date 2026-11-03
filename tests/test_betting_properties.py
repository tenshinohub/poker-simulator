"""Deterministic randomized/property-style tests for betting invariants.

Uses only the standard library so the test suite has no extra dependency.
"""
import random
import unittest

from poker_sim.domain.actions import Action
from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound
from poker_sim.engine.pots import build_side_pots


class BettingPropertyTests(unittest.TestCase):
    def assert_invariants(self, players, round_state, initial_chips):
        self.assertEqual(
            sum(p.stack + p.hand_contribution for p in players), initial_chips
        )
        for player in players:
            self.assertGreaterEqual(player.stack, 0)
            self.assertGreaterEqual(player.street_bet, 0)
            self.assertGreaterEqual(player.hand_contribution, player.street_bet)
            if player.all_in:
                self.assertEqual(player.stack, 0)
        self.assertEqual(
            round_state.current_bet,
            max((p.street_bet for p in players), default=0),
        )

    @staticmethod
    def choose_legal_action(rng, player, betting_round):
        legal = betting_round.legal_actions(player)
        choices = []
        if legal.can_fold:
            choices.append("fold")
        if legal.can_check:
            choices.append("check")
        if legal.can_call:
            choices.append("call")
        if legal.can_bet:
            choices.append("bet")
        if legal.can_raise:
            choices.append("raise")
        if legal.can_all_in:
            choices.append("all_in")

        selected = rng.choice(choices)
        if selected == "fold":
            return Action.fold()
        if selected == "check":
            return Action.check()
        if selected == "call":
            return Action.call()
        if selected == "all_in":
            return Action.all_in()
        if selected == "bet":
            target = rng.randint(legal.min_bet_to, legal.max_raise_to)
            return Action.bet_to(target)
        target = rng.randint(legal.min_raise_to, legal.max_raise_to)
        return Action.raise_to(target)

    def test_randomized_legal_action_sequences_preserve_chip_invariants(self):
        # Fixed seeds make failures reproducible.
        for seed in range(250):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                count = rng.randint(2, 8)
                stacks = [rng.randint(10, 2_000) for _ in range(count)]
                players = [
                    PlayerState(f"p{i}", f"P{i}", stack, i)
                    for i, stack in enumerate(stacks)
                ]
                initial_chips = sum(stacks)
                betting_round = BettingRound(players, big_blind=10)

                # Generate a bounded sequence of legal actions. This explores
                # different bet/raise/call/fold/all-in combinations without
                # depending on external property-testing packages.
                for _ in range(40):
                    active = [p for p in players if not p.folded and not p.all_in]
                    if len(active) <= 1:
                        break
                    actor = rng.choice(active)
                    action = self.choose_legal_action(rng, actor, betting_round)
                    betting_round.apply(actor, action)
                    self.assert_invariants(players, betting_round, initial_chips)

                # Uncalled excess, if any, must be returned without changing
                # the total chips or making any contribution negative.
                betting_round.refund_uncalled_bet()
                self.assert_invariants(players, betting_round, initial_chips)

                contributions = {
                    p.player_id: p.hand_contribution for p in players
                }
                folded = {p.player_id for p in players if p.folded}
                pots = build_side_pots(contributions, folded)
                self.assertEqual(sum(p.amount for p in pots), sum(contributions.values()))
                for pot in pots:
                    self.assertGreater(pot.amount, 0)
                    # Empty eligibility is a separately validated exceptional
                    # condition (e.g. a folded player was the sole top contributor).
                    self.assertEqual(len(pot.eligible), len(set(pot.eligible)))


if __name__ == "__main__":
    unittest.main()
