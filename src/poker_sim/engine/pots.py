from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Pot:
    amount: int
    eligible: tuple[str, ...]

def build_side_pots(contributions: dict[str, int], folded: set[str]) -> list[Pot]:
    """Build pots from total hand contributions, including folded players' chips."""
    levels = sorted({v for v in contributions.values() if v > 0})
    pots: list[Pot] = []
    previous = 0
    for level in levels:
        contributors = [pid for pid, amount in contributions.items() if amount >= level]
        amount = (level - previous) * len(contributors)
        eligible = tuple(pid for pid in contributors if pid not in folded)
        if amount:
            pots.append(Pot(amount, eligible))
        previous = level
    return pots


def split_amount(amount: int, winners: list[str], seat_order: list[str]) -> dict[str, int]:
    """Split a pot among winners, assigning odd chips in seat order."""
    if type(amount) is not int or amount < 0:
        raise ValueError("Pot amount must be a non-negative integer")

    if not winners:
        raise ValueError("A pot must have at least one eligible winner")

    if len(set(winners)) != len(winners):
        raise ValueError("Winners must not contain duplicates")

    if len(set(seat_order)) != len(seat_order):
        raise ValueError("Seat order must not contain duplicates")

    winners_set = set(winners)
    seat_set = set(seat_order)

    missing = winners_set - seat_set
    if missing:
        raise ValueError(
            f"Winner(s) missing from seat order: {sorted(missing)}"
        )

    ordered = [pid for pid in seat_order if pid in winners_set]

    if not ordered:
        raise ValueError("No winners found in seat order")

    share, remainder = divmod(amount, len(ordered))
    result = {pid: share for pid in ordered}

    # Odd chips go to winners in seat order.
    for pid in ordered[:remainder]:
        result[pid] += 1

    return result

def validate_pots(pots: list[Pot]) -> None:
    """Reject pots that cannot be awarded to any player."""
    for index, pot in enumerate(pots, start=1):
        if pot.amount <= 0:
            raise ValueError(
                f"Pot {index} has invalid amount: {pot.amount}"
            )

        if not pot.eligible:
            raise ValueError(
                f"Pot {index} has no eligible players"
            )

        if len(set(pot.eligible)) != len(pot.eligible):
            raise ValueError(
                f"Pot {index} has duplicate eligible players"
            )

@dataclass(frozen=True)
class PotAward:
    amount: int
    eligible: tuple[str, ...]
    winners: tuple[str, ...]
    payouts: dict[str, int]


def distribute_pots(
    pots: list[Pot],
    hand_ranks: dict[str, tuple[int, ...]],
    seat_order: list[str],
) -> list[PotAward]:
    """Determine winners and payouts independently for each main/side pot."""
    validate_pots(pots)
    awards: list[PotAward] = []
    for pot in pots:
        eligible = [pid for pid in pot.eligible if pid in hand_ranks]
        if not eligible:
            raise ValueError("Pot has no eligible player with a hand rank")
        best_rank = max(hand_ranks[pid] for pid in eligible)
        winners = [pid for pid in eligible if hand_ranks[pid] == best_rank]
        payouts = split_amount(pot.amount, winners, seat_order)
        awards.append(PotAward(pot.amount, pot.eligible, tuple(winners), payouts))
    return awards
