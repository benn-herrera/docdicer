"""Unit tests for the kanban server: the page's files, the board payload over the board model, live
following of the watched files, and the moves between Roadmap and Design."""

import errno
import http.client
import io
import json
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from email.message import Message
from importlib.resources import files
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

import pytest

import docdicer
from docdicer.kanban import board as board_module
from docdicer.kanban import planform
from docdicer.kanban import server as server_module
from docdicer.kanban.board import read_board
from docdicer.kanban.server import KanbanServer, run_kanban

_PLAN = (
    "# Plan\n\nRelease: 9.9.9\n\n## Status\n\n| Package | Rating | State |\n|---|---|---|\n"
    "| P1 | expert | |\n| P2 | expert | dispatchable |\n| P3 | mechanical | landed |\n"
)
_ROADMAP = "## Next\n\n### Search index\n\nBuild an index.\n"
_TWO = "\n### Two\n"  # a second ticket, appended to _ROADMAP
_DESIGN = "# Design\n\nText.\n"
_TIMEOUT = 10
_REFUSAL_SECONDS = 3  # a refusal at start comes long before this


def _project(root: Path, files_: dict[str, str]) -> str:
    (root / ".git").mkdir(parents=True)
    for name, text in files_.items():
        _create(root / name, text)
    return str(root)


def _create(path: Path, text: str) -> None:
    """Write text to path, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _wait_until(condition: Callable[[], bool]) -> bool:
    """Whether condition holds within _TIMEOUT, checked every few milliseconds."""
    deadline = time.monotonic() + _TIMEOUT
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.01)
    return True


class _Client:
    def __init__(self, url: str) -> None:
        self.url = url

    def raw(self, method: str, path: str, *, body: bytes = b"", headers: dict[str, str]) -> tuple[int, Message]:
        """The status and headers of a request sent with exactly the headers given, Host included
        where given."""
        url = urlsplit(self.url)
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=_TIMEOUT)
        try:
            connection.request(method, "/" + path, body=body, headers=headers)
            response = connection.getresponse()
            response.read()
            return response.status, response.headers
        finally:
            connection.close()

    def get(self, path: str) -> tuple[int, str, bytes]:
        try:
            with urllib.request.urlopen(self.url + path, timeout=_TIMEOUT) as r:
                return r.status, r.headers.get_content_type(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get_content_type(), e.read()

    def board(self, since=None) -> dict:
        status, _, body = self.get("api/board" if since is None else f"api/board?since={since}")
        assert status == 200
        return json.loads(body)

    def post(self, path: str, body: dict) -> tuple[int, dict]:
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.url + path, data, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


@pytest.fixture
def serve():
    """Start a server on a project's root; every one started is stopped."""
    started = []

    def start(root: str, *, stderr: Optional[io.StringIO] = None) -> _Client:
        server = KanbanServer(root, stderr=stderr if stderr is not None else io.StringIO())
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        started.append((server, thread))
        return _Client(server.url)

    def stop_all() -> None:
        while started:
            server, thread = started.pop()
            server.shutdown()
            thread.join()
            server.server_close()

    start.stop_all = stop_all
    yield start
    stop_all()


def _json_round_trip(value):
    return json.loads(json.dumps(value))


def test_page_and_its_files_are_served(tmp_path, serve):
    client = serve(_project(tmp_path / "proj", {}))
    assets = [entry for entry in (files("docdicer.kanban") / "assets").iterdir() if entry.is_file()]

    status, content_type, body = client.get("")
    assert (status, content_type) == (200, "text/html")
    assert body == (files("docdicer.kanban") / "assets" / "index.html").read_text(encoding="utf-8").encode("utf-8")
    for entry in assets:
        status, _, body = client.get(entry.name)
        assert (status, body) == (200, entry.read_text(encoding="utf-8").encode("utf-8"))
    assert client.get("nothing.js")[0] == 404
    assert client.get("../kanban/assets/index.html")[0] == 404


_SERVED = {
    "ROADMAP.md": "## Next\n\n### Café\n",
    "ACTIVE_DESIGN/entry-point.md": "# Design\n",
    "ACTIVE_DESIGN/a b%.md": "## Goals\n",
    "ROADMAP_DESIGNS/tree/entry-point.md": "# Tree\n",
    "ROADMAP_DESIGNS/tree/leaf.md": "## Leaf\n",
    "SPEC.md": "# Spec\n",
}


