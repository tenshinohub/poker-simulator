import unittest

from poker_sim.engine.pots import build_side_pots, validate_pots


class PotBoundaryTests(unittest.TestCase):
    def test_equal_contributions_create_one_pot(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 100, "p3": 100},
            set(),
        )

        self.assertEqual(len(pots), 1)
        self.assertEqual(pots[0].amount, 300)
        self.assertEqual(set(pots[0].eligible), {"p1", "p2", "p3"})

    def test_folded_player_contribution_remains_in_pot(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 100, "p3": 100},
            {"p3"},
        )

        self.assertEqual(len(pots), 1)
        self.assertEqual(pots[0].amount, 300)
        self.assertEqual(set(pots[0].eligible), {"p1", "p2"})
        self.assertNotIn("p3", pots[0].eligible)

    def test_multiple_side_pots(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 200, "p3": 300},
            set(),
        )

        self.assertEqual(
            [(p.amount, set(p.eligible)) for p in pots],
            [
                (300, {"p1", "p2", "p3"}),
                (200, {"p2", "p3"}),
                (100, {"p3"}),
            ],
        )
        self.assertEqual(sum(p.amount for p in pots), 600)

    def test_four_players_with_different_contributions(self):
        pots = build_side_pots(
            {"p1": 50, "p2": 100, "p3": 150, "p4": 150},
            set(),
        )

        self.assertEqual(
            [(p.amount, set(p.eligible)) for p in pots],
            [
                (200, {"p1", "p2", "p3", "p4"}),
                (150, {"p2", "p3", "p4"}),
                (100, {"p3", "p4"}),
            ],
        )
        self.assertEqual(sum(p.amount for p in pots), 450)

    def test_zero_contributions_create_no_pots(self):
        pots = build_side_pots(
            {"p1": 0, "p2": 0, "p3": 0},
            set(),
        )

        self.assertEqual(pots, [])

    def test_zero_contributor_is_not_eligible(self):
        pots = build_side_pots(
            {"p1": 0, "p2": 100, "p3": 100},
            set(),
        )

        self.assertEqual(len(pots), 1)
        self.assertEqual(pots[0].amount, 200)
        self.assertEqual(set(pots[0].eligible), {"p2", "p3"})
        self.assertNotIn("p1", pots[0].eligible)

    def test_folded_highest_contributor_creates_invalid_pot(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 200, "p3": 300},
            {"p3"},
        )

        # This input produces a layer with no eligible player.
        # It must not proceed to normal pot distribution.
        self.assertTrue(any(not p.eligible for p in pots))

        with self.assertRaises(ValueError):
            validate_pots(pots)

    def test_folded_player_at_shared_highest_level(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 200, "p3": 200},
            {"p3"},
        )

        self.assertEqual(
            [(p.amount, set(p.eligible)) for p in pots],
            [
                (300, {"p1", "p2"}),
                (200, {"p2"}),
            ],
        )
        self.assertEqual(sum(p.amount for p in pots), 500)

    def test_folded_player_at_middle_contribution_level(self):
        pots = build_side_pots(
            {"p1": 100, "p2": 200, "p3": 300, "p4": 300},
            {"p2"},
        )

        self.assertEqual(
            [(p.amount, set(p.eligible)) for p in pots],
            [
                (400, {"p1", "p3", "p4"}),
                (300, {"p3", "p4"}),
                (200, {"p3", "p4"}),
            ],
        )
        self.assertEqual(sum(p.amount for p in pots), 900)


if __name__ == "__main__":
    unittest.main()
