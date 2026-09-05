"""Same-origin reverse proxy for the vendored Pascal editor runtime.

The editor is built with Next.js ``basePath: '/pascal'`` and only binds to
127.0.0.1. This module exposes the loopback runtime to the Agent Zero web UI
through two routes (``/pascal`` and ``/pascal/<path:rest>``) that forward
requests byte-for-byte, including long-lived streams (SSE document events,
GLB downloads) and scene save uploads.

Security model:
- every proxied request requires the same Agent Zero session that gates the
  web UI (``helpers.login.get_credentials_hash`` + session cookie);
- ``Origin``/``Referer``/session cookies are dropped and ``Host`` is set to
  the loopback upstream, exactly as if the browser talked to the editor
  directly on localhost;
- ``X-Frame-Options``/``frame-ancestors`` are neutralized so the same-origin
  iframe embed works in both docked and modal modes.
"""
from __future__ import annotations

import http.client
import json
import queue
import threading

from flask import Response, request
from flask.sessions import SecureCookieSessionInterface
from http.cookies import SimpleCookie

from helpers.print_style import PrintStyle
from usr.plugins.pascal_editor.helpers import runtime

MOUNT = "/pascal"
_UPSTREAM_HOST = "127.0.0.1"
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "content-length",
    "upgrade",
}
_DROPPED_REQUEST_HEADERS = {
    "host",
    "origin",
    "referer",
    "cookie",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
}


def is_authorized(app) -> bool:
    """Reuse the web UI login gate for proxied requests."""
    try:
        from helpers import login

        expected = login.get_credentials_hash()
    except Exception:  # noqa: BLE001
        expected = None
    if not expected:
        return True
    cookie_header = request.headers.get("Cookie", "")
    if not cookie_header:
        return False
    parsed = SimpleCookie()
    parsed.load(cookie_header)
    cookie = parsed.get(app.config.get("SESSION_COOKIE_NAME", "session"))
    if not cookie:
        return False
    try:
        serializer = SecureCookieSessionInterface().get_signing_serializer(app)
        data = serializer.loads(cookie.value)
    except Exception:  # noqa: BLE001
        return False
    return data.get("authentication") == expected


def _forward_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in request.headers:
        lowered = name.lower()
        if lowered in _HOP_BY_HOP or lowered in _DROPPED_REQUEST_HEADERS:
            continue
        headers[name] = value
    headers["Host"] = f"{_UPSTREAM_HOST}:{runtime.port()}"
    length = request.content_length or 0
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} or length:
        headers["Content-Length"] = str(length)
    return headers


def _filter_csp(value: str) -> str:
    directives = [part.strip() for part in value.split(";") if part.strip()]
    kept = [d for d in directives if not d.lower().startswith("frame-ancestors")]
    return "; ".join(kept)


def _response_headers(raw) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for name, value in raw or []:
        lowered = name.lower()
        if lowered in _HOP_BY_HOP:
            continue
        if lowered == "x-frame-options":
            continue
        if lowered == "content-security-policy":
            cleaned = _filter_csp(str(value))
            if cleaned:
                result.append((name, cleaned))
            continue
        result.append((name, str(value)))
    return result


def _worker(
    items: "queue.Queue",
    method: str,
    target: str,
    body: bytes,
    headers: dict,
    cancelled: threading.Event,
) -> None:
    conn = http.client.HTTPConnection(_UPSTREAM_HOST, runtime.port(), timeout=300)

    def send(item):
        while not cancelled.is_set():
            try:
                items.put(item, timeout=0.5)
                return
            except queue.Full:
                continue

    try:
        conn.request(method, target, body=body if body else None, headers=headers)
        resp = conn.getresponse()
        send(("meta", resp.status, _response_headers(resp.getheaders())))
        while not cancelled.is_set():
            # read(n) waits to fill n bytes: small SSE updates can be delayed
            # indefinitely. read1 returns the currently available HTTP chunk.
            chunk = resp.read1(65536)
            if not chunk:
                break
            send(chunk)
    except Exception as exc:
        send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()
        send(None)


