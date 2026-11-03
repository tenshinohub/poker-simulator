from __future__ import annotations
from typing import Any

def summarize_match(result: Any) -> dict[str, Any]:
    hands = result.hands_played
    return {
        "hands_played": hands,
        "final_stacks": result.final_stacks,
        "net_results": result.net_results,
        "net_bb": {pid: net / 10 for pid, net in result.net_results.items()},
        "bb_per_100": {pid: (net / 10) * 100 / hands if hands else 0.0
                       for pid, net in result.net_results.items()},
    }
