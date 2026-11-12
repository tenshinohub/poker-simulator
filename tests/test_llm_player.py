import json

from poker_sim.domain.actions import Action
from poker_sim.domain.cards import Card
from poker_sim.domain.models import LegalActions, PlayerContext, PlayerView
from poker_sim.players.llm_agent import LLMPlayer
from poker_sim.llm.providers.base import LLMResponse


class FakeProvider:
    def __init__(self, content):
        self.content = content

    def generate(self, request):
        self.request = request
        return LLMResponse(self.content, "fake", "fake-model")


def context(legal=None):
    legal = legal or LegalActions(
        can_fold=True, can_check=False, can_call=True, call_amount=10,
        can_bet=False, min_bet_to=None, can_raise=False,
        min_raise_to=None, max_raise_to=100, can_all_in=True,
    )
    view = PlayerView(
        hand_id="hand-1", player_id="p2", street="preflop", position="BTN",
        hole_cards=(Card.parse("As"), Card.parse("Kd")), community_cards=(),
        stack=100, pot=15, current_bet=10, to_call=10,
        legal_actions=legal, action_history=(),
    )
    return PlayerContext("hand-1", "p2", view)


def test_llm_player_parses_legal_call_and_sends_only_own_observation():
    provider = FakeProvider('{"action":"call","amount":null,"reason":"pot odds"}')
    player = LLMPlayer("Gemini", provider)
    action = player.decide(context())
    assert action == Action.call()
    payload = json.loads(provider.request.user_prompt)
    assert payload["hole_cards"] == ["As", "Kd"]
    assert "opponent_hole_cards" not in payload


def test_llm_player_rejects_illegal_action_and_uses_safe_fallback():
    provider = FakeProvider('{"action":"raise","amount":80}')
    player = LLMPlayer("OpenAI", provider)
    action = player.decide(context())
    assert action == Action.call()
    assert player.last_error


def test_llm_player_uses_check_as_fallback_when_available():
    legal = LegalActions(
        can_fold=True, can_check=True, can_call=False, call_amount=0,
        can_bet=False, min_bet_to=None, can_raise=False,
        min_raise_to=None, max_raise_to=100, can_all_in=False,
    )
    player = LLMPlayer("LLM", FakeProvider("not json"))
    assert player.decide(context(legal)) == Action.check()
