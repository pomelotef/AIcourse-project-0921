"""Password hashing (stdlib scrypt) and opaque session tokens."""

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from .config import SESSION_COOKIE, settings
from .db import get_db
from .models import AuthSession, User, utcnow

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=64)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, dk_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(dk_hex) // 2
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), dk_hex)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=settings.session_days),
        )
    )
    db.commit()
    return token


def delete_session(db: Session, token: str) -> None:
    db.query(AuthSession).filter(AuthSession.token_hash == _hash_token(token)).delete()
    db.commit()


def current_user(
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    if not token:
        raise HTTPException(401, "請先登入")
    sess = db.get(AuthSession, _hash_token(token))
    if sess is None or sess.expires_at < utcnow():
        raise HTTPException(401, "登入已過期，請重新登入")
    user = db.get(User, sess.user_id)
    if user is None:
        raise HTTPException(401, "請先登入")
    return user
