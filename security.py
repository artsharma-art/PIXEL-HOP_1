import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, dk = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc, _unb64(dk))
    except Exception:
        return False


def make_token(user_id: int, secret: str, ttl: int) -> str:
    body = f"{user_id}.{int(time.time()) + ttl}"
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: Optional[str], secret: str) -> Optional[int]:
    if not token:
        return None
    try:
        uid, exp, sig = token.split(".")
        good = hmac.new(secret.encode(), f"{uid}.{exp}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good) or int(exp) < time.time():
            return None
        return int(uid)
    except Exception:
        return None
