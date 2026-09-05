"""Lifecycle manager for the vendored Pascal editor runtime.

Spawns the Next.js standalone server as a detached loopback child process and
exposes start/stop/status/health helpers used by the API handlers and the
startup migration hook.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path

PLUGIN_NAME = "pascal_editor"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PLUGIN_DIR / "runtime"
RUNTIME_ENTRY = RUNTIME_DIR / "apps" / "editor" / "server.js"
STATE_DIR = RUNTIME_DIR / ".state"
DATA_DIR = RUNTIME_DIR / ".data"
PID_FILE = STATE_DIR / "editor.pid"
LOG_FILE = STATE_DIR / "editor.log"
INSTANCE_FILE = STATE_DIR / "instance_id.txt"
DEFAULT_PORT = 3101
RUNTIME_VERSION = "1.0.0-beta.1"

_LOCK = threading.Lock()


def _plugin_config() -> dict:
    try:
        from helpers.plugins import get_plugin_config
        cfg = get_plugin_config(PLUGIN_NAME) or {}
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    return cfg


def get_config() -> dict:
    """Public alias for :func:`_plugin_config` (used by execute.py)."""
    return _plugin_config()


def ensure_directories() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INSTANCE_FILE.exists():
        INSTANCE_FILE.write_text(uuid.uuid4().hex)


def port() -> int:
    try:
        return int(_plugin_config().get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        return DEFAULT_PORT


def host() -> str:
    return "127.0.0.1"


def upstream_base() -> str:
    return f"http://{host()}:{port()}"


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def health(timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(
            upstream_base() + "/pascal/api/health", timeout=timeout
        ) as r:
            body = r.read().decode("utf-8", "replace")
            try:
                data = json.loads(body) if body.strip().startswith("{") else {"ok": True}
            except json.JSONDecodeError:
                data = {"ok": True}
            data["http"] = r.status
            data["up"] = r.status == 200
        return data
    except Exception as exc:  # noqa: BLE001 - report any failure as down
        return {"up": False, "error": str(exc)}


def is_running() -> bool:
    if _alive(_read_pid()):
        return True
    h = health(timeout=1.0)
    return bool(h.get("up"))


def _env() -> dict:
    env = dict(os.environ)
    env.update(
        {
            "NODE_ENV": "production",
            "HOSTNAME": host(),
            "PORT": str(port()),
            "PASCAL_DATA_DIR": str(DATA_DIR),
            "PASCAL_DB_PATH": str(DATA_DIR / "pascal.db"),
            "PASCAL_EDITOR_ORIGIN": "/pascal",
            "PASCAL_INSTANCE_ID": INSTANCE_FILE.read_text().strip(),
            "PASCAL_RUNTIME_VERSION": RUNTIME_VERSION,
            "PASCAL_NO_OPEN": "1",
        }
    )
    return env


def stop_runtime(cfg: dict | None = None) -> dict:
    ensure_directories()
    pid = _read_pid()
    message = "not managed"
    if pid and _alive(pid):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(pid), sig)
            except (ProcessLookupError, PermissionError):
                try:
                    os.kill(pid, sig)
                except OSError:
                    break
            for _ in range(20):
                if not _alive(pid):
                    break
                time.sleep(0.25)
            if not _alive(pid):
                break
        message = f"stopped pid {pid}"
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return {"state": "stopped", "message": message}


def _spawn() -> int:
    node = shutil.which("node") or "node"
    with open(LOG_FILE, "ab") as log:
        proc = subprocess.Popen(
            [node, str(RUNTIME_ENTRY)],
            cwd=str(RUNTIME_DIR),
            env=_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    PID_FILE.write_text(str(proc.pid))
    return proc.pid


def _wait_ready(timeout: float) -> dict:
    deadline = time.time() + timeout
    last = {"up": False}
    while time.time() < deadline:
        last = health(timeout=2.0)
        if last.get("up"):
            return {"state": "running", "pid": _read_pid(), "port": port(), **last}
        time.sleep(0.5)
    return {"state": "timeout", "port": port(), **last}


def start_runtime(cfg: dict | None = None) -> dict:
    ensure_directories()
    if not RUNTIME_ENTRY.exists():
        return {
            "state": "error",
            "error": "runtime missing. Run the Pascal Editor install action once to vendor the editor runtime.",
        }
    with _LOCK:
        if is_running():
            return {"state": "running", "pid": _read_pid(), "port": port(), "version": RUNTIME_VERSION}
        pid = _spawn()
    return {"state": "starting", "pid": pid, "port": port()}


def ensure_running(cfg: dict | None = None) -> dict:
    cfg = cfg or _plugin_config()
    if cfg.get("enabled") is False:
        return {"state": "disabled"}
    res = start_runtime(cfg)
    if res.get("state") == "running":
        res.setdefault("version", RUNTIME_VERSION)
        return res
    if res.get("state") == "starting":
        wait = float(cfg.get("start_timeout_seconds", 90))
        return _wait_ready(wait)
    return res


def get_status(cfg: dict | None = None) -> dict:
    cfg = cfg or _plugin_config()
    status = {
        "state": "stopped",
        "running": is_running(),
        "pid": _read_pid(),
        "port": port(),
        "url": "/pascal/",
        "version": RUNTIME_VERSION,
        "runtime_present": RUNTIME_ENTRY.exists(),
        "node": shutil.which("node"),
    }
    if status["running"]:
        status["state"] = "running"
        h = health(timeout=float(cfg.get("health_timeout_seconds", 3)))
        status["health"] = h
        status["ready"] = bool(h.get("up"))
    if cfg.get("enabled") is False and not status["running"]:
        status["state"] = "disabled"
    return status