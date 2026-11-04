import unittest
from poker_sim.llm.validation import validate_analysis


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "hand_id": "h1", "board": ["As", "Kd", "Qc", "Jh", "Ts"],
            "revealed_hole_cards": {"p1": ["Ah", "Ad"]},
            "winners": ["p1"], "payouts": {"p1": 30, "p2": 0},
            "starting_stacks": {"p1": 100, "p2": 100},
            "ending_stacks": {"p1": 120, "p2": 80},
            "contributions": {"p1": 10, "p2": 20},
            "actions": [{"player_id": "p1", "street": "preflop", "action": "call", "amount": None}],
            "pots": [{"amount": 30, "eligible": ["p1", "p2"], "winners": ["p1"], "payouts": {"p1": 30}}],
            "reason": "showdown",
        }
        self.facts = {k: self.source[k] for k in (
            "board", "revealed_hole_cards", "winners", "payouts", "contributions",
            "ending_stacks", "actions", "pots", "reason")}

    def test_all_structured_facts_match(self):
        report = validate_analysis(self.source, {"analysis": {"facts": self.facts}})
        self.assertEqual(report["summary"]["fail"], 0)
        self.assertEqual(report["summary"]["not_reported"], 0)

    def test_wrong_winner_is_detected(self):
        facts = dict(self.facts, winners=["p2"])
        report = validate_analysis(self.source, {"analysis": {"facts": facts}})
        winner = next(x for x in report["checks"] if x["field"] == "winners")
        self.assertEqual(winner["status"], "fail")

    def test_missing_fact_is_not_reported_not_failure(self):
        report = validate_analysis(self.source, {"analysis": {"summary": "short recap"}})
        self.assertEqual(report["summary"]["not_reported"], 9)
        self.assertEqual(report["summary"]["fail"], 0)


if __name__ == "__main__":
    unittest.main()
