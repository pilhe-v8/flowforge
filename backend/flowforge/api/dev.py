"""Dev-only endpoints.

These routes are intentionally gated behind FLOWFORGE_DEV_MODE.
"""

import time

from fastapi import APIRouter, HTTPException
import jwt

from flowforge.config import get_settings


router = APIRouter(tags=["dev"])


@router.get("/dev/token")
async def mint_dev_token() -> dict:
    settings = get_settings()
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")

    payload = {
        "sub": "dev-user",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "role": "admin",
        "exp": int(time.time()) + 86400 * 30,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.algorithm)
    return {"token": token}
