"""One-shot, self-healing bootstrap for the live web UI process.

Agent Zero serves the web UI from a single long-lived process. If the
Pascal Editor plugin code is updated on disk *without* a framework restart,
that process may still hold a stale in-memory copy of ``helpers/proxy.py``.
The persistent boot path (startup extension + :mod:`api.pascal`) always
works on a clean boot; this handler additionally repairs an already-running
process by re-executing the current on-disk proxy source and registering
the same-origin ``/pascal`` routes on the live Flask app.

The handler is idempotent and already session-authenticated; calling it more
than once is a no-op once the routes are registered.
"""
from __future__ import annotations

import types
from pathlib import Path

from helpers.api import ApiHandler, Request

_PROXY_PATH = Path(__file__).resolve().parents[1] / "helpers" / "proxy.py"
_IMPL_MODULE = "pascal_editor_proxy_bootstrap_impl"


def _load_fresh_proxy_module():
    """Compile the on-disk proxy source into a brand-new module namespace.

    Re-executes the current file so the latest code runs even if the live
    process already cached an older ``helpers.proxy`` module. Package-relative
    imports inside the source (helpers.*, usr.plugins.*) resolve to the
    already-imported live modules, which we want to reuse.
    """
    source = _PROXY_PATH.read_text()
    module = types.ModuleType(_IMPL_MODULE)
    module.__file__ = str(_PROXY_PATH)
    module.__package__ = ""
    code = compile(source, str(_PROXY_PATH), "exec")
    exec(code, module.__dict__)  # noqa: S102 - controlled, same-host source
    return module


_ENDPOINTS = ("pascal_editor_proxy_root", "pascal_editor_proxy")


def _remove_pascal_routes(app) -> None:
    """Drop previously installed proxy rules/views so reinstall stays clean.

    Only meaningful on a live app (a clean boot starts empty).  Werkzeug's
    Map exposes no public remove API and ``_rules`` is a read-only computed
    view over ``_rules_by_endpoint``, so the endpoint entries are popped in
    place on that dict.
    """
    try:
        by_endpoint = app.url_map._rules_by_endpoint  # noqa: SLF001 - werkzeug 3.x
        for endpoint in _ENDPOINTS:
            by_endpoint.pop(endpoint, None)
    except (AttributeError, TypeError):  # noqa: BLE001
        pass
    for endpoint in _ENDPOINTS:
        app.view_functions.pop(endpoint, None)
    try:
        app.extensions.pop("pascal_editor_proxy", None)
    except AttributeError:
        pass


class PascalBootstrap(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict:
        module = _load_fresh_proxy_module()
        if getattr(self.app, "extensions", {}).get("pascal_editor_proxy"):
            _remove_pascal_routes(self.app)  # force refresh with current code
        installed_now = module.install_proxy_routes(self.app)
        live = bool(getattr(self.app, "extensions", {}).get("pascal_editor_proxy"))
        return {
            "ok": True,
            "registered": live,
            "installed_now": installed_now,
            "proxy_path": str(_PROXY_PATH),
            "mount": "/pascal",
        }
