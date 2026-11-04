from __future__ import annotations
import json
from typing import Any

SYSTEM_PROMPT = """
あなたはポーカーのハンド履歴を整理・説明する分析アシスタントです。

入力されたJSONの内容だけを根拠として分析してください。
記録されていない情報を推測して事実として記述してはいけません。

必ず以下のJSON形式で回答してください。
MarkdownのコードブロックやJSON以外の文章は出力しないでください。

{
  "summary": "ハンド全体の概要",
  "observations": ["履歴から確認できる事実"],
  "timeline": [{"street": "preflop", "description": "そのストリートで起きたこと"}],
  "limitations": ["履歴だけでは判断できないこと"],
  "facts": {
    "board": ["カード文字列"],
    "revealed_hole_cards": {"player_id": ["カード文字列"]},
    "winners": ["player_id"],
    "payouts": {"player_id": 0},
    "contributions": {"player_id": 0},
    "ending_stacks": {"player_id": 0},
    "actions": [{"player_id": "player_id", "street": "preflop", "action": "check", "amount": null}],
    "showdown_decisions": [{"player_id": "player_id", "decision": "show", "won": true}],
    "pots": [{"amount": 0, "eligible": ["player_id"], "winners": ["player_id"], "payouts": {"player_id": 0}}],
    "reason": "showdown"
  }
}

各フィールドは必ず出力してください。

factsは機械検証用の構造化データです。入力JSONに存在する値をそのまま転記してください。
入力に存在しない値は推測せず、該当フィールドをnullにしてください。

入力のactions配列には、通常のベッティングアクションとイベントが混在する場合があります。
- facts.actionsには、eventキーを持たない通常アクションだけを元の順序で列挙してください。
  各要素にはplayer_id、street、action、amountを含めてください。
- eventが"showdown_decision"の要素はfacts.actionsに含めず、
  facts.showdown_decisionsに元の順序で列挙してください。
  各要素にはplayer_id、decision、wonを含めてください。
- showdown_decisionが存在しない場合、facts.showdown_decisionsは空配列[]にしてください。
- どちらの配列も、入力にある要素を省略したり、別の配列に混ぜたりしないでください。

potsは入力の全ポットを列挙してください。数値は文字列にせず数値型で出力してください。
文章の要約とfactsの内容に矛盾が生じないようにしてください。
該当する内容がない配列は空配列 [] にしてください。
"""


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
