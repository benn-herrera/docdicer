"""The kanban server: the board of one project served to a browser on 127.0.0.1, kept live by
polling the files it reads, with the moves between Roadmap and Design. It keeps no UI state.

Endpoints, each answering JSON but the page's files:

- `GET /` and `GET /<file>`: the page's files, from the package's `assets/` directory.
- `GET /api/board?since=<version>`: the board payload; where `since` is the version the server
  holds, the answer waits until the board changes or `LONG_POLL_SECONDS` pass.
- `POST /api/to-design` `{"card": <a roadmap or parked card as served>}`: move the card's entry into
  the active design.
- `POST /api/to-roadmap` `{"card": <a design card as served>, "target": <the roadmap or parked card
  dropped on, as served, or null>}`: move the card's section out of the design into `ROADMAP.md`.

  Both answer the board payload with `written`, the files written relative to the project root in
  the order written; 409 with `{"error": ...}` where refused, writing nothing; 500 with `{"error":
  "cannot write: <file>", "written": [...]}` where a write fails, and with `{"error": "cannot read:
  <file>"}` where a file the move reads cannot be read.
"""

import json
import os
import sys
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any, Callable, Optional, TextIO
from urllib.parse import parse_qs, urlsplit

from ..dicerlib.textfile import read_text
from .board import (
    PLAN_COLUMNS,
    MoveRefused,
    MoveWriteFailed,
    move_to_design,
    move_to_roadmap,
    read_board,
    root_relative,
    sha256,
    watched_files,
)
from .planform import find_project_root

HOST = "127.0.0.1"
POLL_SECONDS = 0.25
LONG_POLL_SECONDS = 25.0
_CONTENT_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
_PAGE_POLICY = "default-src 'self'; frame-ancestors 'none'"
_UNREADABLE = "unreadable"


def _snapshot(root: str) -> dict[str, Optional[str]]:
    """Each watched file's content digest; None where it is not a file, `_UNREADABLE` where it is
    one that cannot be read."""
    snapshot: dict[str, Optional[str]] = {}
    for path in watched_files(root):
        if not os.path.isfile(path):
            snapshot[path] = None
            continue
        try:
            snapshot[path] = sha256(read_text(path))
        except OSError:
            snapshot[path] = _UNREADABLE
    return snapshot


class BadRequest(Exception):
    """A request the server cannot act on; the message says why."""


class CannotListen(Exception):
    """The server's port could not be bound; the message is the reason."""


def _unreadable(e: OSError, reading: str) -> str:
    """The file an OSError names, else reading, the path being read."""
    return e.filename if e.filename is not None else reading


