try:
    from .account_plugin import handle_account_command
except ImportError:  # pragma: no cover - direct test import path
    from account_plugin import handle_account_command


def register(ctx) -> None:
    ctx.register_command(
        "account",
        handler=handle_account_command,
        description="Show provider account limits and quota details.",
        args_hint="[provider]",
    )
