"""Shared FastAPI dependencies: JWT auth, tenant filter."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from flowforge.config import get_settings

settings = get_settings()
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Decode JWT, return payload dict with sub, tenant_id, role."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Raises 403 if user role != admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user


def get_tenant_id(user: dict = Depends(get_current_user)) -> str:
    """Extract tenant_id from JWT payload."""
    return user["tenant_id"]