@pytest.mark.parametrize(
    "path, name",
    [
        pytest.param("ROADMAP.md", "ROADMAP.md", id="roadmap"),
        pytest.param("ACTIVE_DESIGN/a%20b%25.md", "ACTIVE_DESIGN/a b%.md", id="percent-decoded-leaf"),
        pytest.param("ROADMAP_DESIGNS/tree/entry-point.md", "ROADMAP_DESIGNS/tree/entry-point.md", id="parked-tree"),
        pytest.param("ROADMAP_DESIGNS/a%FF.md", "ROADMAP_DESIGNS/a\udcff.md", id="parked-file-named-not-utf-8"),
    ],
)
def test_a_file_the_board_reads_is_served(tmp_path, serve, path, name):
    files_ = dict(_SERVED)
    if name not in files_:
        files_[name] = "# A\n"
        try:
            _create(tmp_path / "probe" / os.path.basename(name), "")
        except OSError:
            pytest.skip("the file system refuses a name that is not UTF-8")
    root = _project(tmp_path / "proj", files_)
    status, content_type, body = serve(root).get(path)
    assert (status, content_type, body) == (200, "text/markdown", files_[name].encode("utf-8"))


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("SPEC.md", id="not-read-by-the-board"),
        pytest.param("ROADMAP_DESIGNS/tree/leaf.md", id="parked-tree-leaf"),
        pytest.param("../proj/ROADMAP.md", id="escaping-the-root"),
        pytest.param("%2e%2e/proj/ROADMAP.md", id="escaping-the-root-percent-encoded"),
    ],
)
def test_no_other_file_is_served(tmp_path, serve, path):
    client = serve(_project(tmp_path / "proj", _SERVED))
    assert client.raw("GET", path, headers={"Host": urlsplit(client.url).netloc})[0] == 404


def _denied(path: Path) -> bool:
    """Whether path, its permissions just removed, now refuses this user a read."""
    try:
        path.read_text(encoding="utf-8")
    except PermissionError:
        return True
    return False


def test_an_unreadable_served_file_is_refused_alone(tmp_path, serve):
    root = _project(tmp_path / "proj", _SERVED)
    client = serve(root)
    leaf = tmp_path / "proj" / "ACTIVE_DESIGN" / "a b%.md"
    leaf.chmod(0)
    try:
        if not _denied(leaf):
            pytest.skip("chmod denies this user no read")
        assert client.get("ROADMAP.md")[0] == 200
        assert client.get("ACTIVE_DESIGN/a%20b%25.md")[0] == 404
    finally:
        leaf.chmod(0o644)


def test_board_payload_is_the_model(tmp_path, serve):
    root = _project(
        tmp_path / "proj",
        {
            "ACTIVE_PLAN.md": _PLAN,
            "ROADMAP.md": _ROADMAP,
            "ACTIVE_DESIGN.md": _DESIGN,
            "ROADMAP_DESIGNS/later.md": "x\n",
        },
    )
    payload = serve(root).board()

    assert payload["board"] == _json_round_trip(asdict(read_board(root)))
    assert payload["plan_columns"] == [planform.DRAFTED, *planform.STATE_WORDS]
    assert payload["project"] == "proj"
    assert payload["docdicer_version"] == docdicer.__version__


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda root: (root / "ROADMAP.md").write_text(_ROADMAP + "- Two.\n", encoding="utf-8"), id="content"
        ),
        pytest.param(lambda root: (root / "ACTIVE_DESIGN.md").write_text(_DESIGN, encoding="utf-8"), id="creation"),
        pytest.param(lambda root: (root / "ACTIVE_PLAN.md").unlink(), id="deletion"),
        pytest.param(
            lambda root: (root / "ROADMAP_DESIGNS" / "new.md").write_text("x\n", encoding="utf-8"), id="parked"
        ),
        pytest.param(
            lambda root: _create(root / "ACTIVE_DESIGN" / "entry-point.md", "## Goals\n"), id="diced-design-created"
        ),
        pytest.param(
            lambda root: _create(root / "ROADMAP_DESIGNS" / "tree" / "entry-point.md", "# Tree\n"), id="parked-tree"
        ),
    ],
)
def test_a_change_to_a_watched_file_is_followed(tmp_path, serve, change):
    root = _project(
        tmp_path / "proj", {"ACTIVE_PLAN.md": _PLAN, "ROADMAP.md": _ROADMAP, "ROADMAP_DESIGNS/README.md": ""}
    )
    client = serve(root)
    before = client.board()

    change(Path(root))
    after = client.board(since=before["version"])

    assert after["version"] != before["version"]
    assert after["board"] == _json_round_trip(asdict(read_board(root)))
    assert after["board"] != before["board"]


