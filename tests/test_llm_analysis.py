import json
import unittest
from poker_sim.llm.analyzer import HandHistoryAnalyzer
from poker_sim.llm.providers.base import LLMResponse
from poker_sim.llm.prompt_builder import build_request_payload
from poker_sim.llm.response_parser import parse_analysis

class FakeProvider:
    def generate(self, request):
        self.request = request
        return LLMResponse(json.dumps({
            "summary": "hand-000001の記録です。",
            "timeline": ["preflopでアクションが記録されています。"],
            "observations": ["配当記録があります。"],
            "limitations": ["非公開の手札は分析対象に含まれません。"]
        }), "fake", "test-model", {"total_token_count": 10})

class LLMAnalysisTests(unittest.TestCase):
    def test_analyzer_with_fake_provider(self):
        provider = FakeProvider()
        record = {"hand_id": "hand-000001", "actions": [], "revealed_hole_cards": {}}
        result = HandHistoryAnalyzer(provider).analyze(record)
        self.assertEqual(result.hand_id, "hand-000001")
        self.assertEqual(result.provider, "fake")
        self.assertIn("hand_id", json.loads(provider.request.user_prompt))

    def test_parser_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            parse_analysis('{"summary":"x"}')

    def test_payload_does_not_invent_hidden_cards(self):
        payload = json.loads(build_request_payload({"hand_id": "h", "revealed_hole_cards": {"p1": ["As", "Kd"]}}))
        self.assertEqual(payload["revealed_hole_cards"]["p1"], ["As", "Kd"])
        self.assertNotIn("hole_cards", payload)

if __name__ == "__main__":
    unittest.main()
