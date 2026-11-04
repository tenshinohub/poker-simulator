from __future__ import annotations
import json
from typing import Any

SYSTEM_PROMPT = """あなたはポーカーシミュレーターの対局記録を説明する分析者です。
与えられた記録から確認できる事実だけを、日本語で簡潔に説明してください。
各プレイヤーの判断の良し悪し、勝率、最適戦略、次に取るべきアクションなどの助言・推奨は行わないでください。
記録にない情報を推測せず、不明な点は不明と明記してください。
出力は指定されたJSONオブジェクトだけにしてください。"""

def build_request_payload(record: dict[str, Any]) -> str:
    # The source history contains only hole cards explicitly revealed at showdown.
    safe_record = {
        "hand_id": record.get("hand_id"),
        "reason": record.get("reason"),
        "board": record.get("board", []),
        "winners": record.get("winners", []),
        "payouts": record.get("payouts", {}),
        "starting_stacks": record.get("starting_stacks", {}),
        "ending_stacks": record.get("ending_stacks", {}),
        "contributions": record.get("contributions", {}),
        "pots": record.get("pots", []),
        "revealed_hole_cards": record.get("revealed_hole_cards", {}),
        "actions": record.get("actions", []),
    }
    return json.dumps(safe_record, ensure_ascii=False, default=str)
