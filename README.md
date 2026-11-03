# Poker Simulator (MVP)

A dependency-free, modular No-Limit Texas Hold'em cash-game simulator for Python 3.11+.

## Features

- 2–9 player tables
- Human CLI, random agent, and simple rule-based agent
- Preflop through river, fold/check/call/bet/raise/all-in
- Side pots, ties, odd-chip distribution
- 7-card hand evaluation (best 5 of 7)
- Seeded shuffling, hand histories, basic statistics
- Engine does not depend on a particular player strategy

## Run

From this directory:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
poker-sim --players human,rule,random --hands 10 --seed 123
```

Without installing the package:

```bash
PYTHONPATH=src python -m poker_sim.ui.cli --players human,rule --hands 1
```

Player types are `human`, `random`, and `rule`. The first player is the human if `human` is specified.

## Architecture

- `domain`: cards, actions, data types
- `engine`: betting state machine, hand evaluator, pot settlement
- `players`: strategy implementations
- `runner`: hand/match orchestration
- `storage`: JSON Lines hand history
- `evaluation`: basic match statistics
- `ui`: CLI adapter

## API contract

A player receives a `PlayerContext` containing only its own hole cards and public information. It returns an `Action`. The engine validates the action and remains authoritative about legal actions and chip accounting.

Raise amounts are **the player's total contribution to the current betting street**, not the additional amount to put in. For example, if the player has already bet 20 this street, `raise(amount=60)` means the player's total street contribution will be 60.

The current MVP runs player decisions in-process. The `Player` protocol is deliberately small so async or external-process adapters can be added later.

## State transition outline

`HAND_START -> PREFLOP -> FLOP -> TURN -> RIVER -> SHOWDOWN -> SETTLEMENT`

A hand can instead terminate early when all but one player fold. If no further betting is possible because all remaining players are all-in, the engine deals the remaining board automatically.

## Testing

```bash
python -m unittest discover -s tests -v
```

The tests focus on hand ranking, legal actions, side pots, odd chips, and complete hands. This is an MVP; for production use, expand property-based testing and compare evaluator results against an independent reference implementation.

## Browser UI (play-money learning table)

The browser adapter keeps the existing Python game engine authoritative. The browser only sends a player's selected action; the engine checks legality and updates chip stacks. The human seat is fixed at the bottom of the table, and the table supports 2–9 seats (one human plus AI opponents).

Install the optional API dependencies:

```bash
python -m pip install -e ".[web]"
```

Start the API from the project root:

```bash
PYTHONPATH=src python -m uvicorn poker_sim.web.api:app --reload --port 8000
```

In a second terminal, install and start the React/Vite frontend:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite forwards `/api` requests to the FastAPI server on port 8000. For a production frontend, run `npm run build`; FastAPI serves the generated `frontend/dist` directory when it exists.

All chips are non-purchasable, non-redeemable in-game counters. The current browser adapter is an MVP: it advances one hand at a time and exposes the human's private cards and public table state only.

## Browser table positions and action status

The browser session starts the first six-max hand with the human in MP (not BTN).
The button then advances normally between hands. For table sizes without an MP
seat, the first hand starts with the human on the first listed position.

The live table event includes each player's position, dealer-button marker,
street contribution, action status (`YOUR TURN`, `ACTED`, `WAITING`, `BLIND`,
`FOLD`, or `ALL IN`), and most recent action on the current street. The human
seat remains fixed at the bottom while AI seats follow engine seat numbering.

## Showdown card disclosure

At a showdown, the engine evaluates every live hand and settles all pots before
handling card disclosure. A player who wins any pot must show their cards;
losing showdown players may implement `decide_showdown(context)` and return
`"show"` or `"muck"`. Players without that optional method default to showing.
The browser human is prompted to choose when they lose at showdown. Mucking
hides the cards from the result display and hand-history reveal map; it does not
change hand evaluation or chip awards. Hands won without a showdown are not
revealed.
