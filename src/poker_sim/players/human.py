from __future__ import annotations
from ..domain.actions import Action
from ..domain.models import PlayerContext

class HumanCLIPlayer:
    def __init__(self, name: str = "Human"):
        self.name = name

    def decide(self, context: PlayerContext) -> Action:
        obs = context.observation
        legal = obs.legal_actions
        print(f"\n{obs.street.upper()} | position={obs.position} | hand={obs.hand_id}")
        print("Your cards:", " ".join(map(str, obs.hole_cards)))
        print("Board:", " ".join(map(str, obs.community_cards)) or "(empty)")
        print(f"Stack={obs.stack} Pot={obs.pot} Current bet={obs.current_bet} To call={obs.to_call}")
        choices = []
        if legal.can_fold: choices.append("fold")
        if legal.can_check: choices.append("check")
        if legal.can_call: choices.append(f"call ({legal.call_amount})")
        if legal.can_bet: choices.append(f"bet (total {legal.min_bet_to}..{legal.max_raise_to})")
        if legal.can_raise: choices.append(f"raise (total {legal.min_raise_to}..{legal.max_raise_to})")
        if legal.can_all_in: choices.append("all_in")
        print("Available:", ", ".join(choices))
        while True:
            raw = input("Action [fold/check/call/bet N/raise N/allin]: ").strip().lower()
            try:
                if raw == "fold": action = Action.fold()
                elif raw == "check": action = Action.check()
                elif raw == "call": action = Action.call()
                elif raw in {"allin", "all-in"}: action = Action.all_in()
                elif raw.startswith("bet "): action = Action.bet_to(int(raw.split()[1]))
                elif raw.startswith("raise "): action = Action.raise_to(int(raw.split()[1]))
                else:
                    print("Please enter a valid action."); continue
                return action
            except (ValueError, IndexError):
                print("Invalid input. Example: raise 60")
