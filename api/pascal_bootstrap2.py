"""In-session refresh endpoint for the Pascal Editor proxy routes (second generation).

Agent Zero imports each API handler the first time its path is requested and
keeps that module instance for the life of the web UI process.  If plugin
code changes on disk (as it did while the initial proxy was being stabilized)
the *cached* handler keeps running the old code and its idempotency flag
prevents the new code from installing.

This handler is therefore always imported fresh after :mod:`pascal_bootstrap`
and re-executes the *current on-disk* source of :mod:`pascal_bootstrap`
(which itself re-executes the current :mod:`helpers/proxy.py`) to perform a
hard refresh: every previously registered Pascal rule/view is removed and the
routes are re-installed from the latest on-disk code.

The endpoint is idempotent, session-authenticated, and safe to call repeatedly.
"""
from __future__ import annotations

import types
from pathlib import Path

from helpers.api import ApiHandler, Request

_BOOTSTRAP_PATH = Path(__file__).resolve().parent / "pascal_bootstrap.py"
_IMPL_MODULE = "pascal_editor_bootstrap_impl"


def _load_bootstrap_impl():
    """Execute the current on-disk bootstrap helper into a fresh namespace.

    The file defines :func:`_load_fresh_proxy_module` (which re-executes the
    on-disk ``helpers/proxy.py``) and :func:`_remove_pascal_routes`.
    Re-executing it here guarantees the *latest* removal/install logic runs
    even inside an otherwise stale process.
    """
    source = _BOOTSTRAP_PATH.read_text()
    module = types.ModuleType(_IMPL_MODULE)
    module.__file__ = str(_BOOTSTRAP_PATH)
    module.__package__ = ""
    exec(compile(source, str(_BOOTSTRAP_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


class PascalBootstrapRefresh(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict:
        impl = _load_bootstrap_impl()
        proxy_module = impl._load_fresh_proxy_module()
        # Hard refresh: drop anything previously installed (no-op on a
        # clean boot), then install the current on-disk version.
        impl._remove_pascal_routes(self.app)
        installed_now = proxy_module.install_proxy_routes(self.app)
        rules = sorted(
            r.rule for r in self.app.url_map.iter_rules() if "pascal" in r.rule
        )
        live = bool(getattr(self.app, "extensions", {}).get("pascal_editor_proxy"))
        return {
            "ok": True,
            "registered": live,
            "installed_now": installed_now,
            "rules": rules,
            "mount": "/pascal",
        }
