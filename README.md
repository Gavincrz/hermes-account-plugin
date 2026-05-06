# Hermes Account Plugin

Adds a standalone `/account` slash command for Hermes.

## What it does

- Shows provider account limits and quota details without modifying core `/usage`
- Keeps ZAI / GLM Coding Plan quota fetching inside the plugin
- Reuses Hermes core account-limit rendering for providers already supported upstream

## Install

1. Clone or copy this directory to a stable location.
2. Link or copy it into `~/.hermes/plugins/account`.
3. Add `account` to `plugins.enabled` in `~/.hermes/config.yaml`.

## Usage

- `/account`
- `/account zai`
- `/account openai-codex`

## Notes

- The command is best-effort in gateway surfaces because plugin slash commands do not receive full live session context.
- This plugin intentionally does not override the built-in `/usage` command.

