import unittest

from poker_sim.engine.game import Game, GameConfig
from poker_sim.players.random_agent import RandomAgent


class GamePropertyTests(unittest.TestCase):
    def make_agents(self, count, seed):
        return [RandomAgent(f"R{i + 1}", seed=seed * 100 + i) for i in range(count)]

    def assert_hand_invariants(self, game, result, initial_total):
        # Chip conservation across every completed hand.
        self.assertEqual(sum(p.stack for p in game.players), initial_total)
        self.assertEqual(
            sum(result.starting_stacks.values()),
            sum(result.ending_stacks.values()),
        )

        # Per-hand contributions and payouts must balance.
        self.assertEqual(sum(result.contributions.values()), sum(result.payouts.values()))
        self.assertEqual(sum(result.pots and [pot["amount"] for pot in result.pots] or []),
                         sum(result.contributions.values()))

        for player in game.players:
            self.assertGreaterEqual(player.stack, 0)
            self.assertGreaterEqual(player.hand_contribution, 0)
            self.assertGreaterEqual(player.street_bet, 0)
            # all_in is a hand-local flag and can remain set after showdown;
            # a player may have received a payout after being all-in.

        # Each player's stack change equals payout minus hand contribution.
        for pid, start_stack in result.starting_stacks.items():
            expected = start_stack - result.contributions[pid] + result.payouts[pid]
            self.assertEqual(result.ending_stacks[pid], expected)

        # Every pot must have at least one eligible player and payout must equal pot size.
        for pot in result.pots:
            self.assertTrue(pot["eligible"])
            if "payouts" in pot:
                self.assertEqual(sum(pot["payouts"].values()), pot["amount"])

    def test_randomized_matches_preserve_game_invariants(self):
        scenarios = 0
        for player_count in range(2, 10):
            for stack in (20, 50, 100):
                for seed in range(5):
                    config = GameConfig(
                        small_blind=1,
                        big_blind=2,
                        starting_stack=stack,
                        max_hands=25,
                        max_players=9,
                    )
                    agents = self.make_agents(player_count, seed + player_count * 10)
                    game = Game(agents, config, seed=seed + stack * 100 + player_count)
                    initial_total = player_count * stack

                    for _ in range(config.max_hands):
                        if sum(p.stack > 0 for p in game.players) < 2:
                            break
                        result = game.play_hand()
                        self.assert_hand_invariants(game, result, initial_total)
                        scenarios += 1

        self.assertGreater(scenarios, 100)

    def test_same_seed_reproduces_complete_match_history(self):
        def run_once():
            count, stack, seed = 5, 50, 90210
            config = GameConfig(1, 2, stack, max_hands=20, max_players=9)
            game = Game(self.make_agents(count, seed), config, seed=seed)
            for _ in range(config.max_hands):
                if sum(p.stack > 0 for p in game.players) < 2:
                    break
                game.play_hand()
            return game.history, {p.player_id: p.stack for p in game.players}

        history_a, stacks_a = run_once()
        history_b, stacks_b = run_once()
        self.assertEqual(history_a, history_b)
        self.assertEqual(stacks_a, stacks_b)


if __name__ == "__main__":
    unittest.main()