def test_a_change_to_a_diced_designs_leaf_is_followed(tmp_path, serve):
    entry = "# Design\n\nContents:\n\n- [Goals](goals.md)\n"
    root = _project(tmp_path / "proj", {"ACTIVE_DESIGN/entry-point.md": entry, "ACTIVE_DESIGN/goals.md": "## Goals\n"})
    client = serve(root)
    before = client.board()

    (Path(root) / "ACTIVE_DESIGN" / "goals.md").write_text("## Goals\n\n### Fast\n\nFast.\n", encoding="utf-8")
    after = client.board(since=before["version"])

    assert after["board"]["design"][1]["text"] == "Fast."


def test_waiting_for_a_change_returns_the_board_unchanged_at_close(tmp_path, serve):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    version = client.board()["version"]
    answers = []
    before = set(threading.enumerate())
    waiter = threading.Thread(target=lambda: answers.append(client.board(since=version)))
    waiter.start()
    assert _wait_until(lambda: len(set(threading.enumerate()) - before) >= 2)  # the waiter and its request's

    serve.stop_all()
    waiter.join(_TIMEOUT)

    assert not waiter.is_alive()
    assert answers[0]["version"] == version


def test_an_unreadable_file_keeps_the_last_good_board_and_is_named(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP})
    err = io.StringIO()
    server = KanbanServer(root, stderr=err)
    roadmap = Path(root) / "ROADMAP.md"
    try:
        before = server.payload(None)
        roadmap.chmod(0)
        deadline = time.monotonic() + _TIMEOUT
        while str(roadmap) not in err.getvalue() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.payload(None)["board"] == before["board"]
        roadmap.chmod(0o644)
        roadmap.write_text(_ROADMAP + _TWO, encoding="utf-8")
        after = before
        while len(after["board"]["roadmap"]) != 3 and time.monotonic() < deadline:
            after = server.payload(str(after["version"]))
    finally:
        roadmap.chmod(0o644)
        server.server_close()

    named = err.getvalue().splitlines()
    assert len(named) == 1 and str(roadmap) in named[0]
    assert len(after["board"]["roadmap"]) == 3


def _texts(root: str) -> dict[str, str]:
    return {name: (Path(root) / name).read_text(encoding="utf-8") for name in ("ROADMAP.md", "ACTIVE_DESIGN.md")}


def test_a_card_moves_to_design_and_back(tmp_path, serve):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP + _TWO, "ACTIVE_DESIGN.md": _DESIGN})
    client = serve(root)
    board = client.board()["board"]

    status, payload = client.post("api/to-design", {"card": board["roadmap"][1]})

    assert (status, payload["written"]) == (200, ["ACTIVE_DESIGN.md", "ROADMAP.md"])
    assert payload["board"] == _json_round_trip(asdict(read_board(root)))
    [card] = [c for c in payload["board"]["design"] if c["kind"] == "ticket"]
    assert card["title"] == "Search index"

    status, payload = client.post("api/to-roadmap", {"card": card, "target": None})

    assert (status, payload["written"]) == (200, ["ROADMAP.md", "ACTIVE_DESIGN.md"])
    assert [c["kind"] for c in payload["board"]["design"]] == ["category"]
    returned_last = "## Next\n\n### Two\n\n### Search index\n\nBuild an index.\n"
    assert _texts(root) == {"ROADMAP.md": returned_last, "ACTIVE_DESIGN.md": _DESIGN + "\n## Drafts\n"}


def test_a_card_moves_into_a_diced_design(tmp_path, serve):
    design = {"ACTIVE_DESIGN/entry-point.md": "# Design\n", "ACTIVE_DESIGN/goals.md": "## Goals\n"}
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP, **design})
    client = serve(root)

    status, payload = client.post("api/to-design", {"card": client.board()["board"]["roadmap"][1]})

    assert (status, payload["written"]) == (
        200,
        ["ACTIVE_DESIGN/drafts/search-index.md", "ACTIVE_DESIGN/drafts/index.md", "ACTIVE_DESIGN/entry-point.md"]
        + ["ROADMAP.md"],
    )
    assert [c["path"] for c in payload["board"]["design"] if c["title"] == "Search index"] == [
        "ACTIVE_DESIGN/drafts/search-index.md"
    ]


