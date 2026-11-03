import unittest

from poker_sim.engine.game import Game
from poker_sim.web.session import GameSession


class BrowserPositionTests(unittest.TestCase):
    def test_position_names_cover_two_through_nine_players(self):
        self.assertEqual(Game.position_names(2), ["BTN/SB", "BB"])
        self.assertEqual(Game.position_names(6), ["BTN", "SB", "BB", "UTG", "MP", "CO"])
        self.assertEqual(Game.position_names(9), ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"])

    def test_first_six_max_hand_places_human_in_mp_not_button(self):
        session = GameSession(6, 1000, 5, 10, seed=20261031)
        event = session.get_event(timeout=5)
        self.assertEqual(event["type"], "your_turn")
        self.assertEqual(event["human_position"], "MP")
        human = next(p for p in event["players"] if p["is_human"])
        button = next(p for p in event["players"] if p["is_button"])
        self.assertEqual(human["position"], "MP")
        self.assertFalse(human["is_button"])
        self.assertEqual(button["position"], "BTN")
        self.assertEqual(human["action_status"], "YOUR TURN")

    def test_short_handed_table_uses_button_when_mp_does_not_exist(self):
        session = GameSession(2, 1000, 5, 10, seed=7)
        event = session.get_event(timeout=5)
        self.assertEqual(event["type"], "your_turn")
        human = next(p for p in event["players"] if p["is_human"])
        self.assertEqual(human["position"], "BTN/SB")
        self.assertTrue(human["is_button"])


if __name__ == "__main__":
    unittest.main()
