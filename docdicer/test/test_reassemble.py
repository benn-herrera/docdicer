import pytest

from docdicer.dicerlib.reassemble import contents_cut, own_end


@pytest.mark.parametrize(
    "lines, cut",
    [
        pytest.param(["## A", "text", "Contents:", "", "- [b](b.md)"], 2, id="block-at-end"),
        pytest.param(["Contents:", "quoted", "Contents:", ""], 2, id="last-of-two"),
        pytest.param(["## A", "Contents:", "", "- [b](b.md)", "", "- [G](g/index.md)"], 1, id="lines-after-block"),
        pytest.param(["## A", "Contents: ", " Contents:", "contents:"], -1, id="not-exact-no-block"),
    ],
)
def test_contents_cut_is_last_exact_contents_line(lines, cut):
    assert contents_cut(lines) == cut


_WITH_CONTENTS = ["## A", "Contents:", "", "- [b](b.md)"]


@pytest.mark.parametrize(
    "path, lines, end",
    [
        pytest.param("entry-point.md", _WITH_CONTENTS, 1, id="entry-point"),
        pytest.param("g/index.md", _WITH_CONTENTS, 1, id="index"),
        pytest.param("g/v/entry-point.md", _WITH_CONTENTS, 1, id="nested-volume"),
        pytest.param("g/leaf.md", _WITH_CONTENTS, 4, id="leaf-keeps-its-contents-line"),
        pytest.param("index.md", ["## A", "text"], 2, id="head-without-block"),
    ],
)
def test_own_end_cuts_only_a_head_file_at_its_contents_block(path, lines, end):
    assert own_end(path, lines) == end