class KanbanServer(ThreadingHTTPServer):
    """The board of the project at root, served on HOST at an ephemeral port. Reads the board on
    construction, raising OSError where a file it reads cannot be read and CannotListen where the
    port cannot be bound, then polls the files every POLL_SECONDS until server_close."""

    daemon_threads = True

    def __init__(self, root: str, *, stderr: TextIO) -> None:
        self.root = root
        self._stderr = stderr
        self._lock = threading.Condition()
        self._stop = threading.Event()
        self._poller = threading.Thread(target=self._poll, name="kanban-poll", daemon=True)
        self._snapshot = _snapshot(root)
        self._board = read_board(root)
        self._version = 1
        self._reported: Optional[str] = None  # the unreadable file last named on stderr
        try:
            super().__init__((HOST, 0), _Handler)
        except OSError as e:
            raise CannotListen(e.strerror or str(e)) from e
        self._poller.start()

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.server_address[1]}/"

    def server_close(self) -> None:
        self._stop.set()
        if self._poller.is_alive():
            self._poller.join()
        with self._lock:
            self._lock.notify_all()
        super().server_close()

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A client gone mid-request (a page reloaded during a long poll) is not an error; anything
        else gets the default traceback."""
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)

    def payload(self, since: Optional[str]) -> dict[str, Any]:
        """The board payload, once its version differs from since; at most LONG_POLL_SECONDS late."""
        with self._lock:
            if since is not None:
                self._lock.wait_for(lambda: str(self._version) != since or self._stop.is_set(), LONG_POLL_SECONDS)
            return self._payload()

    def to_design(self, body: dict[str, Any]) -> dict[str, Any]:
        card = _field(body, "card", dict)
        with self._lock:
            return self._moved(lambda: move_to_design(self.root, card, read=self._board.sha256))

    def to_roadmap(self, body: dict[str, Any]) -> dict[str, Any]:
        card = _field(body, "card", dict)
        target = body.get("target")
        if target is not None and not isinstance(target, dict):
            raise BadRequest("target must be a dict or null")
        with self._lock:
            return self._moved(lambda: move_to_roadmap(self.root, card, target=target, read=self._board.sha256))

    def _moved(self, move: Callable[[], list[str]]) -> dict[str, Any]:
        """Make move, then read the board again; the payload with the files written. A write that
        fails still reads the board again, as the files written have changed. A read that fails
        in either case is named on stderr and leaves the move's result as it is."""
        try:
            written = move()
        except MoveWriteFailed:
            self._refresh_or_report()
            raise
        self._refresh_or_report()
        return {**self._payload(), "written": written}

    def _payload(self) -> dict[str, Any]:
        return {
            "version": self._version,
            "board": asdict(self._board),
            "plan_columns": list(PLAN_COLUMNS),
            "project": os.path.basename(self.root),
        }

    def _poll(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            with self._lock:
                self._refresh_or_report()

    def _refresh_or_report(self) -> None:
        try:
            self._refresh()
        except OSError as e:
            self._report(_unreadable(e, self.root))

    def _refresh(self) -> None:
        """Read the board again where a watched file changed. Raises OSError where a file cannot
        be read, keeping the last good board and the last snapshot, so the next refresh reads again."""
        snapshot = _snapshot(self.root)
        if snapshot == self._snapshot:
            return
        self._board = read_board(self.root)
        self._snapshot = snapshot
        self._reported = None
        self._version += 1
        self._lock.notify_all()

    def _report(self, path: str) -> None:
        if path != self._reported:
            print(f"cannot read: {path}", file=self._stderr, flush=True)
            self._reported = path


def _field(body: dict[str, Any], name: str, kind: type) -> Any:
    value = body.get(name)
    if not isinstance(value, kind):
        raise BadRequest(f"{name} must be a {kind.__name__}")
    return value


def _asset(name: str) -> Optional[tuple[bytes, str]]:
    """The page file name, as served, and its content type; None where the page has no such file."""
    content_type = _CONTENT_TYPES.get(os.path.splitext(name)[1])
    if content_type is None:
        return None
    for entry in (files(__package__) / "assets").iterdir():
        if entry.name == name and entry.is_file():
            return entry.read_text(encoding="utf-8").encode("utf-8"), f"{content_type}; charset=utf-8"
    return None


class _Handler(BaseHTTPRequestHandler):
    server: KanbanServer

    _ACTIONS = {
        "/api/to-design": KanbanServer.to_design,
        "/api/to-roadmap": KanbanServer.to_roadmap,
    }

    def log_message(self, format: str, *args: Any) -> None:
        """Nothing is written per request."""

    def do_GET(self) -> None:
        if not self._local_host():
            return
        url = urlsplit(self.path)
        if url.path == "/api/board":
            since = parse_qs(url.query).get("since")
            self._send_json(200, self.server.payload(since[0] if since else None))
            return
        asset = _asset("index.html" if url.path == "/" else url.path[1:])
        if asset is None:
            self._send_json(404, {"error": f"no such file: {url.path}"}, page=True)
            return
        self._send(200, *asset, page=True)

    def do_POST(self) -> None:
        if not self._local_host():
            return
        action = self._ACTIONS.get(urlsplit(self.path).path)
        if action is None:
            self._send_json(404, {"error": f"no such endpoint: {self.path}"})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "the body must be application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0:
                raise BadRequest("Content-Length must not be negative")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise BadRequest("the body must be a JSON object")
            self._send_json(200, action(self.server, body))
        except (ValueError, BadRequest) as e:
            self._send_json(400, {"error": str(e)})
        except MoveRefused as e:
            self._send_json(409, {"error": str(e)})
        except MoveWriteFailed as e:
            self._send_json(500, {"error": str(e), "written": e.written})
        except OSError as e:
            root = self.server.root
            self._send_json(500, {"error": f"cannot read: {root_relative(root, _unreadable(e, root))}"})

    def _local_host(self) -> bool:
        """Refuse a request naming another host, as a page served elsewhere would (DNS rebinding)."""
        port = self.server.server_address[1]
        if self.headers.get("Host") in (f"{HOST}:{port}", f"localhost:{port}"):
            return True
        self._send_json(403, {"error": "requests must name the host the board is served on"})
        return False

    def _send_json(self, status: int, payload: dict[str, Any], *, page: bool = False) -> None:
        self._send(status, json.dumps(payload).encode("ascii"), "application/json", page=page)

    def _send(self, status: int, body: bytes, content_type: str, *, page: bool = False) -> None:
        """Send one response; page marks an answer to a request for the page's files."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if page:
            self.send_header("Content-Security-Policy", _PAGE_POLICY)
        self.end_headers()
        self.wfile.write(body)


def run_kanban(project_dir: Optional[str], *, start: str, stdout: TextIO, stderr: TextIO) -> int:
    """Serve the board of the project project_dir is in, or with None the project the directory
    start is in, until interrupted; 0 then, 2 where there is no project root, a file the board reads
    cannot be read at start or the port cannot be bound. A relative project_dir is taken from start."""
    directory = os.path.abspath(start if project_dir is None else os.path.join(start, project_dir))
    root = find_project_root(directory)
    if root is None:
        print(
            f"no project root: neither {directory} nor any directory above it holds .git;"
            " run docdicer kanban inside a project, or name a directory inside a project: docdicer kanban <project-dir>",
            file=stderr,
        )
        return 2
    try:
        server = KanbanServer(root, stderr=stderr)
    except OSError as e:
        print(f"cannot read: {_unreadable(e, root)}", file=stderr)
        return 2
    except CannotListen as e:
        print(f"cannot listen: {e}", file=stderr)
        return 2
    print(server.url, file=stdout, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
