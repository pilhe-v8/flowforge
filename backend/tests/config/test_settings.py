from __future__ import annotations


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
