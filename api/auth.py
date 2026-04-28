"""
用户认证模块
JWT-based authentication with password hashing
"""

import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import logging

import bcrypt

logger = logging.getLogger(__name__)

import jwt
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from storage import get_store

# ============================================================
# JWT Configuration
# ============================================================

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 72  # 3 days

# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)
limiter = Limiter(key_func=get_remote_address)


# ============================================================
# Request / Response Models
# ============================================================

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    username: str
    token: str
    expires_at: str


class UserInfo(BaseModel):
    user_id: str
    username: str


# ============================================================
# Password Hashing
# ============================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain password against its hash.

    Supports bcrypt (prefix $2) and legacy SHA-256.
    """
    if password_hash.startswith("$2"):
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))

    # Legacy SHA-256 fallback
    sha256_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return sha256_hash == password_hash


def is_legacy_hash(password_hash: str) -> bool:
    """Check if a hash is legacy SHA-256 (needs upgrade)."""
    return not password_hash.startswith("$2")


# ============================================================
# JWT Token Helpers
# ============================================================

def create_token(user_id: str, username: str) -> tuple[str, str]:
    """
    Create a JWT token for the given user.
    Returns (token, expires_at_iso).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at.isoformat()


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises HTTPException on invalid/expired tokens.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ============================================================
# Dependency: get_current_user
# ============================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency that extracts the current user from the
    Authorization: Bearer <token> header.

    Returns {"user_id": ..., "username": ...} on success.
    Raises 401 if no token or invalid token.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(credentials.credentials)

    user_id = payload.get("sub")
    username = payload.get("username")

    if not user_id or not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Verify user still exists in database
    store = get_store()
    user = store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    return {"user_id": user_id, "username": username}


# ============================================================
# Endpoints
# ============================================================

@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    """Register a new user with username and password."""
    username = body.username.strip()
    password = body.password.strip()

    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    store = get_store()

    # Check if username already exists
    existing = store.get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat()

    store.create_user(
        user_id=user_id,
        username=username,
        password_hash=password_hash,
        created_at=created_at,
    )

    token, expires_at = create_token(user_id, username)

    return AuthResponse(
        user_id=user_id,
        username=username,
        token=token,
        expires_at=expires_at,
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    """Login with username and password, returns JWT token."""
    username = body.username.strip()
    password = body.password.strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    store = get_store()
    user = store.get_user_by_username(username)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Upgrade legacy SHA-256 hash to bcrypt
    if is_legacy_hash(user["password_hash"]):
        try:
            new_hash = hash_password(password)
            store.update_user_password_hash(user["user_id"], new_hash)
        except Exception:
            logger.warning("Failed to rehash password for user %s", user["user_id"])

    token, expires_at = create_token(user["user_id"], user["username"])

    return AuthResponse(
        user_id=user["user_id"],
        username=user["username"],
        token=token,
        expires_at=expires_at,
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return UserInfo(
        user_id=current_user["user_id"],
        username=current_user["username"],
    )
