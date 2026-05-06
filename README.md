# Hermes Account Plugin

这是一个独立的 Hermes 插件，为 Hermes 增加 `/account` slash command，用来查看账号额度和套餐配额。

## 当前状态

当前版本 **只支持 Z.AI / GLM**。

还 **不支持**：

- OpenAI Codex
- Anthropic
- OpenRouter
- 其他 provider

也就是说，当前这个插件的目标很明确：只补 ZAI Coding Plan / quota 的可见性，不去改 Hermes core 的 `/usage`。

## 功能

- 新增 `/account` 命令
- 读取 Z.AI / GLM 的额度接口
- 适配窄屏消息展示，适合 Feishu / gateway 场景
- 支持中英文两种输出
- 不覆盖 Hermes 内建 `/usage`

## 安装

1. 把插件仓库放到一个固定目录。
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

可选值：

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

如果配置里也没有，就默认用英文。

## 说明

- 这个插件是独立插件，不改 Hermes core
- 这个插件不会覆盖 `/usage`
- 由于 plugin slash command 当前拿不到完整的平台和用户上下文，所以语言不会按用户自动识别，而是走插件配置或命令参数
