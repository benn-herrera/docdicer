from pathlib import Path

import pytest

from docdicer.dicerlib.textfile import fence_flags, join_lines, read_lines, split_lines, write_lines


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
