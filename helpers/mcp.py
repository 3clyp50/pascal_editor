"""Install and register the plugin-owned Pascal stdio MCP, without global installs."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import threading
from copy import deepcopy
from pathlib import Path

from usr.plugins.pascal_editor.helpers import runtime

NAME = "pascal_editor"
MCP_DIR = runtime.PLUGIN_DIR / "mcp"
ENTRY = MCP_DIR / "launch.mjs"
_LOCK = threading.RLock()


def prepare() -> None:
    """The distributable includes the bundle; installation never runs npm scripts."""
    runtime.ensure_directories()
    node = runtime.node_executable()
    if not node:
        raise RuntimeError("Pascal MCP requires Node.js >=22.13 (not installed).")
    version = subprocess.run([node, "-p", "process.versions.node"], check=True,
                             capture_output=True, text=True, timeout=10).stdout.strip()
    parts = tuple(int(part) for part in version.split(".")[:2])
    if parts < (22, 13):
        raise RuntimeError(f"Pascal MCP requires Node.js >=22.13; found {version}.")
    for relative in ("launch.mjs", "dist/server.mjs", "dist/server.mjs.LEGAL.txt",
                     "dist/THIRD_PARTY_NOTICES.txt", "dist/dependencies.json", "PASCAL_LICENSE.txt"):
        if not (MCP_DIR / relative).is_file():
            raise RuntimeError(f"Pascal MCP distribution is incomplete: mcp/{relative}")
    subprocess.run([node, "--check", str(MCP_DIR / "dist/server.mjs")],
                   check=True, capture_output=True, timeout=15)


def server_config() -> dict:
    return {
        "type": "stdio", "command": runtime.node_executable() or "node",
        "args": [str(ENTRY)], "init_timeout": 30, "tool_timeout": 120,
        "description": "Pascal Editor — local saved-scene editing. Supply sceneId on every scene tool call.",
    }


def _owned(entry: dict) -> bool:
    # A name alone is not ownership: never overwrite/remove an unrelated server.
    return isinstance(entry, dict) and entry.get("args") == [str(ENTRY)] and (
        Path(str(entry.get("command", ""))).name in {"node", "nodejs"}
    )


def merge_registration(raw: str, remove: bool = False) -> tuple[str, bool]:
    """Preserve supported JSON shapes, unrelated entries, and user tool toggles.

    Refuse malformed JSON rather than interpreting it as an empty config. The
    MCP settings UI can normalize commented/relaxed JSON before installation.
    """
    document = json.loads(raw or '{"mcpServers": {}}')
    before = deepcopy(document)
    if isinstance(document, dict) and "mcpServers" in document:
        servers = document["mcpServers"]
    elif isinstance(document, list):
        servers = document
    elif isinstance(document, dict) and "name" in document:
        document = [document]
        servers = document
    elif document == {}:
        document = {"mcpServers": {}}
        servers = document["mcpServers"]
    else:
        raise ValueError("Unsupported MCP configuration; existing settings were not changed.")
    if isinstance(servers, dict):
        candidates = [(key, value) for key, value in servers.items()
                      if re.sub(r"[^\w]", "_", str(key).strip().lower()) == NAME]
    elif isinstance(servers, list) and all(isinstance(item, dict) for item in servers):
        candidates = [(index, item) for index, item in enumerate(servers)
                      if re.sub(r"[^\w]", "_", str(item.get("name", "")).strip().lower()) == NAME]
    else:
        raise ValueError("Invalid mcpServers collection; existing settings were not changed.")
    if len(candidates) > 1:
        raise ValueError("Duplicate Pascal MCP names; resolve them in MCP settings first.")
    if candidates:
        key, current = candidates[0]
        if not _owned(current):
            if remove:
                return raw, False
            raise ValueError("An unrelated MCP server already uses the name pascal_editor; it was not changed.")
        if remove:
            if isinstance(servers, list):
                servers.pop(key)
            else:
                del servers[key]
        else:
            updated = {**server_config(), **current}
            # Refresh only the plugin-owned launch path; preserve user timeouts,
            # disabled state, disabled_tools, and other per-server preferences.
            updated.update(command=server_config()["command"], args=[str(ENTRY)])
            servers[key] = updated
    elif not remove:
        if isinstance(servers, dict):
            servers[NAME] = server_config()
        else:
            servers.append({"name": NAME, **server_config()})
    changed = document != before
    return (json.dumps(document, indent=2) if changed else raw), changed


def _refresh_live(raw: str) -> None:
    """Refresh only Pascal, not every other MCP connection or model setting."""
    from helpers.mcp_handler import MCPConfig, MCPServerLocal, normalize_name

    config = MCPConfig.get_instance()
    desired = next((item for item in MCPConfig.parse_config_string(raw)
                    if normalize_name(item.get("name", "")) == NAME), None)
    current = next((item for item in config.servers if item.name == NAME), None)
    if desired and not _owned(desired):
        return
    if desired and not desired.get("disabled", False):
        if current and not _owned(current.model_dump()):
            raise ValueError("An unrelated live MCP server uses the Pascal name; it was not changed.")
        # Refresh the tool catalog on install/update too: a new bundle can
        # change schemas without changing the command or launch path.
        server = MCPServerLocal(desired)
        # Hook/API callers may already have an event loop. MCP initialization
        # must run on a separate thread, never asyncio.run() inside that loop.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(lambda: asyncio.run(server.initialize())).result(timeout=45)
        if server.get_error():
            raise RuntimeError(f"Pascal MCP initialization failed: {server.get_error()}")
        config.servers = [item for item in config.servers if item.name != NAME] + [server]
    else:
        config.servers = [item for item in config.servers if not (item.name == NAME and _owned(item.model_dump()))]
    config.disconnected_servers = [item for item in config.disconnected_servers if item.get("name") != NAME]
    if desired and desired.get("disabled", False):
        config.disconnected_servers.append({"name": NAME, "config": desired, "error": "Disabled in config"})
    MCPConfig.clear_project_instances()


def register(*, remove: bool = False, activate: bool = True) -> dict:
    from helpers import settings

    with _LOCK:
        raw = settings.get_settings().get("mcp_servers", '{"mcpServers": {}}')
        merged, changed = merge_registration(raw, remove=remove)
        if changed:
            # Keep all other settings and services untouched.
            settings.set_settings_delta({"mcp_servers": merged}, apply=False)
        if activate:
            try:
                _refresh_live(merged)
            except Exception:
                # The installer deletes a new plugin when its hook fails. Do not
                # leave a dangling MCP command behind after that rollback.
                if changed and settings.get_settings().get("mcp_servers") == merged:
                    settings.set_settings_delta({"mcp_servers": raw}, apply=False)
                raise
    return {"server": NAME, "registered": not remove, "changed": changed}


def install(*, activate: bool = True) -> dict:
    from helpers import plugins

    cfg = runtime.get_config()
    disabled = plugins.get_toggle_state(NAME) == "disabled" or cfg.get("enabled") is False or cfg.get("mcp_enabled") is False
    if not disabled:
        prepare()
    return register(remove=disabled, activate=activate)
