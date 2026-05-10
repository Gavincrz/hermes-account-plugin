# Agent 指令

## 环境

- Python 运行与测试使用 Hermes 虚拟环境：`/home/dontstarve/.hermes/hermes-agent/venv/bin/python`
- 禁止向系统 Python 安装任何包
- 安装依赖前必须说明必要性并得到用户明确同意
- 若依赖不适合进入 Hermes venv，应改为独立进程集成

## 测试

```bash
/home/dontstarve/.hermes/hermes-agent/venv/bin/python -m pytest tests/
```

- 行为变化必须补测试
- 测试使用 pytest，外部依赖用 monkeypatch 隔离

## 代码风格

- 所有模块开头 `from __future__ import annotations`
- 值对象用 `@dataclass(frozen=True)`
- 类型标注用 `str | None` 而非 `Optional[str]`
- 私有函数 `_` 前缀，常量 `UPPER_SNAKE_CASE`
- `__init__.py` 只做注册接线，不放业务逻辑
- 双导入模式兼容包内加载和直接测试

## 开发纪律

- 一次只做一个聚焦变更，不顺手扩大 scope
- 优先复用已有逻辑，不复制相似代码后局部修改
- 行为变化必须补测试，或在结果中说明未补的原因
- 出现 2-3 处相似实现时，默认视为需要整理结构

## 诊断

- 遇到 bug 先定位根因，确认诊断后再改代码
- 不靠猜测性补丁推进

## 收尾

- 未经用户明确要求，不提交 commit
- 当改动形成清晰、独立、可回滚的检查点时，询问用户是否提交
