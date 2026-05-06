# Hermes Account Plugin

中文说明见：[README.zh.md](./README.zh.md)

This is a standalone Hermes plugin that adds an `/account` slash command for account-limit and quota visibility.

## Current scope

This plugin currently supports **Z.AI / GLM only**.

It does **not** support these providers yet:

- OpenAI Codex
- Anthropic
- OpenRouter
- Other providers

The current goal is intentionally narrow: provide ZAI Coding Plan / quota visibility without modifying Hermes core `/usage`.

## Features

- Adds `/account`
- Fetches Z.AI / GLM quota data
- Uses compact narrow-screen formatting that works better in gateway surfaces such as Feishu
- Supports bilingual output: English and Chinese
- Does not override Hermes built-in `/usage`

## Install

1. Place this plugin repo in a stable local directory.
2. Link or copy it into `~/.hermes/plugins/account`
3. Enable it in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - account
```

## Configuration

The plugin has its own language setting. Default is English:

```yaml
plugins:
  enabled:
    - account
  account:
    language: en
```

Supported values:

- `en`
- `zh`

Default:

- `en`

## Usage

Only `zai` is supported today:

```text
/account zai
/account zai --lang zh
/account zai --lang en
```

If `--lang` is omitted, the plugin reads:

```yaml
plugins:
  account:
    language: en
```

If the config value is missing, it falls back to English.

## Notes

- This is an external plugin and does not patch Hermes core
- It does not override `/usage`
- Plugin slash commands do not currently receive full platform/user context, so language is controlled by plugin config or explicit `--lang`, not automatic per-user locale detection

