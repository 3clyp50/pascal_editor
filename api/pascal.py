"""API surface for the Pascal Editor plugin.

Serves status/ensure/stop/restart/health actions and lazily registers the
same-origin ``/pascal`` proxy route on the live Flask app, so the editor can
be enabled on a running instance without a framework restart.
"""
from __future__ import annotations

from helpers.api import ApiHandler, Request
from usr.plugins.pascal_editor.helpers import runtime
from usr.plugins.pascal_editor.helpers.proxy import install_proxy_routes


class PascalEditor(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    async def process(self, input: dict, request: Request) -> dict:
        # Make the /pascal proxy route available on this live server
        # instance (idempotent; no-op once registered).
        try:
            install_proxy_routes(self.app)
        except Exception:  # noqa: BLE001
            pass

        action = str(
            (input or {}).get("action") or request.args.get("action") or "status"
        ).strip().lower()
        config = runtime.get_config()

        if action in {"ensure", "start", "open"}:
            result = runtime.ensure_running(config)
        elif action in {"stop", "shutdown"}:
            result = runtime.stop_runtime(config)
        elif action in {"restart", "reload"}:
            runtime.stop_runtime(config)
            result = runtime.ensure_running(config)
        elif action == "health":
            result = {"healthy": True, **runtime.health(timeout=3.0)}
        else:
            result = runtime.get_status(config)

        result.setdefault("url", "/pascal/")
        return result
