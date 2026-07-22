from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from .core import get_settings
from .schemas import Role, User


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt, expected = encoded.split("$")
        actual = hash_password(password, _unb64(salt)).split("$")[-1]
        return hmac.compare_digest(actual, expected)
    except ValueError:
        return False


def create_token(user: User, lifetime: int = 8 * 60 * 60) -> str:
    settings = get_settings()
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(
        json.dumps(
            {
                "sub": user.id,
                "tenant_id": user.tenant_id,
                "role": user.role.value,
                "email": user.email,
                "name": user.name,
                "exp": int(time.time()) + lifetime,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64(hmac.new(settings.jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header, payload, signature = token.split(".")
        expected = _b64(
            hmac.new(settings.jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        decoded = json.loads(_unb64(payload))
        if decoded["exp"] < time.time():
            raise ValueError("expired")
        return decoded
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def current_user(authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(authorization.removeprefix("Bearer "))
    return User(
        id=payload["sub"],
        tenant_id=payload["tenant_id"],
        email=payload["email"],
        name=payload["name"],
        role=Role(payload["role"]),
    )


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Role is not permitted")
        return user

    return dependency

