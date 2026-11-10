import stat
from pathlib import Path

import pytest

from docdicer.dicerlib import textfile
from docdicer.dicerlib.textfile import fence_flags, join_lines, read_lines, replace_lines, split_lines, write_lines


@pytest.mark.parametrize(
    "text, lines",
    [
        pytest.param("a\nb\n", ["a", "b"], id="terminated"),
        pytest.param("a\r\nb\r\n", ["a\r", "b\r"], id="crlf-keeps-cr"),
        pytest.param("a\rb\n", ["a\rb"], id="lone-cr-not-a-break"),
        pytest.param("a\x0bb\x0cc\x1cd\x85e f g\n", ["a\x0bb\x0cc\x1cd\x85e f g"], id="other-separators-not-breaks"),
        pytest.param("a\nb", ["a", "b"], id="unterminated-last-line-counts"),
        pytest.param("a\n\n", ["a", ""], id="blank-last-line-kept"),
        pytest.param("", [], id="empty"),
    ],
)
def test_split_lines_breaks_on_newline_only(text, lines):
    assert split_lines(text) == lines


@pytest.mark.parametrize(
    "text, written",
    [
        pytest.param("a\nb\n", "a\nb\n", id="terminated-unchanged"),
        pytest.param("a\nb", "a\nb\n", id="unterminated-gains-final-newline"),
        pytest.param("a\r\n\n", "a\r\n\n", id="cr-and-blank-line-preserved"),
    ],
)
def test_join_lines_terminates_every_line(text, written):
    assert join_lines(split_lines(text)) == written


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"a\r\nb\r\n", id="crlf"),
        pytest.param(b"a\rb\n", id="lone-cr"),
        pytest.param(b"caf\xe9 \xff\xfe\n\xc3\n", id="invalid-utf8"),
        pytest.param("café ∑\n".encode("utf-8"), id="valid-utf8"),
    ],
)
def test_read_then_write_keeps_every_byte(tmp_path: Path, content: bytes) -> None:
    source, copy = tmp_path / "in.md", tmp_path / "out.md"
    source.write_bytes(content)
    write_lines(str(copy), read_lines(str(source)))
    assert copy.read_bytes() == content


F, T = False, True


@pytest.mark.parametrize(
    "lines, flags",
    [
        pytest.param(["a", "```", "x", "```", "b"], [F, T, T, T, F], id="backtick-fence"),
        pytest.param(["a", "~~~", "x", "~~~", "b"], [F, T, T, T, F], id="tilde-fence"),
        pytest.param(["  ```", "x", "  ```", "b"], [T, T, T, F], id="indented-fence"),
        pytest.param(["\t```", "x", "\t```", "b"], [F, F, F, F], id="tab-indented-not-a-fence"),
        pytest.param(["```python", "x", "```", "b"], [T, T, T, F], id="info-string"),
        pytest.param(["``", "x", "``"], [F, F, F], id="two-backticks-not-a-fence"),
        pytest.param(["```a`b", "x", "```"], [F, F, T], id="backtick-in-backtick-info-string-not-a-fence"),
        pytest.param(["~~~a`b", "x", "~~~", "b"], [T, T, T, F], id="backtick-in-tilde-info-string-opens"),
        pytest.param(["```", "~~~", "x", "```", "b"], [T, T, T, T, F], id="other-character-does-not-close"),
        pytest.param(["````", "```", "x", "`````", "b"], [T, T, T, T, F], id="close-needs-at-least-as-many"),
        pytest.param(["```", "```  ", "b"], [T, T, F], id="close-followed-by-spaces"),
        pytest.param(["```", "``` x", "y", "```", "b"], [T, T, T, T, F], id="close-followed-by-text-does-not-close"),
        pytest.param(["a", "```", "x", "y"], [F, T, T, T], id="unclosed-runs-to-end"),
    ],
)
def test_fence_flags(lines, flags):
    assert fence_flags(lines) == flags


def test_replace_lines_writes_through_a_link_and_keeps_the_mode(tmp_path):
    target, link = tmp_path / "doc.md", tmp_path / "link.md"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o640)
    link.symlink_to("doc.md")

    replace_lines(str(link), ["new"])

    assert target.read_text(encoding="utf-8") == "new\n"
    assert link.is_symlink()
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert sorted(p.name for p in tmp_path.iterdir()) == ["doc.md", "link.md"]


def test_replace_lines_that_fails_leaves_the_old_file_whole_and_nothing_else(tmp_path, monkeypatch):
    target = tmp_path / "doc.md"
    target.write_text("old\n", encoding="utf-8")
    markdown_at_rename = []

    def rename_fails(source, destination):
        markdown_at_rename.extend(p.name for p in tmp_path.iterdir() if p.suffix == ".md")
        raise OSError("disk full")

    monkeypatch.setattr(textfile.os, "replace", rename_fails)
    with pytest.raises(OSError):
        replace_lines(str(target), ["new"])

    assert markdown_at_rename == ["doc.md"]  # the file being written is no `.md` a directory scan would read
    assert target.read_text(encoding="utf-8") == "old\n"
    assert [p.name for p in tmp_path.iterdir()] == ["doc.md"]
