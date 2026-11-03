import unittest

from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound
from poker_sim.engine.pots import build_side_pots, validate_pots


class RefundAndSidePotIntegrationTests(unittest.TestCase):
    def test_uncalled_all_in_refund_then_build_side_pots(self):
        # Before refund: p1 bet 300, p2 matched 200, folded p3 contributed 100.
        p1 = PlayerState("p1", "P1", 0, 0)
        p2 = PlayerState("p2", "P2", 0, 1)
        p3 = PlayerState("p3", "P3", 900, 2)
        # Construct the round before the actions, as Game does.
        round_ = BettingRound([p1, p2, p3], big_blind=10, current_bet=0)
        p1.stack = 0
        p1.street_bet = p1.hand_contribution = 300
        p1.all_in = True
        p2.stack = 0
        p2.street_bet = p2.hand_contribution = 200
        p2.all_in = True
        p3.stack = 900
        p3.street_bet = p3.hand_contribution = 100
        p3.folded = True
        round_.current_bet = 300
        round_.last_aggressor_id = "p1"

        # Total chips (stacks + contributions) before settlement.
        total_before = sum(p.stack + p.hand_contribution for p in (p1, p2, p3))

        refunded = round_.refund_uncalled_bet()

        self.assertEqual(refunded, 100)
        self.assertEqual((p1.stack, p1.street_bet, p1.hand_contribution), (100, 200, 200))
        self.assertFalse(p1.all_in)
        self.assertEqual(round_.current_bet, 200)

        pots = build_side_pots(
            {p.player_id: p.hand_contribution for p in (p1, p2, p3)},
            {p.player_id for p in (p1, p2, p3) if p.folded},
        )
        validate_pots(pots)
        self.assertEqual(
            [(pot.amount, set(pot.eligible)) for pot in pots],
            [(300, {"p1", "p2"}), (200, {"p1", "p2"})],
        )
        self.assertEqual(sum(pot.amount for pot in pots), 500)
        self.assertEqual(
            sum(p.stack + p.hand_contribution for p in (p1, p2, p3)),
            total_before,
        )

    def test_matched_all_ins_create_no_refund_and_one_pot(self):
        p1 = PlayerState("p1", "P1", 0, 0)
        p2 = PlayerState("p2", "P2", 0, 1)
        p1.street_bet = p1.hand_contribution = 200
        p2.street_bet = p2.hand_contribution = 200
        p1.all_in = p2.all_in = True

        round_ = BettingRound([p1, p2], big_blind=10, current_bet=200)
        round_.last_aggressor_id = "p1"

        self.assertEqual(round_.refund_uncalled_bet(), 0)
        pots = build_side_pots(
            {p.player_id: p.hand_contribution for p in (p1, p2)}, set()
        )
        validate_pots(pots)
        self.assertEqual(len(pots), 1)
        self.assertEqual(pots[0].amount, 400)
        self.assertEqual(set(pots[0].eligible), {"p1", "p2"})

    def test_folded_players_chips_remain_in_pot_but_not_eligible(self):
        contributions = {"p1": 100, "p2": 200, "p3": 300, "p4": 300}
        folded = {"p2"}
        pots = build_side_pots(contributions, folded)

        self.assertEqual(sum(p.amount for p in pots), sum(contributions.values()))
        validate_pots(pots)
        self.assertEqual(
            [(p.amount, set(p.eligible)) for p in pots],
            [
                (400, {"p1", "p3", "p4"}),
                (300, {"p3", "p4"}),
                (200, {"p3", "p4"}),
            ],
        )
        self.assertTrue(all("p2" not in p.eligible for p in pots))


if __name__ == "__main__":
    unittest.main()
