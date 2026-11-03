from __future__ import annotations
from queue import Empty
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path

from .session import GameSession

app = FastAPI(title="Poker Learning Table", version="0.1.0")
SESSIONS: dict[str, GameSession] = {}
SESSIONS_LOCK = Lock()


class CreateSession(BaseModel):
    player_count: int = Field(default=6, ge=2, le=9)
    starting_stack: int = Field(default=1000, ge=100, le=100000)
    small_blind: int = Field(default=5, ge=1, le=10000)
    big_blind: int = Field(default=10, ge=1, le=20000)
    seed: int | None = None


class PlayerAction(BaseModel):
    type: str
    amount: int | None = None


class ShowdownDecision(BaseModel):
    decision: str


def get_session(session_id: str) -> GameSession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sessions")
def create_session(config: CreateSession):
    if config.big_blind < config.small_blind:
        raise HTTPException(status_code=422, detail="big_blind must be >= small_blind")
    try:
        session = GameSession(**config.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with SESSIONS_LOCK:
        SESSIONS[session.id] = session
    return {"session_id": session.id, "player_count": config.player_count}


@app.get("/api/sessions/{session_id}/events")
def get_events(session_id: str, timeout: float = 15.0):
    session = get_session(session_id)
    return session.get_event(max(0.1, min(timeout, 25.0)))


@app.post("/api/sessions/{session_id}/actions")
def submit_action(session_id: str, action: PlayerAction):
    session = get_session(session_id)
    try:
        session.submit_action(action.model_dump())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"accepted": True}


@app.post("/api/sessions/{session_id}/showdown-decision")
def submit_showdown_decision(session_id: str, payload: ShowdownDecision):
    session = get_session(session_id)
    try:
        session.submit_showdown_decision(payload.decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"accepted": True}


@app.post("/api/sessions/{session_id}/next-hand")
def next_hand(session_id: str):
    get_session(session_id).start_next_hand()
    return {"accepted": True}


FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
