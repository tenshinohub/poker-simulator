from poker_sim.domain.actions import Action
from poker_sim.domain.cards import Card
from poker_sim.domain.models import LegalActions, PlayerContext, PlayerView
from poker_sim.players.rule_agent import RuleBasedAgent


def make_context(
    *,
    street="flop",
    position="BTN",
    hole_cards,
    community_cards=(),
    stack=200,
    pot=100,
    current_bet=0,
    to_call=0,
    legal,
):
    view = PlayerView(
        hand_id="hand-1",
        player_id="p1",
        street=street,
        position=position,
        hole_cards=tuple(hole_cards),
        community_cards=tuple(community_cards),
        stack=stack,
        pot=pot,
        current_bet=current_bet,
        to_call=to_call,
        legal_actions=legal,
        action_history=(),
    )
    return PlayerContext("hand-1", "p1", view)


def test_preflop_premium_uses_position_adjusted_raise_sizing():
    legal = LegalActions(
        can_fold=True, can_check=False, can_call=True, call_amount=10,
        can_bet=False, min_bet_to=None, can_raise=True,
        min_raise_to=30, max_raise_to=200, can_all_in=True,
    )
    context = make_context(
        street="preflop",
        hole_cards=[Card.parse("As"), Card.parse("Ks")],
        stack=200,
        pot=15,
        current_bet=10,
        to_call=10,
        legal=legal,
    )

    action = RuleBasedAgent().decide(context)

    assert action.type == "raise"
    assert action.amount is not None
    assert 30 <= action.amount <= 200


def test_postflop_flush_bets_pot_relative_size():
    legal = LegalActions(
        can_fold=True, can_check=True, can_call=False, call_amount=0,
        can_bet=True, min_bet_to=20, can_raise=False,
        min_raise_to=None, max_raise_to=200, can_all_in=True,
    )
    context = make_context(
        hole_cards=[Card.parse("As"), Card.parse("Ks")],
        community_cards=[
            Card.parse("Js"), Card.parse("9s"), Card.parse("4s"),
        ],
        pot=100,
        legal=legal,
    )

    action = RuleBasedAgent().decide(context)

    assert action == Action.bet_to(65)


def test_postflop_raise_uses_pot_relative_size_instead_of_minimum():
    legal = LegalActions(
        can_fold=True, can_check=False, can_call=True, call_amount=50,
        can_bet=False, min_bet_to=None, can_raise=True,
        min_raise_to=100, max_raise_to=200, can_all_in=True,
    )
    context = make_context(
        street="turn",
        hole_cards=[Card.parse("Ah"), Card.parse("Ad")],
        community_cards=[
            Card.parse("Ac"), Card.parse("8s"), Card.parse("8d"),
            Card.parse("2c"),
        ],
        stack=200,
        pot=100,
        current_bet=50,
        to_call=50,
        legal=legal,
    )

    action = RuleBasedAgent().decide(context)

    assert action.type == "raise"
    assert action.amount == 115


def test_short_stack_pair_is_called_immediately():
    legal = LegalActions(
        can_fold=True, can_check=False, can_call=True, call_amount=80,
        can_bet=False, min_bet_to=None, can_raise=False,
        min_raise_to=None, max_raise_to=200, can_all_in=True,
    )
    context = make_context(
        hole_cards=[Card.parse("Jh"), Card.parse("Jd")],
        community_cards=[
            Card.parse("Ac"), Card.parse("8s"), Card.parse("2d"),
        ],
        stack=100,
        pot=120,
        current_bet=80,
        to_call=80,
        legal=legal,
    )

    assert RuleBasedAgent().decide(context) == Action.call()
