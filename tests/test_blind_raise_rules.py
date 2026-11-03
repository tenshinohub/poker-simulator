import unittest

from poker_sim.domain.actions import Action
from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound


class BlindAndMinimumRaiseTests(unittest.TestCase):
    def test_big_blind_gets_option_after_preflop_calls(self):
        sb = PlayerState("sb", "Small Blind", 95, 0)
        bb = PlayerState("bb", "Big Blind", 90, 1)
        caller = PlayerState("caller", "Caller", 90, 2)
        sb.street_bet = 5
        sb.hand_contribution = 5
        bb.street_bet = 10
        bb.hand_contribution = 10
        caller.street_bet = 10
        caller.hand_contribution = 10

        round_state = BettingRound([sb, bb, caller], big_blind=10, current_bet=10)

        legal = round_state.legal_actions(bb)
        self.assertTrue(legal.can_raise)
        self.assertEqual(legal.min_raise_to, 20)

    def test_minimum_raise_is_big_blind_plus_short_big_blind_bet(self):
        short_bb = PlayerState("bb", "Short Big Blind", 0, 0)
        raiser = PlayerState("raiser", "Raiser", 100, 1)
        short_bb.street_bet = 5
        short_bb.hand_contribution = 5
        short_bb.all_in = True

        round_state = BettingRound([short_bb, raiser], big_blind=10, current_bet=5)
        legal = round_state.legal_actions(raiser)

        self.assertTrue(legal.can_raise)
        self.assertEqual(legal.min_raise_to, 15)

    def test_postflop_minimum_bet_and_raise_increment(self):
        bettor = PlayerState("bettor", "Bettor", 100, 0)
        raiser = PlayerState("raiser", "Raiser", 100, 1)
        round_state = BettingRound([bettor, raiser], big_blind=10, current_bet=0)

        self.assertTrue(round_state.legal_actions(bettor).can_bet)
        round_state.apply(bettor, Action.bet_to(10))

        legal = round_state.legal_actions(raiser)
        self.assertTrue(legal.can_raise)
        self.assertEqual(legal.min_raise_to, 20)

    def test_all_in_below_minimum_raise_remains_legal(self):
        raiser = PlayerState("raiser", "Raiser", 5, 0)
        opponent = PlayerState("opponent", "Opponent", 100, 1)
        raiser.street_bet = 10
        raiser.hand_contribution = 10
        opponent.street_bet = 10
        opponent.hand_contribution = 10
        round_state = BettingRound([raiser, opponent], big_blind=10, current_bet=10)

        legal = round_state.legal_actions(raiser)
        self.assertFalse(legal.can_raise)  # only 15 total is available; min is 20
        self.assertTrue(legal.can_all_in)
        round_state.apply(raiser, Action.all_in())
        self.assertEqual(round_state.current_bet, 15)
        self.assertEqual(raiser.stack, 0)


if __name__ == "__main__":
    unittest.main()