@pytest.mark.parametrize(
    "path, card",
    [
        pytest.param("api/to-design", {"title": "Gone", "path": "ROADMAP_DESIGNS/gone.md"}, id="to-design"),
        pytest.param(
            "api/to-roadmap",
            {"title": "Gone", "text": "", "path": "ACTIVE_DESIGN.md", "parked": None, "kind": "ticket"},
            id="to-roadmap",
        ),
    ],
)
def test_a_move_of_a_card_not_on_the_board_is_refused(tmp_path, serve, path, card):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN})
    client = serve(root)

    status, payload = client.post(path, {"card": card, "target": None})

    assert status == 409 and payload["error"]
    assert _texts(root) == {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN}


def _fail_roadmap_writes(monkeypatch) -> None:
    """Make a move's every write of ROADMAP.md fail at the file system."""
    real = board_module.replace_lines

    def fail_on_roadmap(path, lines):
        if os.path.basename(path) == "ROADMAP.md":
            raise OSError("disk full")
        real(path, lines)

    monkeypatch.setattr(board_module, "replace_lines", fail_on_roadmap)


def test_a_failed_write_names_the_file_and_the_files_written(tmp_path, serve, monkeypatch):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN})
    client = serve(root)
    _fail_roadmap_writes(monkeypatch)
    status, payload = client.post("api/to-design", {"card": client.board()["board"]["roadmap"][1]})

    assert status == 500
    assert "ROADMAP.md" in payload["error"]
    assert payload["written"] == ["ACTIVE_DESIGN.md"]


def test_a_file_a_move_cannot_read_is_named_from_the_root(tmp_path, serve):
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN})
    client = serve(root)
    card = client.board()["board"]["roadmap"][1]
    roadmap = Path(root) / "ROADMAP.md"
    roadmap.chmod(0)
    try:
        status, payload = client.post("api/to-design", {"card": card})
    finally:
        roadmap.chmod(0o644)

    assert status == 500
    assert "ROADMAP.md" in payload["error"] and root not in payload["error"]
    assert "written" not in payload
    assert _texts(root) == {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN}


@pytest.mark.parametrize("write_fails", [False, True], ids=["moved", "write-failed"])
def test_a_failed_read_after_a_move_is_named_and_keeps_the_moves_answer(tmp_path, serve, monkeypatch, write_fails):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP, "ACTIVE_DESIGN.md": _DESIGN})
    err = io.StringIO()
    client = serve(root, stderr=err)
    card = client.board()["board"]["roadmap"][1]
    unreadable = str(Path(root) / "ACTIVE_DESIGN.md")

    def read_fails(_root):
        raise OSError(errno.EACCES, os.strerror(errno.EACCES), unreadable)

    monkeypatch.setattr(server_module, "read_board", read_fails)
    if write_fails:
        _fail_roadmap_writes(monkeypatch)
    status, payload = client.post("api/to-design", {"card": card})

    if write_fails:
        assert (status, payload["written"]) == (500, ["ACTIVE_DESIGN.md"])
    else:
        assert (status, payload["written"]) == (200, ["ACTIVE_DESIGN.md", "ROADMAP.md"])
    assert unreadable in err.getvalue()


def test_a_read_that_fails_once_is_retried_without_a_further_edit(tmp_path, serve, monkeypatch):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP})
    client = serve(root)
    before = client.board()
    calls = []

    def fails_once(path):
        calls.append(path)
        if len(calls) == 1:
            raise OSError(errno.EIO, os.strerror(errno.EIO), str(Path(path) / "ROADMAP.md"))
        return read_board(path)

    monkeypatch.setattr(server_module, "read_board", fails_once)
    (Path(root) / "ROADMAP.md").write_text(_ROADMAP + _TWO, encoding="utf-8")
    after = client.board(since=before["version"])
    while len(after["board"]["roadmap"]) != 3:  # a poll may catch the write half done
        after = client.board(since=after["version"])

    assert len(calls) >= 2
    assert after["board"] == _json_round_trip(asdict(read_board(root)))
    assert len(after["board"]["roadmap"]) == 3


