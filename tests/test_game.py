import unittest
from unittest.mock import patch
from poker_sim.engine.game import Game, GameConfig
from poker_sim.domain.actions import Action
from poker_sim.domain.models import PlayerState
from poker_sim.engine.betting import BettingRound
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

    def test_losing_showdown_player_can_muck_without_changing_payout(self):
        class DisclosureAgent:
            def __init__(self, name):
                self.name = name
                self.decision = None

            def decide(self, context):
                legal = context.observation.legal_actions
                if legal.can_check:
                    return Action.check()
                if legal.can_call:
                    return Action.call()
                return Action.fold()

            def decide_showdown(self, context):
                self.decision = "show" if context["won"] else "muck"
                return self.decision

        agents = [DisclosureAgent("A"), DisclosureAgent("B")]
        game = Game(agents, GameConfig(starting_stack=500, max_hands=1), seed=17)
        result = game.play_hand()
        self.assertEqual(result.reason, "showdown")
        self.assertEqual(sum(result.payouts.values()), sum(result.contributions.values()))
        self.assertEqual(set(result.revealed_hole_cards), set(result.winners))
        decisions = [a for a in result.actions if a.get("event") == "showdown_decision"]
        self.assertEqual(len(decisions), 2)
        for item in decisions:
            self.assertEqual(item["decision"], "show" if item["won"] else "muck")

    def test_long_match_does_not_fold_every_player(self):
        # Regression: the old betting loop could ask the last remaining player
        # to act after everyone else folded, producing a pot with no eligible player.
        from poker_sim.runner.match import MatchRunner
        from poker_sim.players.random_agent import RandomAgent
        runner = MatchRunner(
            [RuleBasedAgent("A"), RandomAgent("B", seed=1001)],
            GameConfig(starting_stack=1000, max_hands=1000),
            seed=123,
        )
        result = runner.run()
        self.assertGreater(result.hands_played, 0)
        self.assertEqual(sum(result.net_results.values()), 0)

    def test_betting_loop_runs_once_per_street(self):
        class CheckCallAgent:
            def __init__(self, name):
                self.name = name

            def decide(self, context):
                legal = context.observation.legal_actions
                if legal.can_check:
                    return Action.check()
                if legal.can_call:
                    return Action.call()
                return Action.fold()

        game = Game(
            [CheckCallAgent("A"), CheckCallAgent("B")],
            GameConfig(starting_stack=500, max_hands=1),
            seed=17,
        )
        with patch.object(game, "_betting_loop", wraps=game._betting_loop) as loop:
            game.play_hand()

        # Preflop, flop, turn, and river: one invocation for each street.
        self.assertEqual(loop.call_count, 4)

    def test_all_in_opponents_do_not_trigger_extra_betting_when_matched(self):
        all_in = PlayerState("p1", "All-in", 0, 0, all_in=True, street_bet=100)
        active = PlayerState("p2", "Active", 200, 1, street_bet=100)
        round_state = BettingRound([all_in, active], big_blind=10, current_bet=100)

        self.assertFalse(Game._should_run_betting_round([all_in, active], round_state))

    def test_lone_active_player_must_respond_to_all_in_bet(self):
        all_in = PlayerState("p1", "All-in", 0, 0, all_in=True, street_bet=150)
        active = PlayerState("p2", "Active", 200, 1, street_bet=100)
        round_state = BettingRound([all_in, active], big_blind=10, current_bet=150)

        self.assertTrue(Game._should_run_betting_round([all_in, active], round_state))

    def test_two_actionable_players_run_betting_round(self):
        p1 = PlayerState("p1", "P1", 100, 0, street_bet=10)
        p2 = PlayerState("p2", "P2", 100, 1, street_bet=10)
        round_state = BettingRound([p1, p2], big_blind=10, current_bet=10)

        self.assertTrue(Game._should_run_betting_round([p1, p2], round_state))

    def test_no_actionable_players_skip_betting_round(self):
        p1 = PlayerState("p1", "P1", 0, 0, all_in=True, street_bet=10)
        p2 = PlayerState("p2", "P2", 0, 1, all_in=True, street_bet=10)
        round_state = BettingRound([p1, p2], big_blind=10, current_bet=10)

        self.assertFalse(Game._should_run_betting_round([p1, p2], round_state))

    def test_seed_reproduces_first_board(self):
        def run():
            game = Game([RuleBasedAgent("A"), RuleBasedAgent("B")],
                        GameConfig(starting_stack=100), seed=77)
            return [str(c) for c in game.play_hand().board]
        self.assertEqual(run(), run())

if __name__ == "__main__": unittest.main()
