import unittest
from poker_sim.domain.cards import Card
from poker_sim.engine.hand_evaluator import evaluate_five, evaluate_hand

def cards(*values): return [Card.parse(value) for value in values]

class ExtendedHandEvaluatorTests(unittest.TestCase):
    def test_all_nine_categories_are_ordered(self):
        hands=[cards("As","Kd","Qh","9c","3s"),cards("As","Ad","Qh","9c","3s"),cards("As","Ad","Qh","Qc","3s"),cards("As","Ad","Ah","9c","3s"),cards("As","2d","3h","4c","5s"),cards("As","Js","8s","5s","2s"),cards("As","Ad","Ah","Kc","Kd"),cards("As","Ad","Ah","Ac","Kd"),cards("As","Ks","Qs","Js","Ts")]
        scores=[evaluate_five(hand) for hand in hands]
        self.assertEqual([score[0] for score in scores],list(range(9)))
        self.assertEqual(scores,sorted(scores))

    def test_pair_kickers_break_ties(self):
        self.assertGreater(evaluate_five(cards("As","Ad","Kh","9c","3s")),evaluate_five(cards("Ah","Ac","Qh","9d","3c")))

    def test_two_pair_compares_top_pair_then_second_pair_then_kicker(self):
        self.assertGreater(evaluate_five(cards("As","Ad","Kh","Kc","3s")),evaluate_five(cards("Ks","Kd","Qh","Qc","As")))
        self.assertGreater(evaluate_five(cards("As","Ad","Kh","Kc","Qs")),evaluate_five(cards("Ah","Ac","Kd","Kc","Js")))

    def test_full_house_compares_trips_before_pair(self):
        self.assertGreater(evaluate_five(cards("As","Ad","Ah","2c","2d")),evaluate_five(cards("Ks","Kd","Kh","Qc","Qd")))

    def test_seven_card_hand_uses_best_five(self):
        self.assertEqual(evaluate_hand(cards("As","Ks","Qs","Js","Ts","2d","2c")),(8,14))

    def test_ace_low_straight_loses_to_six_high_straight(self):
        self.assertGreater(evaluate_five(cards("2s","3d","4h","5c","6s")),evaluate_five(cards("As","2d","3h","4c","5s")))

    def test_flush_tie_breaks_by_all_five_cards(self):
        self.assertGreater(evaluate_five(cards("As","Js","8s","5s","2s")),evaluate_five(cards("Ks","Qs","8s","5s","2s")))

if __name__=="__main__": unittest.main()
