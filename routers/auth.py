import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

import shared_db

SECRET_KEY = os.environ.get("JWT_SECRET", "servallab-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


router = APIRouter()


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def _make_token(user_id: int) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except Exception:
        return None


def get_current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency — resolves Bearer token → user dict or raises 401."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = _decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_email(req.email.strip().lower())
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _make_token(user["id"])
    return LoginResponse(
        token=token,
        user=UserOut(id=user["id"], email=user["email"], name=user["full_name"], role=user["role"]),
    )


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], email=user["email"], name=user["full_name"], role=user["role"])