_JSON = "application/json"


@pytest.mark.parametrize(
    "path, content_type, body, length, status",
    [
        pytest.param("api/nothing", _JSON, b"{}", None, 404, id="unknown-endpoint"),
        pytest.param("api/to-design", "text/plain", b"{}", None, 415, id="not-json"),
        pytest.param("api/to-design", _JSON, b"{not json", None, 400, id="unparsable"),
        pytest.param("api/to-design", _JSON, b"[]", None, 400, id="not-an-object"),
        pytest.param("api/to-design", _JSON, b'{"card": "x"}', None, 400, id="card-not-an-object"),
        pytest.param("api/to-roadmap", _JSON, b'{"card": {}, "target": 1}', None, 400, id="target-not-an-object"),
        pytest.param("api/to-design", _JSON, b"", "x", 400, id="length-not-a-number"),
        pytest.param("api/to-design", _JSON, b"", "-1", 400, id="length-negative"),
    ],
)
def test_a_bad_request_is_refused(tmp_path, serve, path, content_type, body, length, status):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    url = urlsplit(client.url)
    headers = {"Host": url.netloc, "Content-Type": content_type, "Content-Length": length or str(len(body))}

    assert client.raw("POST", path, body=body, headers=headers)[0] == status
    assert (tmp_path / "proj" / "ROADMAP.md").read_text(encoding="utf-8") == _ROADMAP


def test_a_stop_request_that_is_not_json_is_refused_and_the_board_still_answers(tmp_path, serve):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    headers = {"Host": urlsplit(client.url).netloc, "Content-Type": "text/plain", "Content-Length": "2"}

    assert client.raw("POST", "api/stop", body=b"{}", headers=headers)[0] == 415
    assert client.board()["version"] == 1


def test_a_cross_origin_preflight_is_not_granted(tmp_path, serve):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    headers = {
        "Host": urlsplit(client.url).netloc,
        "Origin": "http://attacker.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }

    _, answer = client.raw("OPTIONS", "api/to-design", headers=headers)

    assert "Access-Control-Allow-Origin" not in answer


@pytest.mark.parametrize(
    "method, path, body, answered",
    [
        pytest.param("GET", "api/board", b"", 200, id="GET"),
        # a POST past the Host check fails on its body, so that nothing is moved either way
        pytest.param("POST", "api/to-design", b"[]", 400, id="POST"),
        pytest.param("POST", "api/stop", b"[]", 400, id="POST-stop"),
    ],
)
@pytest.mark.parametrize(
    "host, accepted",
    [
        pytest.param("127.0.0.1:{port}", True, id="address"),
        pytest.param("localhost:{port}", True, id="localhost"),
        pytest.param("127.0.0.1:{other}", False, id="address-other-port"),
        pytest.param("localhost:{other}", False, id="localhost-other-port"),
        pytest.param("attacker.example", False, id="other-host"),
    ],
)
def test_only_a_request_naming_the_servers_own_host_and_port_is_answered(
    tmp_path, serve, method, path, body, answered, host, accepted
):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    port = urlsplit(client.url).port
    headers = {"Host": host.format(port=port, other=port + 1), "Content-Type": _JSON}

    status, _ = client.raw(method, path, body=body, headers=headers)

    assert status == (answered if accepted else 403)


def test_every_response_forbids_sniffing_and_the_pages_restrict_their_sources(tmp_path, serve):
    client = serve(_project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP}))
    host = {"Host": urlsplit(client.url).netloc}

    served = ("", "board.js", "ROADMAP.md")
    for path in (*served, "nothing.js", "api/board"):
        status, headers = client.raw("GET", path, headers=host)
        if path in served:
            assert status == 200, path
        assert headers["X-Content-Type-Options"] == "nosniff", path
        if not path.startswith("api/"):
            assert headers["Content-Security-Policy"] == "default-src 'self'; frame-ancestors 'none'", path


def test_a_client_gone_mid_request_leaves_stderr_empty(tmp_path, serve, capsys):
    root = _project(tmp_path / "proj", {"ACTIVE_PLAN.md": _PLAN})
    client = serve(root)
    version = client.board()["version"]
    url = urlsplit(client.url)
    before = set(threading.enumerate())

    with socket.create_connection((url.hostname, url.port), timeout=_TIMEOUT) as gone:
        gone.sendall(f"GET /api/board?since={version} HTTP/1.1\r\nHost: {url.netloc}\r\n\r\n".encode("ascii"))
        gone.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))  # close with a reset
    # wakes the long poll onto the closed socket
    (Path(root) / "ACTIVE_PLAN.md").write_text(_PLAN + "\nMore.\n", encoding="utf-8")
    for thread in set(threading.enumerate()) - before:
        thread.join(_TIMEOUT)
        assert not thread.is_alive()

    assert capsys.readouterr().err == ""


