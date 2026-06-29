import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

import shared_db

SECRET_KEY = os.environ.get("JWT_SECRET", "servallab-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7
OTP_EXPIRE_MINUTES = 10


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    totp_enabled: bool = False


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class OtpChallenge(BaseModel):
    otp_required: bool = True
    user_id: int
    demo_otp: str


class VerifyOtpRequest(BaseModel):
    user_id: int
    code: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


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


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"], email=user["email"], name=user["full_name"], role=user["role"],
        totp_enabled=bool(user.get("totp_enabled")),
    )


@router.post("/auth/login", response_model=Union[LoginResponse, OtpChallenge])
def login(req: LoginRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_email(req.email.strip().lower())
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.get("totp_enabled"):
        code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
        expires_at = (datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat()
        shared_db.set_user_otp(user["id"], otp_hash, expires_at)
        # demo_otp is returned directly because this is a demo deployment with no email server —
        # a real deployment would email the code instead of including it in the response.
        return OtpChallenge(user_id=user["id"], demo_otp=code)

    token = _make_token(user["id"])
    return LoginResponse(token=token, user=_user_out(user))


@router.post("/auth/verify-otp", response_model=LoginResponse)
def verify_otp(req: VerifyOtpRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_id(req.user_id)
    if not user or not user.get("otp_code"):
        raise HTTPException(status_code=401, detail="No pending verification for this user")
    expires_at = user.get("otp_expires_at")
    if not expires_at or datetime.now(tz=timezone.utc) > datetime.fromisoformat(expires_at):
        shared_db.clear_user_otp(user["id"])
        raise HTTPException(status_code=401, detail="Code expired — please log in again")
    if not bcrypt.checkpw(req.code.encode(), user["otp_code"].encode()):
        raise HTTPException(status_code=401, detail="Invalid code")
    shared_db.clear_user_otp(user["id"])
    token = _make_token(user["id"])
    return LoginResponse(token=token, user=_user_out(user))


@router.post("/auth/enable-2fa", response_model=UserOut)
def enable_2fa(user: dict = Depends(get_current_user)):
    shared_db.set_2fa_enabled(user["id"], True)
    user["totp_enabled"] = 1
    return _user_out(user)


@router.post("/auth/disable-2fa", response_model=UserOut)
def disable_2fa(user: dict = Depends(get_current_user)):
    shared_db.set_2fa_enabled(user["id"], False)
    user["totp_enabled"] = 0
    return _user_out(user)


@router.post("/auth/register", response_model=LoginResponse)
def register(req: RegisterRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    ok, err = shared_db.create_user(
        req.email.strip().lower(), hashed, req.full_name.strip(), "other"
    )
    if not ok:
        raise HTTPException(status_code=409, detail=err)
    user = shared_db.get_user_by_email(req.email.strip().lower())
    token = _make_token(user["id"])
    return LoginResponse(token=token, user=_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return _user_out(user)
