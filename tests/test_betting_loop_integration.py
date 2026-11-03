import unittest

from poker_sim.domain.actions import Action
from poker_sim.engine.betting import BettingRound
from poker_sim.engine.game import Game, GameConfig


class ScriptedAgent:
    def __init__(self, name, actions):
        self.name = name
        self.actions = list(actions)
        self.seen = []

    def decide(self, context):
        self.seen.append(context.observation)
        if not self.actions:
            raise AssertionError(f"{self.name} was asked to act unexpectedly")
        return self.actions.pop(0)


class BettingLoopIntegrationTests(unittest.TestCase):
    def make_game(self, scripts):
        agents = [ScriptedAgent(name, actions) for name, actions in scripts]
        game = Game(
            agents,
            GameConfig(small_blind=5, big_blind=10, starting_stack=100),
            seed=11,
        )
        round_state = BettingRound(game.players, big_blind=10, current_bet=0)
        return game, agents, round_state, []

    def run_loop(self, game, round_state, actions):
        game._betting_loop(
            round_state=round_state,
            order=[0, 1, 2],
            hand_id="integration-test",
            street="flop",
            board=[],
            actions=actions,
        )

    def test_bet_raise_call_reopens_action_in_correct_order(self):
        game, agents, round_state, history = self.make_game([
            ("A", [Action.bet_to(10), Action.call()]),
            ("B", [Action.raise_to(20)]),
            ("C", [Action.call()]),
        ])
        self.run_loop(game, round_state, history)
        self.assertEqual(
            [(row["player_id"], row["action"]) for row in history],
            [("p1", "bet"), ("p2", "raise"), ("p1", "call"), ("p3", "call")],
        )
        self.assertEqual(round_state.current_bet, 20)
        self.assertEqual([p.street_bet for p in game.players], [20, 20, 20])
        self.assertEqual([p.stack for p in game.players], [80, 80, 80])
        self.assertEqual([len(agent.seen) for agent in agents], [2, 1, 1])
        self.assertTrue(all(not agent.actions for agent in agents))

    def test_fold_after_raise_does_not_require_further_action_from_folder(self):
        game, agents, round_state, history = self.make_game([
            ("A", [Action.bet_to(10), Action.call()]),
            ("B", [Action.raise_to(20)]),
            ("C", [Action.fold()]),
        ])
        self.run_loop(game, round_state, history)
        self.assertEqual(
            [(row["player_id"], row["action"]) for row in history],
            [("p1", "bet"), ("p2", "raise"), ("p1", "call"), ("p3", "fold")],
        )
        self.assertTrue(game.players[2].folded)
        self.assertEqual(game.players[2].hand_contribution, 0)
        self.assertEqual([p.street_bet for p in game.players], [20, 20, 0])
        self.assertEqual([len(agent.seen) for agent in agents], [2, 1, 1])

    def test_check_check_check_finishes_without_reasking_players(self):
        game, agents, round_state, history = self.make_game([
            ("A", [Action.check()]),
            ("B", [Action.check()]),
            ("C", [Action.check()]),
        ])
        self.run_loop(game, round_state, history)
        self.assertEqual(
            [(row["player_id"], row["action"]) for row in history],
            [("p1", "check"), ("p2", "check"), ("p3", "check")],
        )
        self.assertEqual([len(agent.seen) for agent in agents], [1, 1, 1])
        self.assertEqual([p.street_bet for p in game.players], [0, 0, 0])

    def test_bet_then_all_other_players_fold_ends_action(self):
        game, agents, round_state, history = self.make_game([
            ("A", [Action.bet_to(10)]),
            ("B", [Action.fold()]),
            ("C", [Action.fold()]),
        ])
        self.run_loop(game, round_state, history)
        self.assertEqual(
            [(row["player_id"], row["action"]) for row in history],
            [("p1", "bet"), ("p2", "fold"), ("p3", "fold")],
        )
        self.assertFalse(game.players[0].folded)
        self.assertTrue(game.players[1].folded)
        self.assertTrue(game.players[2].folded)
        self.assertEqual(len(history), 3)


if __name__ == "__main__":
    unittest.main()
