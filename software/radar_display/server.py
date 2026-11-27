"""Local web server for the display. Listens on 127.0.0.1 only.

The only things a request can change are processing and simulation settings.
There is no transmitter control of any kind.
"""

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import Engine

HOST = "127.0.0.1"
MAX_BODY_BYTES = 4096
WEB_DIR = Path(__file__).parent / "web"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def apply_control(engine: Engine, command: dict) -> None:
    """Apply a settings change from the page, or raise ValueError."""
    if not isinstance(command, dict) or not command:
        raise ValueError("expected a JSON object")
    unknown = set(command) - {"window", "simulation", "drop_frames"}
    if unknown:
        raise ValueError(f"unknown command: {sorted(unknown)}")
    simulation = command.get("simulation")
    drop = command.get("drop_frames")
    if (simulation is not None or drop is not None) and not engine.source.is_simulated:
        raise ValueError("simulation controls need the simulated source")
    if simulation is not None and not isinstance(simulation, dict):
        raise ValueError("simulation must be an object")
    if drop is not None and (type(drop) is not int or not 1 <= drop <= 100):
        raise ValueError("drop_frames must be a whole number from 1 to 100")
    if "window" in command:
        engine.set_window(command["window"])
    if simulation is not None:
        engine.source.update(simulation)
    if drop is not None:
        engine.source.drop_frames(drop)


def make_handler(engine: Engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # the stream would flood the console
            pass

        def _host_ok(self) -> bool:
            # Refuses other host names, which blocks DNS-rebinding pages.
            port = self.server.server_address[1]
            return self.headers.get("Host") in (f"{HOST}:{port}", f"localhost:{port}")

        def _send(self, status, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status, payload) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json")

        def do_GET(self):
            if not self._host_ok():
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
            elif self.path in STATIC:
                name, content_type = STATIC[self.path]
                self._send(HTTPStatus.OK, (WEB_DIR / name).read_bytes(), content_type)
            elif self.path == "/api/state":
                _, snapshot, error = engine.wait_for_update(0, 2.0)
                self._send_json(HTTPStatus.OK, {"frame": snapshot, "error": error})
            elif self.path == "/api/stream":
                self._stream()
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def _stream(self):
            """Server-sent events: one message per processed frame."""
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            version = 0
            try:
                while not engine.stopping:
                    new_version, snapshot, error = engine.wait_for_update(version, 1.0)
                    if new_version == version:
                        self.wfile.write(b": waiting\n\n")
                    else:
                        version = new_version
                        payload = json.dumps(
                            {"frame": snapshot, "error": error}, allow_nan=False
                        )
                        self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
            except OSError:
                pass  # the browser tab closed

        def _read_body(self) -> bytes | None:
            """The request body, or None if its stated size is not acceptable.

            It is read even for requests that get refused: closing a socket
            with unread data resets the connection on Windows, and the client
            then never sees the error reply.
            """
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            return self.rfile.read(length) if 0 < length <= MAX_BODY_BYTES else None

        def do_POST(self):
            body = self._read_body()
            if not self._host_ok():
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                return
            if self.path != "/api/control":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            # Requiring JSON makes other web sites pre-flight, which we refuse.
            content_type = self.headers.get("Content-Type", "").split(";")[0]
            if content_type.strip() != "application/json":
                self._send_json(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send JSON"}
                )
                return
            try:
                if body is None:
                    raise ValueError("bad body size")
                apply_control(engine, json.loads(body))
            except (ValueError, TypeError) as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._send_json(HTTPStatus.OK, {"ok": True})

    return Handler


class DisplayServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, address reuse would let two copies share one port silently.
    allow_reuse_address = False


def make_server(engine: Engine, port: int) -> DisplayServer:
    return DisplayServer((HOST, port), make_handler(engine))
