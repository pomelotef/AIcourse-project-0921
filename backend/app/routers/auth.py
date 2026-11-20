from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..config import SESSION_COOKIE, settings
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, RegisterIn
from ..security import create_session, current_user, delete_session, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_days * 86400,
        path="/",
    )


def _me(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "此 email 已註冊")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _set_cookie(response, create_session(db, user))
    return _me(user)


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email 或密碼錯誤")
    _set_cookie(response, create_session(db, user))
    return _me(user)


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    if token:
        delete_session(db, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _me(user)
