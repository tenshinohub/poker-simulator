import unittest
from poker_sim.engine.game import Game, GameConfig
from poker_sim.players.rule_agent import RuleBasedAgent
from poker_sim.players.random_agent import RandomAgent

class GameTests(unittest.TestCase):
    def test_one_hand_conserves_chips(self):
        players = [RuleBasedAgent("A"), RandomAgent("B", 2), RuleBasedAgent("C")]
        game = Game(players, GameConfig(starting_stack=500, max_hands=5), seed=42)
        before = sum(p.stack for p in game.players)
        result = game.play_hand()
        after = sum(p.stack for p in game.players)
        self.assertEqual(before, after)
        self.assertEqual(len(result.board), 5)
        self.assertTrue(result.payouts)

    def test_seed_reproduces_first_board(self):
        def run():
            game = Game([RuleBasedAgent("A"), RuleBasedAgent("B")],
                        GameConfig(starting_stack=100), seed=77)
            return [str(c) for c in game.play_hand().board]
        self.assertEqual(run(), run())

if __name__ == "__main__": unittest.main()
