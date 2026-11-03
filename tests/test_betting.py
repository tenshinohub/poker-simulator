import unittest
from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound
from poker_sim.domain.actions import Action

class BettingTests(unittest.TestCase):
    def test_check_and_call_legality(self):
        a = PlayerState("a", "A", 100, 0)
        b = PlayerState("b", "B", 100, 1)
        round_ = BettingRound([a, b], big_blind=10, current_bet=0)
        self.assertTrue(round_.legal_actions(a).can_check)
        round_.apply(a, Action.bet_to(10))
        self.assertTrue(round_.legal_actions(b).can_call)
        round_.apply(b, Action.call())
        self.assertEqual(b.street_bet, 10)

    def test_illegal_check_rejected_when_facing_bet(self):
        a = PlayerState("a", "A", 100, 0)
        b = PlayerState("b", "B", 100, 1)
        r = BettingRound([a, b], 10, 10)
        with self.assertRaises(ValueError):
            r.apply(a, Action.check())

    def test_raise_not_legal_when_no_bet_exists(self):
        from poker_sim.engine.betting import BettingRound
        from poker_sim.domain.models import PlayerState

        player = PlayerState(
            player_id="p1",
            name="Player 1",
            seat=0,
            stack=1000,
        )
        round_state = BettingRound(
            players=[player],
            big_blind=10,
            current_bet=0,
        )

        legal = round_state.legal_actions(player)

        self.assertFalse(legal.can_raise)
        self.assertTrue(legal.can_bet)
    
    def test_uncalled_bet_is_refunded(self):
        a = PlayerState("a", "A", 100, 0)
        b = PlayerState("b", "B", 100, 1)

        round_ = BettingRound(
            [a, b],
            big_blind=10,
            current_bet=0,
        )

        # ラウンド開始後にベットが行われた状態を再現
        a.stack = 0
        a.street_bet = 100
        a.hand_contribution = 100
        a.all_in = True

        b.street_bet = 60
        b.hand_contribution = 60

        round_.current_bet = 100
        round_.last_aggressor_id = "a"

        refunded = round_.refund_uncalled_bet()

        self.assertEqual(refunded, 40)
        self.assertEqual(a.stack, 40)
        self.assertEqual(a.street_bet, 60)
        self.assertEqual(a.hand_contribution, 60)
        self.assertFalse(a.all_in)


    def test_single_short_all_in_does_not_reopen_raise(self):
        a = PlayerState("a", "A", 500, 0)
        b = PlayerState("b", "B", 50, 1)
        a.street_bet = 100
        a.hand_contribution = 100
        b.street_bet = 100
        b.hand_contribution = 100
        r = BettingRound([a, b], big_blind=100, current_bet=100)

        # A has already responded to the 100 bet.
        r.apply(a, Action.check())
        r.apply(b, Action.all_in())  # short raise to 150

        self.assertEqual(r.current_bet, 150)
        self.assertFalse(r.legal_actions(a).can_raise)

    def test_cumulative_short_all_ins_reopen_raise_right(self):
        a = PlayerState("a", "A", 500, 0)
        b = PlayerState("b", "B", 50, 1)
        c = PlayerState("c", "C", 50, 2)
        a.street_bet = 100
        a.hand_contribution = 100
        b.street_bet = 100
        b.hand_contribution = 100
        c.street_bet = 150
        c.hand_contribution = 150
        r = BettingRound([a, b, c], big_blind=100, current_bet=100)

        # A has acted at 100. B raises all-in to 150; C raises all-in to 200.
        r.apply(a, Action.check())
        r.apply(b, Action.all_in())
        r.apply(c, Action.all_in())

        self.assertEqual(r.current_bet, 200)
        self.assertTrue(r.legal_actions(a).can_raise)
        self.assertEqual(r.legal_actions(a).min_raise_to, 300)

    def test_no_refund_when_bets_are_matched(self):
        a = PlayerState("a", "A", 0, 0)
        b = PlayerState("b", "B", 0, 1)

        a.street_bet = 100
        a.hand_contribution = 100
        a.all_in = True

        b.street_bet = 100
        b.hand_contribution = 100
        b.all_in = True

        round_ = BettingRound(
            [a, b],
            big_blind=10,
            current_bet=100,
        )
        round_.last_aggressor_id = "a"

        refunded = round_.refund_uncalled_bet()

        self.assertEqual(refunded, 0)
        self.assertEqual(a.street_bet, 100)
        self.assertEqual(a.hand_contribution, 100)


    def test_no_refund_when_only_blinds_were_posted(self):
        sb = PlayerState("sb", "Small Blind", 95, 0)
        bb = PlayerState("bb", "Big Blind", 90, 1)

        sb.street_bet = 5
        sb.hand_contribution = 5
        bb.street_bet = 10
        bb.hand_contribution = 10

        round_ = BettingRound(
            [sb, bb],
            big_blind=10,
            current_bet=10,
        )

        refunded = round_.refund_uncalled_bet()

        self.assertEqual(refunded, 0)
        self.assertEqual(bb.stack, 90)
        self.assertEqual(bb.street_bet, 10)

if __name__ == "__main__": unittest.main()
