from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from agent.account_usage import (
    AccountUsageSnapshot,
    AccountUsageWindow,
    fetch_account_usage as fetch_core_account_usage,
)
from hermes_cli.config import load_config
from hermes_cli.runtime_provider import resolve_runtime_provider
from utils import base_url_host_matches

ZAI_QUOTA_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
_PROVIDER_ALIASES = {
    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",
}
_LANG_ALIASES = {
    "en": "en",
    "en-us": "en",
    "en_us": "en",
    "english": "en",
    "zh": "zh",
    "zh-cn": "zh",
    "zh_cn": "zh",
    "cn": "zh",
    "chinese": "zh",
}
_TEXT = {
    "en": {
        "help": (
            "Usage: /account [provider] [--lang en|zh]\n"
            "Examples: /account zai, /account zai --lang zh"
        ),
        "resolve_error": "Could not resolve a supported account provider from the current runtime.",
        "unsupported_provider": "Provider '{provider}' is not supported yet. Only 'zai' is supported today.",
        "no_data": "No account limit data available for provider '{provider}'.",
        "title": "📈 **Account limits**",
        "provider": "Provider: `{provider}`",
        "remaining": "{label}: {remaining}% remaining",
        "used": "{used}% used",
        "resets": "resets {rel} ({abs_time})",
        "now": "now",
        "unavailable": "{label}: unavailable",
        "mcp_usage": "MCP usage",
        "unavailable_reason": "Unavailable: {reason}",
        "plan_sep": " ({plan})",
    },
    "zh": {
        "help": (
            "用法：/account [provider] [--lang en|zh]\n"
            "示例：/account zai, /account zai --lang zh"
        ),
        "resolve_error": "当前运行环境里无法解析出受支持的账号提供方。",
        "unsupported_provider": "提供方 '{provider}' 暂不支持，目前只支持 'zai'。",
        "no_data": "提供方 '{provider}' 当前没有可用的额度数据。",
        "title": "📈 **账户额度**",
        "provider": "提供方：`{provider}`",
        "remaining": "{label}：剩余 {remaining}%",
        "used": "已用 {used}%",
        "resets": "{rel} 重置（{abs_time}）",
        "now": "现在",
        "unavailable": "{label}：不可用",
        "mcp_usage": "MCP 使用明细",
        "unavailable_reason": "不可用：{reason}",
        "plan_sep": "（{plan}）",
    },
}
_WINDOW_LABELS = {
    "en": {
        "5h rolling": "5h rolling",
        "Weekly": "Weekly",
        "MCP monthly": "MCP monthly",
    },
    "zh": {
        "5h rolling": "5 小时滚动",
        "Weekly": "每周",
        "MCP monthly": "MCP 月度",
    },
}


