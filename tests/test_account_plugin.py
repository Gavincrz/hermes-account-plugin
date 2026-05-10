from datetime import datetime, timezone

from agent.account_usage import AccountUsageSnapshot, AccountUsageWindow
from account_plugin import (
    _parse_args,
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


def test_parse_args_supports_lang_override(monkeypatch):
    monkeypatch.setattr(
        "account_plugin._plugin_language_from_config",
        lambda: "en",
    )

    opts = _parse_args("zai --lang zh")

    assert opts.provider == "zai"
    assert opts.language == "zh"


def test_handle_account_command_formats_snapshot(monkeypatch):
    monkeypatch.setattr(
        "account_plugin._resolve_target",
        lambda requested: type("Target", (), {
            "provider": "zai",
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
            "api_key": "key-123",
        })(),
    )
    monkeypatch.setattr(
        "account_plugin._fetch_snapshot",
        lambda target: AccountUsageSnapshot(
            provider="zai",
            source="quota_api",
            fetched_at=datetime.now(timezone.utc),
            windows=(
                AccountUsageWindow(label="Weekly", used_percent=30.0),
            ),
            details=("MCP usage: search-prime 12 • web-reader 3",),
        ),
    )

    output = handle_account_command("zai --lang zh")

    assert "账户额度" in output
    assert "提供方：`zai`" in output
    assert "每周：剩余 70%" in output
    assert "MCP 使用明细" in output


def test_handle_account_command_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(
        "account_plugin._resolve_target",
        lambda requested: type("Target", (), {
            "provider": "openai-codex",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "key-123",
        })(),
    )

    output = handle_account_command("openai-codex")

    assert "not supported yet" in output or "暂不支持" in output
