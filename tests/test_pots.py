import unittest
from poker_sim.engine.pots import build_side_pots, split_amount, validate_pots, Pot

class PotTests(unittest.TestCase):
    def test_side_pots(self):
        pots = build_side_pots({"a": 100, "b": 200, "c": 300}, set())
        self.assertEqual([p.amount for p in pots], [300, 200, 100])
        self.assertEqual(pots[0].eligible, ("a", "b", "c"))
        self.assertEqual(pots[1].eligible, ("b", "c"))
        self.assertEqual(pots[2].eligible, ("c",))

    def test_folded_contribution_remains_in_pot(self):
        pots = build_side_pots({"a": 100, "b": 200, "c": 200}, {"a"})
        self.assertEqual(pots[0].amount, 300)
        self.assertEqual(pots[0].eligible, ("b", "c"))

    def test_odd_chip(self):
        self.assertEqual(split_amount(5, ["b", "a"], ["a", "b"]), {"a": 3, "b": 2})

    
    def test_split_amount_rejects_invalid_amount(self):
        for amount in (-1, 1.5, True):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    split_amount(amount, ["a"], ["a"])

    def test_split_amount_rejects_empty_winners(self):
        with self.assertRaises(ValueError):
            split_amount(10, [], ["a", "b"])

    def test_split_amount_rejects_duplicate_winners(self):
        with self.assertRaises(ValueError):
            split_amount(10, ["a", "a"], ["a", "b"])

    def test_split_amount_rejects_duplicate_seat_order(self):
        with self.assertRaises(ValueError):
            split_amount(10, ["a"], ["a", "a"])

    def test_split_amount_rejects_winner_missing_from_seat_order(self):
        with self.assertRaises(ValueError):
            split_amount(10, ["a", "c"], ["a", "b"])

    def test_split_amount_even_split(self):
        self.assertEqual(
            split_amount(12, ["a", "b", "c"], ["a", "b", "c"]),
            {"a": 4, "b": 4, "c": 4},
        )

    def test_split_amount_multiple_odd_chips(self):
        self.assertEqual(
            split_amount(8, ["c", "a", "b"], ["a", "b", "c"]),
            {"a": 3, "b": 3, "c": 2},
        )

    def test_side_pots_with_folded_contributor_at_highest_level(self):
        pots = build_side_pots(
            {"a": 100, "b": 200, "c": 300},
            {"c"},
        )

        self.assertEqual([p.amount for p in pots], [300, 200, 100])
        self.assertEqual(pots[0].eligible, ("a", "b"))
        self.assertEqual(pots[1].eligible, ("b",))
        self.assertEqual(pots[2].eligible, ())

    def test_side_pot_amounts_conserve_contributions(self):
        contributions = {"a": 75, "b": 150, "c": 150, "d": 250}
        pots = build_side_pots(contributions, {"d"})

        self.assertEqual(
            sum(p.amount for p in pots),
            sum(contributions.values()),
        )
        self.assertEqual([p.amount for p in pots], [300, 225, 100])
    
    def test_validate_pots_rejects_empty_eligible(self):
        pots = build_side_pots(
            {"a": 100, "b": 200, "c": 300},
            {"c"},
        )

        with self.assertRaisesRegex(ValueError, "no eligible players"):
            validate_pots(pots)

    def test_validate_pots_accepts_valid_pots(self):
        pots = build_side_pots(
            {"a": 100, "b": 200, "c": 300},
            set(),
        )

        validate_pots(pots)  # 例外が発生しなければ成功

    def test_validate_pots_rejects_non_positive_amount(self):
        with self.assertRaisesRegex(ValueError, "invalid amount"):
            validate_pots([Pot(amount=0, eligible=("a",))])

    def test_validate_pots_rejects_duplicate_eligible_players(self):
        with self.assertRaisesRegex(ValueError, "duplicate eligible"):
            validate_pots([Pot(amount=10, eligible=("a", "a"))])


if __name__ == "__main__": unittest.main()