@dataclass(frozen=True)
class ResolvedAccountTarget:
    provider: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class CommandOptions:
    provider: str
    language: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _title_case_slug(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    return cleaned.replace("_", " ").replace("-", " ").title()


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _normalize_provider(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return _PROVIDER_ALIASES.get(normalized, normalized)


def _normalize_language(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return _LANG_ALIASES.get(normalized, "")


def _plugin_language_from_config() -> str:
    try:
        cfg = load_config()
    except Exception:
        return "en"
    plugins_cfg = cfg.get("plugins") if isinstance(cfg, dict) else None
    if not isinstance(plugins_cfg, dict):
        return "en"
    account_cfg = plugins_cfg.get("account")
    if not isinstance(account_cfg, dict):
        return "en"
    return _normalize_language(account_cfg.get("language")) or "en"


def _parse_args(raw_args: str) -> CommandOptions:
    parts = str(raw_args or "").strip().split()
    provider = ""
    language = ""
    i = 0
    while i < len(parts):
        part = parts[i]
        if part in {"--lang", "--language"} and i + 1 < len(parts):
            language = _normalize_language(parts[i + 1]) or language
            i += 2
            continue
        if not provider and not part.startswith("--"):
            provider = part
        i += 1
    return CommandOptions(
        provider=_normalize_provider(provider),
        language=language or _plugin_language_from_config(),
    )


def _infer_provider_from_base_url(base_url: str) -> str:
    if base_url_host_matches(base_url, "api.z.ai") or base_url_host_matches(base_url, "open.bigmodel.cn"):
        return "zai"
    if base_url_host_matches(base_url, "openrouter.ai"):
        return "openrouter"
    if base_url_host_matches(base_url, "api.anthropic.com"):
        return "anthropic"
    if base_url_host_matches(base_url, "chatgpt.com"):
        return "openai-codex"
    return ""


def _resolve_provider_from_config() -> str:
    try:
        cfg = load_config()
    except Exception:
        return ""
    model_cfg = cfg.get("model") if isinstance(cfg, dict) else None
    if isinstance(model_cfg, dict):
        provider = _normalize_provider(model_cfg.get("provider"))
        if provider not in {"", "auto", "custom"}:
            return provider
        base_url = str(model_cfg.get("base_url") or "").strip()
        inferred = _infer_provider_from_base_url(base_url)
        if inferred:
            return inferred
    return ""


def _resolve_target(requested_provider: str) -> ResolvedAccountTarget | None:
    requested = _normalize_provider(requested_provider) or "auto"
    runtime: dict[str, Any] = {}
    try:
        runtime = resolve_runtime_provider(requested=requested)
    except Exception:
        runtime = {}

    provider = _normalize_provider(runtime.get("provider"))
    base_url = str(runtime.get("base_url") or "").strip()
    api_key = str(runtime.get("api_key") or "").strip()

    if requested != "auto":
        provider = requested or provider
    if provider in {"", "auto", "custom"}:
        inferred = _infer_provider_from_base_url(base_url)
        provider = inferred or provider
    if provider in {"", "auto", "custom"}:
        provider = _resolve_provider_from_config() or provider

    if provider in {"", "auto", "custom"}:
        return None
    return ResolvedAccountTarget(provider=provider, base_url=base_url, api_key=api_key)


def _fetch_zai_account_usage(
    base_url: str | None,
    api_key: str | None,
) -> AccountUsageSnapshot | None:
    runtime = resolve_runtime_provider(
        requested="zai",
        explicit_base_url=base_url,
        explicit_api_key=api_key,
    )
    token = str(runtime.get("api_key", "") or "").strip()
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.get(ZAI_QUOTA_URL, headers=headers)
        response.raise_for_status()

    payload = response.json() or {}
    data = payload.get("data") or {}
    limits = data.get("limits") or []

    window_5h: AccountUsageWindow | None = None
    window_weekly: AccountUsageWindow | None = None
    window_mcp: AccountUsageWindow | None = None
    details: list[str] = []

    for limit in limits:
        if not isinstance(limit, dict):
            continue
        limit_type = str(limit.get("type", "") or "")
        percentage = limit.get("percentage")
        next_reset_ms = limit.get("nextResetTime")
        reset_at = None
        if isinstance(next_reset_ms, (int, float)) and next_reset_ms > 0:
            reset_at = _parse_dt(next_reset_ms / 1000)

        if limit_type == "TOKENS_LIMIT":
            unit = limit.get("unit")
            if percentage is not None:
                if unit == 3:
                    window_5h = AccountUsageWindow(
                        label="5h rolling",
                        used_percent=float(percentage),
                        reset_at=reset_at,
                    )
                elif unit == 6:
                    window_weekly = AccountUsageWindow(
                        label="Weekly",
                        used_percent=float(percentage),
                        reset_at=reset_at,
                    )
        elif limit_type == "TIME_LIMIT":
            if percentage is not None:
                window_mcp = AccountUsageWindow(
                    label="MCP monthly",
                    used_percent=float(percentage),
                    reset_at=reset_at,
                )
            usage_details = limit.get("usageDetails") or []
            if isinstance(usage_details, list) and usage_details:
                parts: list[str] = []
                for item in usage_details:
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get("modelCode", "") or "")
                    usage = item.get("usage")
                    if code and usage is not None:
                        parts.append(f"{code} {usage}")
                if parts:
                    details.append("MCP usage: " + " • ".join(parts))

    windows = tuple(
        window
        for window in (window_5h, window_weekly, window_mcp)
        if window is not None
    )
    return AccountUsageSnapshot(
        provider="zai",
        source="quota_api",
        fetched_at=_utc_now(),
        plan=_title_case_slug(data.get("level")),
        windows=windows,
        details=tuple(details),
    )


def _fetch_snapshot(target: ResolvedAccountTarget) -> AccountUsageSnapshot | None:
    if target.provider == "zai":
        return _fetch_zai_account_usage(target.base_url, target.api_key)
    return fetch_core_account_usage(
        target.provider,
        base_url=target.base_url,
        api_key=target.api_key,
    )


def _format_relative_time(dt: datetime, language: str) -> str:
    delta = dt - _utc_now()
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return _TEXT[language]["now"]
    hours, rem = divmod(total_seconds, 3600)
    minutes = rem // 60
    if language == "zh":
        if hours >= 24:
            days, hours = divmod(hours, 24)
            return f"{days}天{hours}小时后"
        if hours > 0:
            return f"{hours}小时{minutes}分钟后"
        return f"{minutes}分钟后"
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"in {days}d {hours}h"
    if hours > 0:
        return f"in {hours}h {minutes}m"
    return f"in {minutes}m"


def _format_snapshot(snapshot: AccountUsageSnapshot, language: str) -> str:
    text = _TEXT[language]
    lines = [text["title"]]
    provider_line = text["provider"].format(provider=snapshot.provider)
    if snapshot.plan:
        provider_line += text["plan_sep"].format(plan=snapshot.plan)
    lines.append(provider_line)

    if snapshot.windows:
        lines.append("")
        for window in snapshot.windows:
            label = _WINDOW_LABELS[language].get(window.label, window.label)
            if window.used_percent is None:
                lines.append(f"- {text['unavailable'].format(label=label)}")
            else:
                remaining = max(0, round(100 - float(window.used_percent)))
                used = max(0, round(float(window.used_percent)))
                lines.append(f"- {text['remaining'].format(label=label, remaining=remaining)}")
                lines.append(f"  {text['used'].format(used=used)}")
            if window.reset_at:
                local_dt = window.reset_at.astimezone()
                rel = _format_relative_time(window.reset_at, language)
                lines.append(
                    "  " + text["resets"].format(
                        rel=rel,
                        abs_time=local_dt.strftime("%Y-%m-%d %H:%M %Z"),
                    )
                )
            elif window.detail:
                lines.append(f"  {window.detail}")

    if snapshot.details:
        lines.append("")
        lines.append(text["mcp_usage"])
        for detail in snapshot.details:
            payload = detail.split(":", 1)[1].strip() if ":" in detail else detail
            for part in payload.split("•"):
                cleaned = part.strip()
                if cleaned:
                    if language == "zh" and " " in cleaned:
                        code, value = cleaned.rsplit(" ", 1)
                        lines.append(f"- {code}: {value}")
                    else:
                        lines.append(f"- {cleaned}")

    if snapshot.unavailable_reason:
        lines.append("")
        lines.append(text["unavailable_reason"].format(reason=snapshot.unavailable_reason))

    return "\n".join(lines)


def handle_account_command(raw_args: str) -> str:
    args = str(raw_args or "").strip()
    opts = _parse_args(args)
    text = _TEXT[opts.language]
    if args in {"-h", "--help", "help"}:
        return text["help"]

    target = _resolve_target(opts.provider)
    if target is None:
        return (
            f"{text['resolve_error']}\n"
            f"{text['help']}"
        )
    if target.provider != "zai":
        return text["unsupported_provider"].format(provider=target.provider)

    snapshot = _fetch_snapshot(target)
    if snapshot is None:
        return (
            f"{text['no_data'].format(provider=target.provider)}\n"
            f"{text['help']}"
        )

    return _format_snapshot(snapshot, opts.language)
