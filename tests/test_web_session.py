import unittest

from poker_sim.web.session import GameSession


class BrowserSessionTests(unittest.TestCase):
    def test_session_publishes_human_turn_with_private_cards_and_legal_actions(self):
        session = GameSession(player_count=2, starting_stack=200,
                              small_blind=5, big_blind=10, seed=123)
        event = session.get_event(timeout=3)
        self.assertEqual(event["type"], "your_turn")
        self.assertEqual(event["street"], "preflop")
        self.assertEqual(len(event["hole_cards"]), 2)
        self.assertEqual(len(event["players"]), 2)
        self.assertTrue(event["legal_actions"]["can_call"])
        # Opponent hole cards are never included in a live decision event.
        self.assertNotIn("hole_cards", event["players"][1])

    def test_human_action_advances_to_next_decision(self):
        session = GameSession(player_count=2, starting_stack=200,
                              small_blind=5, big_blind=10, seed=123)
        first = session.get_event(timeout=3)
        session.submit_action({"type": "call"})
        second = session.get_event(timeout=3)
        self.assertEqual(first["type"], "your_turn")
        self.assertEqual(second["type"], "your_turn")
        self.assertEqual(second["street"], "flop")

    def test_rejects_unknown_action(self):
        session = GameSession(player_count=2, starting_stack=200,
                              small_blind=5, big_blind=10, seed=123)
        session.get_event(timeout=3)
        with self.assertRaises(ValueError):
            session.submit_action({"type": "teleport"})

    def test_showdown_decision_accepts_only_show_or_muck(self):
        session = GameSession(player_count=2, starting_stack=200,
                              small_blind=5, big_blind=10, seed=123)
        with self.assertRaises(ValueError):
            session.submit_showdown_decision("fold")
        session.submit_showdown_decision("muck")
        self.assertEqual(session.showdown_decisions.get_nowait(), "muck")

    def test_hand_complete_includes_display_names_and_final_player_stacks(self):
        session = GameSession(player_count=2, starting_stack=200,
                              small_blind=5, big_blind=10, seed=321)
        turn = session.get_event(timeout=3)
        self.assertEqual(turn["type"], "your_turn")
        session.submit_action({"type": "fold"})
        result = session.get_event(timeout=3)
        self.assertEqual(result["type"], "hand_complete")
        self.assertEqual(result["winner_names"], [
            next(p["name"] for p in result["players"] if p["player_id"] == pid)
            for pid in result["winners"]
        ])
        human = next(p for p in result["players"] if p["is_human"])
        self.assertEqual(human["name"], "あなた")
        self.assertEqual(human["stack"], result["ending_stacks"][human["player_id"]])
        self.assertEqual(result["hole_cards"], turn["hole_cards"])
