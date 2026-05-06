from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from agent.account_usage import (
    AccountUsageSnapshot,
    AccountUsageWindow,
    fetch_account_usage as fetch_core_account_usage,
    render_account_usage_lines,
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
_HELP_TEXT = (
    "Usage: /account [provider]\n"
    "Examples: /account, /account zai, /account openai-codex"
)


@dataclass(frozen=True)
class ResolvedAccountTarget:
    provider: str
    base_url: str
    api_key: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _title_case_slug(value: Optional[str]) -> Optional[str]:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    return cleaned.replace("_", " ").replace("-", " ").title()


def _parse_dt(value: Any) -> Optional[datetime]:
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


def _normalize_provider(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    return _PROVIDER_ALIASES.get(normalized, normalized)


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


def _resolve_target(requested_provider: str) -> Optional[ResolvedAccountTarget]:
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
    base_url: Optional[str],
    api_key: Optional[str],
) -> Optional[AccountUsageSnapshot]:
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

    window_5h: Optional[AccountUsageWindow] = None
    window_weekly: Optional[AccountUsageWindow] = None
    window_mcp: Optional[AccountUsageWindow] = None
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
                    details.append("MCP usage: " + " | ".join(parts))

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


def _fetch_snapshot(target: ResolvedAccountTarget) -> Optional[AccountUsageSnapshot]:
    if target.provider == "zai":
        return _fetch_zai_account_usage(target.base_url, target.api_key)
    return fetch_core_account_usage(
        target.provider,
        base_url=target.base_url,
        api_key=target.api_key,
    )


def handle_account_command(raw_args: str) -> str:
    args = str(raw_args or "").strip()
    if args in {"-h", "--help", "help"}:
        return _HELP_TEXT

    requested_provider = args.split()[0] if args else ""
    target = _resolve_target(requested_provider)
    if target is None:
        return (
            "Could not resolve an account provider from the current runtime.\n"
            f"{_HELP_TEXT}"
        )

    snapshot = _fetch_snapshot(target)
    if snapshot is None:
        return (
            f"No account limit data available for provider '{target.provider}'.\n"
            f"{_HELP_TEXT}"
        )

    return "\n".join(render_account_usage_lines(snapshot))
