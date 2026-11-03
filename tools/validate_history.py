
import json
import sys
from pathlib import Path


path = Path(sys.argv[1] if len(sys.argv) > 1 else "hand_history.jsonl")
errors = []
hands = 0
actions_checked = 0


def report(hand_id, message):
    errors.append(f"{hand_id}: {message}")


def expected_pots(contributions, folded):
    """独立した検証ロジックでポットを再構築する。"""
    levels = sorted({v for v in contributions.values() if v > 0})
    pots = []
    previous = 0

    for level in levels:
        contributors = [
            pid for pid, amount in contributions.items()
            if amount >= level
        ]
        amount = (level - previous) * len(contributors)
        eligible = [
            pid for pid in contributors
            if pid not in folded
        ]

        if amount:
            pots.append({"amount": amount, "eligible": eligible})

        previous = level

    return pots


with path.open(encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        if not line.strip():
            continue

        try:
            hand = json.loads(line)
        except json.JSONDecodeError as exc:
            report(f"line {line_no}", f"invalid JSON: {exc}")
            continue

        hands += 1
        hand_id = hand.get("hand_id", line_no)
        start = hand.get("starting_stacks", {})
        end = hand.get("ending_stacks", {})
        payouts = hand.get("payouts", {})
        contributions = hand.get("contributions")
        pots = hand.get("pots", [])

        # チップ総量とプレイヤーIDの整合性
        if sum(start.values()) != sum(end.values()):
            report(hand_id, "total chips changed")

        if set(start) != set(end):
            report(hand_id, "player IDs differ between starting and ending stacks")

        if set(start) != set(payouts):
            report(hand_id, "player IDs differ in payouts")

        # 各アクションの整合性
        folded = set()

        for i, action in enumerate(hand.get("actions", []), 1):
            actions_checked += 1
            pid = action.get("player_id")
            name = f"action {i} ({pid})"

            # 返金イベントは通常のプレイヤーアクションと区別して検証
            if action.get("event") == "refund_uncalled_bet":
                required_refund = {
                    "player_id",
                    "amount",
                    "stack_before",
                    "stack_after",
                    "street_bet_before",
                    "street_bet_after",
                    "hand_contribution_before",
                    "hand_contribution_after",
                    "current_bet_before",
                    "current_bet_after",
                }

                missing = required_refund - action.keys()
                if missing:
                    report(
                        hand_id,
                        f"refund event {i}: missing fields "
                        f"{sorted(missing)}",
                    )
                    continue

                amount = action["amount"]
                numeric_fields = [
                    "stack_before",
                    "stack_after",
                    "street_bet_before",
                    "street_bet_after",
                    "hand_contribution_before",
                    "hand_contribution_after",
                    "current_bet_before",
                    "current_bet_after",
                ]

                values = [
                    action[key] for key in numeric_fields
                ]

                if type(amount) is not int or amount <= 0:
                    report(
                        hand_id,
                        f"refund event {i}: invalid refund amount",
                    )
                    continue

                if any(type(value) is not int for value in values):
                    report(
                        hand_id,
                        f"refund event {i}: chip values must be integers",
                    )
                    continue

                if any(value < 0 for value in values):
                    report(
                        hand_id,
                        f"refund event {i}: negative chip/state value",
                    )

                if action["player_id"] not in start:
                    report(
                        hand_id,
                        f"refund event {i}: unknown player",
                    )

                if (
                    action["stack_after"] - action["stack_before"]
                    != amount
                ):
                    report(
                        hand_id,
                        f"refund event {i}: stack change does not match refund",
                    )

                if (
                    action["street_bet_before"]
                    - action["street_bet_after"]
                    != amount
                ):
                    report(
                        hand_id,
                        f"refund event {i}: street bet change does not match refund",
                    )

                if (
                    action["hand_contribution_before"]
                    - action["hand_contribution_after"]
                    != amount
                ):
                    report(
                        hand_id,
                        f"refund event {i}: contribution change does not match refund",
                    )

                if (
                    action["current_bet_after"]
                    > action["current_bet_before"]
                ):
                    report(
                        hand_id,
                        f"refund event {i}: current bet increased after refund",
                    )

                actions_checked += 1
                continue

            pid = action.get("player_id")
            name = f"action {i} ({pid})"

            if pid in folded:
                report(hand_id, f"{name}: action after fold")

            if action.get("action") == "fold":
                folded.add(pid)

            required = {
                "stack_before", "stack_after",
                "street_bet_before", "street_bet_after",
                "current_bet_before", "current_bet_after",
                "to_call_before", "legal_before",
            }

            if not required.issubset(action):
                report(hand_id, f"{name}: missing action-state fields")
                continue

            before = action["stack_before"]
            after = action["stack_after"]
            bet_before = action["street_bet_before"]
            bet_after = action["street_bet_after"]
            current_before = action["current_bet_before"]
            current_after = action["current_bet_after"]
            to_call = action["to_call_before"]
            legal = action["legal_before"]
            kind = action.get("action")

            if min(
                before, after, bet_before, bet_after,
                current_before, current_after, to_call
            ) < 0:
                report(hand_id, f"{name}: negative chip/state value")

            if before - after != bet_after - bet_before:
                report(hand_id, f"{name}: stack change does not match bet change")

            if to_call != max(0, current_before - bet_before):
                report(hand_id, f"{name}: incorrect to_call")

            legal_key = {
                "fold": "can_fold",
                "check": "can_check",
                "call": "can_call",
                "bet": "can_bet",
                "raise": "can_raise",
                "all_in": "can_all_in",
            }.get(kind)

            if legal_key and not legal.get(legal_key, False):
                report(hand_id, f"{name}: illegal {kind} according to legal_before")

            if kind in ("bet", "raise", "all_in") and current_after < current_before:
                report(hand_id, f"{name}: current bet decreased")

        # ポットの独立再計算と照合
        if contributions is None:
            report(hand_id, "missing contributions")
        elif (
            set(contributions) != set(start)
            or any(type(v) is not int or v < 0 for v in contributions.values())
        ):
            report(hand_id, "invalid contributions")
        else:
            if sum(contributions.values()) != sum(pot.get("amount", 0) for pot in pots):
                report(hand_id, "contribution total does not match pot total")

            expected = expected_pots(contributions, folded)

            # フォールド勝ちでは、現在の実装に合わせて1つのポットとして照合
            if hand.get("reason") == "everyone_else_folded":
                winners = hand.get("winners", [])
                if len(winners) != 1:
                    report(hand_id, "fold-win hand must have exactly one winner")
                else:
                    expected = [{
                        "amount": sum(contributions.values()),
                        "eligible": winners,
                    }]

            if len(expected) != len(pots):
                report(hand_id, "number of pots does not match contributions")

            for i, (exp, actual) in enumerate(zip(expected, pots), 1):
                if actual.get("amount") != exp["amount"]:
                    report(hand_id, f"pot {i}: amount mismatch")

                if set(actual.get("eligible", [])) != set(exp["eligible"]):
                    report(hand_id, f"pot {i}: eligible players mismatch")

            # 配当と勝者の整合性
            for i, pot in enumerate(pots, 1):
                amount = pot.get("amount")
                shares = pot.get("payouts")
                winners = set(pot.get("winners", []))
                eligible = set(pot.get("eligible", []))

                if type(amount) is not int or amount < 0:
                    report(hand_id, f"pot {i}: invalid amount")
                    continue

                if not winners.issubset(eligible):
                    report(hand_id, f"pot {i}: winner not eligible")

                if shares is None and hand.get("reason") == "everyone_else_folded":
                    continue

                if not isinstance(shares, dict):
                    report(hand_id, f"pot {i}: missing payouts")
                    continue

                if any(type(v) is not int or v < 0 for v in shares.values()):
                    report(hand_id, f"pot {i}: invalid payout amount")
                    continue

                if sum(shares.values()) != amount:
                    report(hand_id, f"pot {i}: payout total mismatch")

                if not set(shares).issubset(winners):
                    report(hand_id, f"pot {i}: payout recipient is not a winner")

                if not winners.issubset(eligible):
                    report(hand_id, f"pot {i}: winner not eligible")

print(f"Hands checked: {hands}")
print(f"Actions checked: {actions_checked}")
print(f"Errors: {len(errors)}")

for error in errors[:100]:
    print("ERROR:", error)

if len(errors) > 100:
    print(f"... {len(errors) - 100} more errors")

sys.exit(1 if errors else 0)
