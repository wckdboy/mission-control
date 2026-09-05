from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import SessionLocal, init_db
from .deps import ws_actor
from .events import hub
from .models import Agent
from .api import router


def seed_defaults() -> None:
    db = SessionLocal()
    try:
        for entry in [s.strip() for s in settings.agent_seeds.split(",") if s.strip()]:
            handle, display, role = (entry.split("=") + ["", ""])[:3]
            if not db.query(Agent).filter(Agent.handle == handle).first():
                db.add(Agent(handle=handle, display_name=display or handle, role=role or ""))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_defaults()
    yield


app = FastAPI(title="Mission Control", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True}


@app.websocket("/ws/{room}")
async def websocket_room(websocket: WebSocket, room: str):
    db = SessionLocal()
    try:
        actor = ws_actor(websocket, db)
        if actor is None:
            await websocket.close(code=4401)
            return
        await hub.connect(room, websocket)
        try:
            while True:
                await websocket.receive_text()  # keepalive / ping
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(room, websocket)
    finally:
        db.close()
