from __future__ import annotations


def install() -> None:
    """Called automatically by Agent Zero after install and update."""
    from usr.plugins.pascal_editor.helpers import mcp

    mcp.install()


def pre_update() -> None:
    from usr.plugins.pascal_editor.helpers.runtime import stop_runtime

    stop_runtime()


def uninstall() -> None:
    """Remove only our MCP registration before Agent Zero deletes the plugin."""
    from usr.plugins.pascal_editor.helpers import mcp, runtime

    mcp.register(remove=True)
    runtime.stop_runtime()
