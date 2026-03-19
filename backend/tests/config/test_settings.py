from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_from_dotenv():
    """Keep settings tests independent of a local .env file."""

    from flowforge.config import Settings

    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    try:
        yield
    finally:
        if original_env_file is None:
            Settings.model_config.pop("env_file", None)
        else:
            Settings.model_config["env_file"] = original_env_file


def test_settings_tool_gateway_defaults_when_env_missing(monkeypatch):
    from flowforge.config import get_settings

    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_URL", raising=False)
    monkeypatch.delenv("FLOWFORGE_TOOL_GATEWAY_JWT", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.tool_gateway_url == "http://tool-gateway:8010"
    assert settings.tool_gateway_jwt == ""


def test_settings_tool_gateway_env_overrides(monkeypatch):
    from flowforge.config import get_settings

    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_URL", "http://example:9999")
    monkeypatch.setenv("FLOWFORGE_TOOL_GATEWAY_JWT", "test-jwt")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.tool_gateway_url == "http://example:9999"
    assert settings.tool_gateway_jwt == "test-jwt"
