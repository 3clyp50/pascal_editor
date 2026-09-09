"""Automatic dependency setup, initialization, and cleanup for Agent Zero."""
from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from usr.plugins.pascal_editor.helpers import runtime

NODE_VERSION = "22.22.0"
NODE_ARCHIVE = f"node-v{NODE_VERSION}-linux-x64"
NODE_SHA256 = "9aa8e9d2298ab68c600bd6fb86a6c13bce11a4eca1ba9b39d79fa021755d7c37"


def install_dependencies() -> None:
    """Reuse compatible Node, otherwise install a verified plugin-local copy."""
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("This Pascal Editor runtime requires Linux x64.")
    node = runtime.node_executable()
    if node:
        version = subprocess.run(
            [node, "-p", "process.versions.node"], check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if tuple(int(part) for part in version.split(".")[:2]) >= (22, 13):
            return
    runtime.DEPS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=runtime.DEPS_DIR) as directory:
        archive = Path(directory) / "node.tar.xz"
        url = f"https://nodejs.org/dist/v{NODE_VERSION}/{NODE_ARCHIVE}.tar.xz"
        with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        with archive.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != NODE_SHA256:
                raise RuntimeError("Pascal Editor Node.js download checksum mismatch.")
        with tarfile.open(archive) as bundle:
            bundle.extractall(directory, filter="data")
        if runtime.NODE_DIR.exists():
            shutil.rmtree(runtime.NODE_DIR)
        (Path(directory) / NODE_ARCHIVE).rename(runtime.NODE_DIR)


def install(*, activate: bool = True) -> None:
    """Install/update and boot share the same automatic initialization."""
    from helpers import plugins
    from helpers.ui_server import UiServerRuntime
    from usr.plugins.pascal_editor.helpers import mcp, proxy

    proxy.install_boot_hook(UiServerRuntime)
    if plugins.get_toggle_state(runtime.PLUGIN_NAME) == "disabled" or runtime.get_config().get("enabled") is False:
        mcp.register(remove=True, activate=activate)
        runtime.stop_runtime()
        return
    install_dependencies()
    was_running = runtime.is_running()
    try:
        result = runtime.ensure_running()
        if result.get("state") != "running":
            raise RuntimeError(f"Pascal Editor initialization failed: {result}")
        mcp.install(activate=activate)
    except Exception:
        if not was_running:
            runtime.stop_runtime()
        raise


def pre_update() -> None:
    runtime.stop_runtime()


def uninstall() -> None:
    """Release MCP and editor before removing only plugin-owned dependencies."""
    from usr.plugins.pascal_editor.helpers import mcp

    mcp.register(remove=True)
    runtime.stop_runtime()
    if runtime.DEPS_DIR.exists():
        shutil.rmtree(runtime.DEPS_DIR)
