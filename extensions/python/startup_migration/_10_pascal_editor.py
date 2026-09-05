"""Boot-time wiring for the Pascal Editor plugin.

Preheats plugin-owned state directories and installs the same-origin
``/pascal`` proxy route for this and all future boots (idempotent
composition-safe wrapper, same pattern as the core ``_browser`` plugin).
The editor process itself stays lazy: it is only spawned when the surface is
first opened or an ``ensure`` action runs.
"""
from __future__ import annotations

from helpers.extension import Extension


class PascalEditorBootExtension(Extension):
    def execute(self, **kwargs):
        from helpers.ui_server import UiServerRuntime

        from usr.plugins.pascal_editor.helpers import proxy, runtime

        runtime.ensure_directories()
        proxy.install_boot_hook(UiServerRuntime)
        # Persist before the framework initializes its MCP clients later in boot.
        # No package downloads, global installs, or editor startup at boot.
        from usr.plugins.pascal_editor.helpers import mcp
        from helpers.print_style import PrintStyle

        try:
            mcp.install(activate=False)
        except Exception as exc:
            PrintStyle.warning(f"Pascal MCP setup failed: {exc}")
