import unittest

from poker_sim.llm.validation import validate_analysis


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "hand_id": "h1",
            "board": ["As", "Kd", "Qc", "Jh", "Ts"],
            "revealed_hole_cards": {"p1": ["Ah", "Ad"]},
            "winners": ["p1"],
            "payouts": {"p1": 30, "p2": 0},
            "starting_stacks": {"p1": 100, "p2": 100},
            "ending_stacks": {"p1": 120, "p2": 80},
            "contributions": {"p1": 10, "p2": 20},
            "actions": [
                {"player_id": "p1", "street": "preflop", "action": "call", "amount": None},
                {"event": "showdown_decision", "player_id": "p1", "decision": "show", "won": True},
                {"event": "showdown_decision", "player_id": "p2", "decision": "show", "won": False},
            ],
            "pots": [{"amount": 30, "eligible": ["p1", "p2"], "winners": ["p1"], "payouts": {"p1": 30}}],
            "reason": "showdown",
        }
        self.facts = {
            key: self.source[key]
            for key in ("board", "revealed_hole_cards", "winners", "payouts", "contributions",
                        "ending_stacks", "pots", "reason")
        }
        self.facts["actions"] = [
            {"player_id": "p1", "street": "preflop", "action": "call", "amount": None}
        ]
        self.facts["showdown_decisions"] = [
            {"player_id": "p1", "decision": "show", "won": True},
            {"player_id": "p2", "decision": "show", "won": False},
        ]

    def test_all_structured_facts_and_events_match(self):
        report = validate_analysis(self.source, {"analysis": {"facts": self.facts}})
        self.assertEqual(report["summary"]["fail"], 0)
        self.assertEqual(report["summary"]["not_reported"], 0)

    def test_wrong_winner_is_detected(self):
        facts = dict(self.facts, winners=["p2"])
        report = validate_analysis(self.source, {"analysis": {"facts": facts}})
        winner = next(check for check in report["checks"] if check["field"] == "winners")
        self.assertEqual(winner["status"], "fail")

    def test_missing_facts_are_not_reported_not_failures(self):
        report = validate_analysis(self.source, {"analysis": {"summary": "short recap"}})
        self.assertEqual(report["summary"]["not_reported"], 10)
        self.assertEqual(report["summary"]["fail"], 0)

    def test_missing_showdown_decisions_are_not_reported(self):
        facts = dict(self.facts)
        facts.pop("showdown_decisions")
        report = validate_analysis(self.source, {"analysis": {"facts": facts}})
        check = next(item for item in report["checks"] if item["field"] == "showdown_decisions")
        self.assertEqual(check["status"], "not_reported")

    def test_wrong_showdown_decision_is_detected(self):
        facts = dict(self.facts)
        facts["showdown_decisions"] = [
            {"player_id": "p1", "decision": "show", "won": False},
            {"player_id": "p2", "decision": "show", "won": False},
        ]
        report = validate_analysis(self.source, {"analysis": {"facts": facts}})
        check = next(item for item in report["checks"] if item["field"] == "showdown_decisions")
        self.assertEqual(check["status"], "fail")


if __name__ == "__main__":
    unittest.main()
