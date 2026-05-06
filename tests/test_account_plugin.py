from datetime import datetime, timezone

from agent.account_usage import AccountUsageSnapshot, AccountUsageWindow
from account_plugin import (
    _fetch_snapshot,
    _resolve_target,
    handle_account_command,
)


def test_resolve_target_uses_runtime_provider(monkeypatch):
    monkeypatch.setattr(
        "account_plugin.resolve_runtime_provider",
        lambda **kwargs: {
            "provider": "zai",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "api_key": "key-123",
        },
    )

    target = _resolve_target("")

    assert target is not None
    assert target.provider == "zai"
    assert target.base_url == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert target.api_key == "key-123"


def test_fetch_snapshot_routes_zai_to_plugin_fetch(monkeypatch):
    monkeypatch.setattr(
        "account_plugin._fetch_zai_account_usage",
        lambda base_url, api_key: AccountUsageSnapshot(
            provider="zai",
            source="quota_api",
            fetched_at=datetime.now(timezone.utc),
            plan="Pro",
            windows=(
                AccountUsageWindow(label="Weekly", used_percent=14.0),
            ),
        ),
    )

    snapshot = _fetch_snapshot(
        type("Target", (), {
            "provider": "zai",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "api_key": "key-123",
        })()
    )

    assert snapshot is not None
    assert snapshot.provider == "zai"
    assert snapshot.plan == "Pro"


def test_handle_account_command_formats_snapshot(monkeypatch):
    monkeypatch.setattr(
        "account_plugin._resolve_target",
        lambda requested: type("Target", (), {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "key-123",
        })(),
    )
    monkeypatch.setattr(
        "account_plugin._fetch_snapshot",
        lambda target: AccountUsageSnapshot(
            provider="openrouter",
            source="credits_api",
            fetched_at=datetime.now(timezone.utc),
            windows=(
                AccountUsageWindow(label="API key quota", used_percent=30.0),
            ),
            details=("Credits balance: $12.34",),
        ),
    )

    output = handle_account_command("")

    assert "Account limits" in output
    assert "Provider: openrouter" in output
    assert "Credits balance: $12.34" in output