def _handle_proxy_request(app):
    if not is_authorized(app):
        return Response("Authentication required", status=401, mimetype="text/plain")

    health = runtime.health(timeout=2.0)
    if not health.get("up"):
        status = runtime.start_runtime()
        if status.get("state") == "running":
            health = runtime.health(timeout=2.0)
        if not health.get("up"):
            payload = {
                "error": "Pascal Editor runtime is starting, retry shortly.",
                "state": status.get("state"),
                "retry": True,
            }
            return Response(
                json.dumps(payload), status=503, mimetype="application/json"
            )

    method = request.method
    body = (
        request.get_data(cache=True)
        if method in {"POST", "PUT", "PATCH", "DELETE"}
        else b""
    )
    query = request.query_string.decode("latin-1")
    path = request.path
    if path == MOUNT + "/":
        # The Next.js index is served without a trailing slash; the
        # trailing-slash form would only earn a needless 308 hop.
        path = MOUNT
    target = path + (f"?{query}" if query else "")
    headers = _forward_headers()

    items: "queue.Queue" = queue.Queue(maxsize=64)
    cancelled = threading.Event()
    thread = threading.Thread(
        target=_worker,
        args=(items, method, target, body, headers, cancelled),
        name="pascal-editor-proxy",
        daemon=True,
    )
    thread.start()

    try:
        first = items.get(timeout=120)
    except queue.Empty:
        cancelled.set()
        return Response(
            json.dumps({"error": "Pascal Editor runtime did not answer in time."}),
            status=504,
            mimetype="application/json",
        )
    if not isinstance(first, tuple):
        cancelled.set()
        return Response(
            json.dumps({"error": "Unexpected upstream response shape."}),
            status=502,
            mimetype="application/json",
        )
    if first[0] == "error":
        cancelled.set()
        return Response(
            json.dumps({"error": first[1]}), status=502, mimetype="application/json"
        )
    _, status_code, headers = first

    def stream():
        try:
            while True:
                try:
                    item = items.get(timeout=60)
                except queue.Empty:
                    yield b""
                    continue
                if item is None or isinstance(item, tuple):
                    break
                yield item
        finally:
            # Stop producing when a browser disconnects instead of leaving a
            # worker blocked on a full queue. SSE heartbeats wake read1 too.
            cancelled.set()

    response = Response(stream(), status=status_code, direct_passthrough=True)
    response.call_on_close(cancelled.set)
    for name, value in headers:
        response.headers[name] = value
    return response


def make_proxy_view(app):
    """Build a request-context-safe view func that forwards to upstream.

    Flask invokes the returned callable with the path-conversion kwargs of
    the matched rule (``rest`` for ``/pascal/<path:rest>``); they are ignored
    here because the full request path is forwarded to upstream as-is.  All
    ``flask.request`` access happens inside the call (i.e. within a request
    context), never at registration time.
    """
    def proxy_view(_rest=None, **_kwargs):
        return _handle_proxy_request(app)

    proxy_view.__name__ = "pascal_editor_proxy_view"
    proxy_view.__doc__ = "Same-origin reverse proxy to the Pascal editor runtime."
    return proxy_view


def install_proxy_routes(app) -> bool:
    """Register the proxy routes on the Flask app (idempotent).

    Uses ``add_url_rule`` on a virgin app (clean boot).  On an app that has
    already handled its first request Flask refuses ``add_url_rule``; in
    that case the Rule objects and view are injected directly into
    ``url_map`` / ``view_functions``, which are read at dispatch time, so
    both a boot hook and a mid-session bootstrap can install the routes.

    Returns True when the routes were (re)installed, False when present.
    """
    try:
        if app.extensions.get("pascal_editor_proxy"):
            return False
    except AttributeError:  # pragma: no cover - very old Flask
        pass
    view = make_proxy_view(app)
    try:
        app.add_url_rule(
            MOUNT,
            endpoint="pascal_editor_proxy_root",
            view_func=view,
            methods=list(_METHODS),
            strict_slashes=False,
        )
        app.add_url_rule(
            MOUNT + "/<path:rest>",
            endpoint="pascal_editor_proxy",
            view_func=view,
            methods=list(_METHODS),
        )
    except AssertionError:
        # App already served requests: add_url_rule is refused, but the
        # url_map and view_functions are plain read-at-dispatch structures.
        from werkzeug.routing import Rule

        for rule_str, endpoint in (
            (MOUNT, "pascal_editor_proxy_root"),
            (MOUNT + "/<path:rest>", "pascal_editor_proxy"),
        ):
            # The root rule accepts /pascal/ as well (Next.js index has no
            # trailing slash; the view normalizes the target).
            strict = rule_str != MOUNT
            app.url_map.add(
                Rule(
                    rule_str,
                    endpoint=endpoint,
                    methods=list(_METHODS),
                    strict_slashes=strict,
                )
            )
            app.view_functions[endpoint] = view
    app.extensions["pascal_editor_proxy"] = True
    return True


def install_boot_hook(runtime_cls) -> None:
    """Wrap ``register_http_routes`` so future boots get the proxy too.

    Mirrors the composition-safe monkeypatch pattern used by the core
    ``_browser`` plugin: the original method always runs first and the
    wrapper is only installed once.
    """
    if getattr(runtime_cls, "_pascal_proxy_boot_hook_installed", False):
        return
    original = runtime_cls.register_http_routes

    def register_http_routes(self):
        original(self)
        try:
            install_proxy_routes(self.webapp)
        except Exception as exc:  # noqa: BLE001
            PrintStyle.warning("Pascal Editor proxy route install failed:", exc)

    runtime_cls.register_http_routes = register_http_routes
    runtime_cls._pascal_proxy_boot_hook_installed = True
