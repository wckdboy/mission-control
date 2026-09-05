from fastapi import Cookie, Depends, Header, HTTPException, WebSocket
from sqlalchemy.orm import Session

from . import security
from .db import get_db
from .models import Agent


def current_operator(session: str | None = Cookie(default=None)) -> str:
    if not session or not security.read_session_token(session):
        raise HTTPException(status_code=401, detail="Operator session required")
    return "operator"


def current_agent(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Agent:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Agent token required")
    token = authorization.split(" ", 1)[1].strip()
    agent = (
        db.query(Agent)
        .filter(Agent.token_hash == security.sha256(token))
        .first()
    )
    if not agent:
        raise HTTPException(status_code=401, detail="Unknown agent token")
    return agent


def ws_actor(websocket: WebSocket, db: Session):
    """Resolve operator or agent identity from WS query token / cookie."""
    token = websocket.query_params.get("token", "")
    if token:
        agent = (
            db.query(Agent)
            .filter(Agent.token_hash == security.sha256(token))
            .first()
        )
        if agent:
            return ("agent", agent.id)
        return None
    cookie = websocket.headers.get("cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("session="):
            if security.read_session_token(part.split("=", 1)[1]):
                return ("operator", None)
    return None
