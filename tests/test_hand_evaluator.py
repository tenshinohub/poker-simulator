import unittest
from poker_sim.domain.cards import Card
from poker_sim.engine.hand_evaluator import evaluate_five, evaluate_hand

def cards(*xs): return [Card.parse(x) for x in xs]

class EvaluatorTests(unittest.TestCase):
    def test_royal_flush_beats_four_kind(self):
        royal = evaluate_five(cards("As", "Ks", "Qs", "Js", "Ts"))
        quads = evaluate_five(cards("Ac", "Ad", "Ah", "As", "Kd"))
        self.assertGreater(royal, quads)

    def test_wheel_straight(self):
        self.assertEqual(evaluate_five(cards("As", "2d", "3h", "4c", "5s")), (4, 5))

    def test_full_house_uses_best_trips_and_pair(self):
        score = evaluate_hand(cards("As", "Ad", "Ah", "Ks", "Kd", "Kc", "2s"))
        self.assertEqual(score, (6, 14, 13))

    def test_duplicate_cards_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_hand(cards("As", "As", "2h", "3c", "4d"))

if __name__ == "__main__": unittest.main()
