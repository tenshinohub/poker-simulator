"""State-transition regression tests for poker betting rounds."""
import unittest

from poker_sim.domain.actions import Action
from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound


class BettingStateTransitionTests(unittest.TestCase):
    def make_players(self, stacks=(500, 500, 500)):
        return [PlayerState(f"p{i+1}", f"P{i+1}", stack, i)
                for i, stack in enumerate(stacks)]

    def assert_state_consistent(self, players, initial_total):
        self.assertEqual(
            sum(p.stack + p.hand_contribution for p in players), initial_total
        )
        for player in players:
            self.assertGreaterEqual(player.stack, 0)
            self.assertGreaterEqual(player.street_bet, 0)
            self.assertGreaterEqual(player.hand_contribution, player.street_bet)
            if player.all_in:
                self.assertEqual(player.stack, 0)

    def test_check_check_leaves_round_at_zero_and_marks_both_acted(self):
        players = self.make_players((100, 100))
        round_state = BettingRound(players, big_blind=10)

        round_state.apply(players[0], Action.check())
        round_state.apply(players[1], Action.check())

        self.assertEqual(round_state.current_bet, 0)
        self.assertEqual(round_state.acted_since_full_raise, {"p1", "p2"})
        self.assert_state_consistent(players, 200)

    def test_bet_call_updates_stack_contribution_and_legal_actions(self):
        players = self.make_players((100, 100))
        round_state = BettingRound(players, big_blind=10)

        round_state.apply(players[0], Action.bet_to(20))
        self.assertEqual(round_state.current_bet, 20)
        self.assertEqual(players[0].stack, 80)
        self.assertTrue(round_state.legal_actions(players[1]).can_call)
        self.assertEqual(round_state.legal_actions(players[1]).call_amount, 20)

        round_state.apply(players[1], Action.call())
        self.assertEqual(players[1].street_bet, 20)
        self.assertEqual(players[1].hand_contribution, 20)
        # Both players have matched the bet; the original bettor does not owe chips.
        self.assertEqual(players[0].street_bet, round_state.current_bet)
        self.assertEqual(players[1].street_bet, round_state.current_bet)
        self.assert_state_consistent(players, 200)

    def test_full_raise_requires_other_players_to_respond_again(self):
        players = self.make_players((500, 500, 500))
        round_state = BettingRound(players, big_blind=10, current_bet=10)
        for player in players:
            player.street_bet = 10
            player.hand_contribution = 10
        round_state = BettingRound(players, big_blind=10, current_bet=10)

        round_state.apply(players[0], Action.raise_to(30))
        self.assertEqual(round_state.last_full_raise, 20)
        self.assertEqual(round_state.acted_since_full_raise, {"p1"})
        self.assertTrue(round_state.legal_actions(players[1]).can_call)
        self.assertEqual(round_state.legal_actions(players[1]).call_amount, 20)
        self.assert_state_consistent(players, 1530)

    def test_fold_removes_player_from_contenders_without_refunding_contribution(self):
        players = self.make_players((100, 100, 100))
        round_state = BettingRound(players, big_blind=10)
        round_state.apply(players[0], Action.bet_to(20))
        round_state.apply(players[1], Action.fold())

        self.assertTrue(players[1].folded)
        self.assertEqual(players[1].hand_contribution, 0)
        self.assertEqual(players[0].street_bet, 20)
        self.assert_state_consistent(players, 300)

    def test_short_all_in_does_not_change_minimum_full_raise_size(self):
        a = PlayerState("a", "A", 500, 0, street_bet=100, hand_contribution=100)
        b = PlayerState("b", "B", 50, 1, street_bet=100, hand_contribution=100)
        round_state = BettingRound([a, b], big_blind=100, current_bet=100)

        round_state.apply(a, Action.check())
        round_state.apply(b, Action.all_in())

        self.assertEqual(round_state.current_bet, 150)
        self.assertEqual(round_state.last_full_raise, 100)
        self.assertFalse(round_state.legal_actions(a).can_raise)
        self.assert_state_consistent([a, b], 750)

    def test_illegal_action_does_not_mutate_player_or_round_state(self):
        players = [
            PlayerState("p1", "P1", 100, 0),
            PlayerState("p2", "P2", 90, 1, street_bet=10, hand_contribution=10),
        ]
        round_state = BettingRound(players, big_blind=10, current_bet=10)
        before = (players[0].stack, players[0].street_bet,
                  players[0].hand_contribution, round_state.current_bet,
                  set(round_state.acted_since_full_raise))

        with self.assertRaises(ValueError):
            round_state.apply(players[0], Action.check())

        after = (players[0].stack, players[0].street_bet,
                 players[0].hand_contribution, round_state.current_bet,
                 set(round_state.acted_since_full_raise))
        self.assertEqual(after, before)
        self.assert_state_consistent(players, 200)

    def test_all_in_call_caps_contribution_at_remaining_stack(self):
        short = PlayerState("short", "Short", 15, 0, street_bet=5, hand_contribution=5)
        bettor = PlayerState("bettor", "Bettor", 100, 1, street_bet=20, hand_contribution=20)
        round_state = BettingRound([short, bettor], big_blind=10, current_bet=20)

        round_state.apply(short, Action.call())

        self.assertEqual(short.stack, 0)
        self.assertTrue(short.all_in)
        self.assertEqual(short.street_bet, 20)
        self.assertEqual(short.hand_contribution, 20)
        self.assert_state_consistent([short, bettor], 140)


if __name__ == "__main__":
    unittest.main()
