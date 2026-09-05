import hashlib
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

_serializer = URLSafeTimedSerializer(settings.session_secret, salt="mc-session")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def check_operator_password(password: str) -> bool:
    if settings.operator_password_hash:
        return secrets.compare_digest(sha256(password), settings.operator_password_hash)
    return secrets.compare_digest(password, settings.operator_password)


def make_session_token() -> str:
    return _serializer.dumps({"sub": "operator"})


def read_session_token(token: str, max_age: int = 60 * 60 * 24 * 7) -> bool:
    try:
        data = _serializer.loads(token, max_age=max_age)
        return data.get("sub") == "operator"
    except (BadSignature, SignatureExpired):
        return False


def new_agent_token() -> str:
    return secrets.token_urlsafe(32)
