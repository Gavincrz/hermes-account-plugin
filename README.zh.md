# Hermes Account Plugin

English version: [README.md](./README.md)

这是一个独立的 Hermes 插件，为 Hermes 增加 `/account` slash command，用来查看账号额度和套餐配额。

## 当前范围

当前版本 **只支持 Z.AI / GLM**。

还 **不支持**：

- OpenAI Codex
- Anthropic
- OpenRouter
- 其他 provider

当前这个插件的目标是有意收窄的：只补 ZAI Coding Plan / quota 的可见性，不去修改 Hermes core 的 `/usage`。

## 功能

- 新增 `/account` 命令
- 读取 Z.AI / GLM 的额度接口
- 使用更适合 Feishu 等 gateway 窄屏消息的紧凑排版
- 支持中英文输出
- 不覆盖 Hermes 内建 `/usage`

## 安装

1. 把插件仓库放到一个固定目录
2. 链接或复制到 `~/.hermes/plugins/account`
3. 在 `~/.hermes/config.yaml` 里启用插件：

```yaml
plugins:
  enabled:
    - account
```

## 配置

插件支持自己的语言配置，默认英文：

```yaml
plugins:
  enabled:
    - account
  account:
    language: en
```

支持的值：

- `en`
- `zh`

默认值：

- `en`

## 用法

当前只支持 `zai`：

```text
/account zai
/account zai --lang zh
/account zai --lang en
```

如果不传 `--lang`，会读取：

```yaml
plugins:
  account:
    language: en
```

如果配置里没有，就回退到英文。

## 说明

- 这是独立插件，不修改 Hermes core
- 不会覆盖 `/usage`
- 由于 plugin slash command 当前拿不到完整的平台和用户上下文，所以语言不会按用户自动识别，而是走插件配置或命令参数
