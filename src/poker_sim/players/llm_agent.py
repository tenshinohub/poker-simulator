from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any, Callable

from ..domain.actions import Action
from ..domain.models import PlayerContext
from ..llm.providers.base import LLMProvider, LLMRequest


SYSTEM_PROMPT = """あなたはテキサスホールデムのプレイヤーです。
渡された自分の手札、公開ボード、ポット、アクション履歴、合法アクションだけを使って判断してください。
他プレイヤーの非公開カードを知っているかのように扱ってはいけません。
合法アクションの範囲外の行動を選んではいけません。
ベット額・レイズ額は現在のストリートにおける自分の合計拠出額（total street contribution）です。
必ずJSONオブジェクトだけを返してください。Markdownやコードフェンスは不要です。
形式: {"action":"fold|check|call|bet|raise|all_in", "amount": null, "reason":"短い判断理由"}
bet/raiseの場合のみamountに整数を指定してください。"""


class LLMPlayer:
    """A live poker player backed by a pluggable LLM provider."""

    def __init__(self, name: str, provider: LLMProvider,
                 on_status: Callable[[str, dict[str, Any]], None] | None = None):
        self.name = name
        self.provider = provider
        self.on_status = on_status
        self.last_reason: str | None = None
        self.last_error: str | None = None

    def _payload(self, context: PlayerContext) -> str:
        obs = context.observation
        payload = {
            "hand_id": context.hand_id,
            "player_id": context.player_id,
            "street": obs.street,
            "position": obs.position,
            "hole_cards": [str(card) for card in obs.hole_cards],
            "community_cards": [str(card) for card in obs.community_cards],
            "stack": obs.stack,
            "pot": obs.pot,
            "current_bet": obs.current_bet,
            "to_call": obs.to_call,
            "legal_actions": asdict(obs.legal_actions),
            "action_history": list(obs.action_history),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _fallback(context: PlayerContext) -> Action:
        legal = context.observation.legal_actions
        if legal.can_check:
            return Action.check()
        if legal.can_call:
            return Action.call()
        return Action.fold()

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise ValueError("LLM response did not contain a JSON object")
            value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("LLM response must be a JSON object")
        return value

    def _to_action(self, data: dict[str, Any], context: PlayerContext) -> Action:
        legal = context.observation.legal_actions
        kind = str(data.get("action", "")).strip().lower()
        if kind in {"all-in", "allin"}:
            kind = "all_in"
        if kind == "fold" and legal.can_fold:
            return Action.fold()
        if kind == "check" and legal.can_check:
            return Action.check()
        if kind == "call" and legal.can_call:
            return Action.call()
        if kind == "all_in" and legal.can_all_in:
            return Action.all_in()
        amount = data.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError("bet/raise amount must be an integer")
        if kind == "bet" and legal.can_bet and legal.min_bet_to is not None:
            if legal.min_bet_to <= amount <= legal.max_raise_to:
                return Action.bet_to(amount)
        if kind == "raise" and legal.can_raise and legal.min_raise_to is not None:
            if legal.min_raise_to <= amount <= legal.max_raise_to:
                return Action.raise_to(amount)
        raise ValueError(f"Illegal or unsupported LLM action: {kind}")

    def decide(self, context: PlayerContext) -> Action:
        if self.on_status:
            self.on_status("ai_thinking", {"player_id": context.player_id, "name": self.name})
        try:
            response = self.provider.generate(LLMRequest(SYSTEM_PROMPT, self._payload(context)))
            data = self._extract_json(response.content)
            action = self._to_action(data, context)
            self.last_reason = str(data.get("reason", ""))[:500]
            self.last_error = None
            if self.on_status:
                self.on_status("ai_action", {
                    "player_id": context.player_id, "name": self.name,
                    "action": action.type, "reason": self.last_reason,
                    "provider": response.provider, "model": response.model,
                })
            return action
        except Exception as exc:
            self.last_error = str(exc)
            self.last_reason = "AI応答を利用できなかったため、安全な合法アクションを選択しました。"
            if self.on_status:
                self.on_status("ai_fallback", {
                    "player_id": context.player_id, "name": self.name,
                    "error": self.last_error,
                })
            return self._fallback(context)
