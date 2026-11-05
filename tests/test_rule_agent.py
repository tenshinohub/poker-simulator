import unittest

from poker_sim.domain.actions import Action
from poker_sim.domain.cards import Card
from poker_sim.domain.models import LegalActions, PlayerContext, PlayerView
from poker_sim.players.rule_agent import RuleBasedAgent


def make_context(
    hole_cards,
    community_cards=(),
    *,
    pot=100,
    to_call=0,
    opponent_count=1,
    legal_actions=None,
):
    legal = legal_actions or LegalActions(
        can_fold=to_call > 0,
        can_check=to_call == 0,
        can_call=to_call > 0,
        call_amount=to_call,
        can_bet=to_call == 0,
        min_bet_to=10 if to_call == 0 else None,
        can_raise=to_call > 0,
        min_raise_to=to_call * 2 if to_call > 0 else None,
        max_raise_to=500,
        can_all_in=True,
    )
    view = PlayerView(
        hand_id="test-hand",
        player_id="hero",
        street="river" if len(community_cards) == 5 else "flop",
        position="BTN",
        hole_cards=tuple(hole_cards),
        community_cards=tuple(community_cards),
        stack=500,
        pot=pot,
        current_bet=to_call,
        to_call=to_call,
        legal_actions=legal,
        action_history=(),
        opponent_count=opponent_count,
    )
    return PlayerContext("test-hand", "hero", view)


class RuleBasedAgentTests(unittest.TestCase):
    def test_equity_accounts_for_tied_board_and_opponent_count(self):
        board = tuple(Card.parse(card) for card in ("As", "Ks", "Qs", "Js", "Ts"))
        hole = tuple(Card.parse(card) for card in ("2c", "3d"))
        one_opponent = make_context(hole, board)
        two_opponents = make_context(hole, board, opponent_count=2)

        self.assertAlmostEqual(RuleBasedAgent._estimate_equity(one_opponent), 0.5)
        self.assertAlmostEqual(RuleBasedAgent._estimate_equity(two_opponents), 1 / 3)

    def test_strong_hand_makes_a_pot_sized_value_bet(self):
        hole = tuple(Card.parse(card) for card in ("Jc", "Tc"))
        board = tuple(Card.parse(card) for card in ("As", "Kd", "Qh", "2c", "3s"))
        context = make_context(hole, board, pot=100)

        self.assertEqual(RuleBasedAgent().decide(context), Action.bet_to(66))

    def test_folds_when_estimated_equity_is_far_below_pot_odds(self):
        board = tuple(Card.parse(card) for card in ("As", "Ks", "Qs", "Js", "Ts"))
        hole = tuple(Card.parse(card) for card in ("2c", "3d"))
        legal = LegalActions(
            can_fold=True,
            can_check=False,
            can_call=True,
            call_amount=900,
            can_bet=False,
            min_bet_to=None,
            can_raise=False,
            min_raise_to=None,
            max_raise_to=1000,
            can_all_in=True,
        )
        context = make_context(hole, board, pot=100, to_call=900, legal_actions=legal)

        self.assertEqual(RuleBasedAgent().decide(context), Action.fold())

    def test_short_stack_call_uses_the_affordable_amount_for_pot_odds(self):
        board = tuple(Card.parse(card) for card in ("As", "Ks", "Qs", "Js", "Ts"))
        hole = tuple(Card.parse(card) for card in ("2c", "3d"))
        legal = LegalActions(
            can_fold=True,
            can_check=False,
            can_call=True,
            call_amount=10,
            can_bet=False,
            min_bet_to=None,
            can_raise=False,
            min_raise_to=None,
            max_raise_to=10,
            can_all_in=True,
        )
        context = make_context(hole, board, pot=100, to_call=900, legal_actions=legal)

        self.assertEqual(RuleBasedAgent().decide(context), Action.call())

    def test_raise_size_uses_pot_odds_and_respects_legal_bounds(self):
        legal = LegalActions(
            can_fold=True,
            can_check=False,
            can_call=True,
            call_amount=20,
            can_bet=False,
            min_bet_to=None,
            can_raise=True,
            min_raise_to=40,
            max_raise_to=200,
            can_all_in=True,
        )

        self.assertEqual(RuleBasedAgent._raise_target(legal, pot=100, to_call=20), 79)
        self.assertEqual(RuleBasedAgent._raise_target(legal, pot=1000, to_call=20), 200)


if __name__ == "__main__":
    unittest.main()
