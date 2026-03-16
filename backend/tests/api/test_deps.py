"""Tests for deps.py: get_current_user, require_admin."""

import time
import pytest
import jwt
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from flowforge.api.deps import get_current_user, require_admin, security

JWT_SECRET = "dev-secret-change-in-production"


def make_token(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def make_app_with_user_endpoint():
    """Create a tiny app with a /me endpoint for testing."""
    app = FastAPI()

    @app.get("/me")
    def me(user: dict = Depends(get_current_user)):
        return user

    @app.get("/admin")
    def admin(user: dict = Depends(require_admin)):
        return user

    return app


class TestGetCurrentUser:
    def setup_method(self):
        self.app = make_app_with_user_endpoint()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_valid_jwt_returns_payload(self):
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-abc",
            "role": "editor",
            "exp": int(time.time()) + 3600,
        }
        token = make_token(payload)
        resp = self.client.get("/me", headers=self._auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "user-123"
        assert data["tenant_id"] == "tenant-abc"
        assert data["role"] == "editor"

    def test_expired_jwt_returns_401(self):
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-abc",
            "role": "editor",
            "exp": int(time.time()) - 1,  # already expired
        }
        token = make_token(payload)
        resp = self.client.get("/me", headers=self._auth(token))
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    def test_invalid_token_returns_401(self):
        resp = self.client.get("/me", headers=self._auth("not-a-real-jwt"))
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_missing_token_returns_401_or_403(self):
        resp = self.client.get("/me")
        assert resp.status_code in (401, 403)

    def test_wrong_secret_returns_401(self):
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-abc",
            "role": "editor",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        resp = self.client.get("/me", headers=self._auth(token))
        assert resp.status_code == 401


class TestRequireAdmin:
    def setup_method(self):
        self.app = make_app_with_user_endpoint()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _auth(self, role: str) -> dict:
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-abc",
            "role": role,
            "exp": int(time.time()) + 3600,
        }
        token = make_token(payload)
        return {"Authorization": f"Bearer {token}"}

    def test_admin_role_succeeds(self):
        resp = self.client.get("/admin", headers=self._auth("admin"))
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_editor_role_gets_403(self):
        resp = self.client.get("/admin", headers=self._auth("editor"))
        assert resp.status_code == 403

    def test_viewer_role_gets_403(self):
        resp = self.client.get("/admin", headers=self._auth("viewer"))
        assert resp.status_code == 403
