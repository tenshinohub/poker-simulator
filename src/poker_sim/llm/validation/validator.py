from __future__ import annotations

from typing import Any


def _status(field: str, expected: Any, actual: Any) -> dict[str, Any]:
    if actual is None:
        return {"field": field, "status": "not_reported", "expected": expected,
                "actual": None, "message": "分析結果に構造化された記載がありません"}
    if expected == actual:
        return {"field": field, "status": "pass", "expected": expected,
                "actual": actual, "message": "元の履歴と一致しています"}
    return {"field": field, "status": "fail", "expected": expected,
            "actual": actual, "message": "元の履歴と一致しません"}


def _split_history_actions(actions: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate betting actions from showdown-decision events in the source history."""
    if not isinstance(actions, list):
        return [], []
    betting_actions: list[dict[str, Any]] = []
    showdown_decisions: list[dict[str, Any]] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        if item.get("event") == "showdown_decision":
            showdown_decisions.append(item)
        elif "event" not in item:
            betting_actions.append(item)
    return betting_actions, showdown_decisions


def _normalize_actions(actions: Any) -> list[dict[str, Any]]:
    if not isinstance(actions, list):
        return []
    return [{"player_id": action.get("player_id"), "street": action.get("street"),
             "action": action.get("action"), "amount": action.get("amount")}
            for action in actions if isinstance(action, dict)]


def _normalize_showdown_decisions(decisions: Any) -> list[dict[str, Any]]:
    if not isinstance(decisions, list):
        return []
    return [{"player_id": decision.get("player_id"),
             "decision": decision.get("decision"), "won": decision.get("won")}
            for decision in decisions if isinstance(decision, dict)]


def _normalize_pots(pots: Any) -> list[dict[str, Any]]:
    if not isinstance(pots, list):
        return []
    keys = ("amount", "eligible", "winners", "payouts")
    return [{key: pot[key] for key in keys if key in pot}
            for pot in pots if isinstance(pot, dict)]


def validate_analysis(record: dict[str, Any], analysis_record: dict[str, Any]) -> dict[str, Any]:
    """Compare structured LLM claims against one source hand record.

    Free-form prose is intentionally not treated as machine-verifiable evidence.
    Missing facts are reported as not_reported, not as failures.
    """
    hand_id = record.get("hand_id")
    analysis = analysis_record.get("analysis", analysis_record)
    facts = analysis.get("facts", {}) if isinstance(analysis, dict) else {}
    if not isinstance(facts, dict):
        facts = {}

    source_actions, source_showdown_decisions = _split_history_actions(record.get("actions"))
    comparisons = {
        "board": (record.get("board"), facts.get("board")),
        "revealed_hole_cards": (record.get("revealed_hole_cards"), facts.get("revealed_hole_cards")),
        "winners": (record.get("winners"), facts.get("winners")),
        "payouts": (record.get("payouts"), facts.get("payouts")),
        "contributions": (record.get("contributions"), facts.get("contributions")),
        "ending_stacks": (record.get("ending_stacks"), facts.get("ending_stacks")),
        "actions": (_normalize_actions(source_actions),
                    _normalize_actions(facts["actions"]) if isinstance(facts.get("actions"), list) else None),
        "showdown_decisions": (_normalize_showdown_decisions(source_showdown_decisions),
                    _normalize_showdown_decisions(facts["showdown_decisions"])
                    if isinstance(facts.get("showdown_decisions"), list) else None),
        "pots": (_normalize_pots(record.get("pots")),
                 _normalize_pots(facts["pots"]) if isinstance(facts.get("pots"), list) else None),
        "reason": (record.get("reason"), facts.get("reason")),
    }
    checks = [_status(field, expected, actual)
              for field, (expected, actual) in comparisons.items()]

    # Validate source-record invariants independently of the LLM response.
    start, end = record.get("starting_stacks"), record.get("ending_stacks")
    if isinstance(start, dict) and isinstance(end, dict):
        start_total, end_total = sum(start.values()), sum(end.values())
        checks.append({
            "field": "source_chip_conservation",
            "status": "pass" if start_total == end_total else "fail",
            "expected": start_total,
            "actual": end_total,
            "message": "元履歴内の総チップ数を確認しました" if start_total == end_total
                       else "元履歴内で総チップ数が変化しています",
        })

    counts = {name: sum(check["status"] == name for check in checks)
              for name in ("pass", "fail", "not_reported")}
    return {"hand_id": hand_id, "checks": checks, "summary": counts}
