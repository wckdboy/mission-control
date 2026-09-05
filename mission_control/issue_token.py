"""Issue a fresh agent token. Prints the plaintext ONCE — store it in the
agent's secret store (Hermes .env / Coolify) and never in git.

Usage:
    python -m mission_control.issue_token jaeger
"""
import sys

from .db import SessionLocal
from .models import Agent
from .security import new_agent_token, sha256


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m mission_control.issue_token <agent_handle>")
        raise SystemExit(2)
    handle = sys.argv[1].lower()
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.handle == handle).first()
        if not agent:
            print(f"unknown agent: {handle}")
            raise SystemExit(1)
        token = new_agent_token()
        agent.token_hash = sha256(token)
        db.commit()
        print(f"agent={handle} token={token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