def _run_refused(monkeypatch, start: str) -> tuple[int, str, str]:
    """run_kanban's status, stdout and stderr, run from start, where it refuses to start. Where it
    starts instead, the server is shut down and the test fails, rather than serving until
    interrupted."""
    started: list[KanbanServer] = []

    class Recorded(KanbanServer):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            started.append(self)

    monkeypatch.setattr(server_module, "KanbanServer", Recorded)
    out, err = io.StringIO(), io.StringIO()
    statuses: list[int] = []
    run = threading.Thread(
        target=lambda: statuses.append(run_kanban(None, start=start, stdout=out, stderr=err)),
        daemon=True,
    )
    run.start()
    run.join(_REFUSAL_SECONDS)
    if run.is_alive():
        for server in started:
            server.shutdown()
        run.join(_TIMEOUT)
        pytest.fail(f"kanban started instead of refusing: {out.getvalue()!r}")
    return statuses[0], out.getvalue(), err.getvalue()


def test_no_project_root_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(planform.os.path, "lexists", lambda path: False)

    status, out, err = _run_refused(monkeypatch, str(tmp_path))

    assert (status, out) == (2, "")
    assert str(tmp_path) in err


def test_an_unreadable_document_at_start_is_refused(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP})
    roadmap = Path(root) / "ROADMAP.md"
    roadmap.chmod(0)
    try:
        status, out, err = _run_refused(monkeypatch, root)
    finally:
        roadmap.chmod(0o644)

    assert (status, out) == (2, "")
    assert str(roadmap) in err


def test_a_read_failure_naming_no_file_at_start_names_the_root(tmp_path, monkeypatch):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP})

    def read_fails(_root):
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    monkeypatch.setattr(server_module, "read_board", read_fails)
    status, out, err = _run_refused(monkeypatch, root)

    assert (status, out) == (2, "")
    assert root in err


def test_a_port_that_cannot_be_bound_is_refused_with_the_reason(tmp_path, monkeypatch):
    root = _project(tmp_path / "proj", {"ROADMAP.md": _ROADMAP})

    def bind_fails(self):
        raise OSError(errno.EADDRINUSE, os.strerror(errno.EADDRINUSE))

    monkeypatch.setattr(KanbanServer, "server_bind", bind_fails)
    status, out, err = _run_refused(monkeypatch, root)

    assert (status, out) == (2, "")
    assert os.strerror(errno.EADDRINUSE) in err


def _serve_the_command(
    root: str, end: Callable[["subprocess.Popen[bytes]", _Client], None]
) -> tuple[int, bytes, bytes]:
    """Run `python -m docdicer kanban root`, fetch the page from the URL it prints, end it with end,
    and give its status and what it wrote after the URL line."""
    child = subprocess.Popen(
        [sys.executable, "-m", "docdicer", "kanban", root],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ready, _, _ = select.select([child.stdout], [], [], _TIMEOUT)
        assert ready, "no URL printed"
        url = child.stdout.readline().decode("utf-8").strip()
        client = _Client(url)
        assert url.startswith("http://127.0.0.1:") and url.endswith("/")
        assert client.get("")[0] == 200
        end(child, client)
        out, err = child.communicate(timeout=_TIMEOUT)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    return child.returncode, out, err


def test_the_command_prints_the_url_and_serves_until_interrupted(tmp_path):
    root = _project(tmp_path / "proj", {"ACTIVE_PLAN.md": _PLAN})
    assert _serve_the_command(root, lambda child, _: child.send_signal(signal.SIGINT)) == (0, b"", b"")


def test_the_command_serves_until_stopped_from_the_page(tmp_path):
    root = _project(tmp_path / "proj", {"ACTIVE_PLAN.md": _PLAN})
    answers = []
    assert _serve_the_command(root, lambda _, client: answers.append(client.post("api/stop", {}))) == (0, b"", b"")
    assert answers == [(200, {})]
