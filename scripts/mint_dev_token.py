#!/usr/bin/env python3
"""
Mints a dev JWT for local development.

Usage:
    python scripts/mint_dev_token.py

Prints the JWT to stdout. Copy it into frontend/.env.local as:
    VITE_DEV_JWT=<token>

The frontend's App.tsx reads VITE_DEV_JWT and auto-sets it in localStorage on startup.
"""

import time
import jwt

SECRET = "dev-secret-change-in-production"
ALGORITHM = "HS256"


def main():
    # Use a fixed UUID so it stays stable across runs
    tenant_id = "00000000-0000-0000-0000-000000000001"
    payload = {
        "sub": "dev-user",
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int(time.time()) + 86400 * 30,  # 30 days
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    print(token)


if __name__ == "__main__":
    main()
