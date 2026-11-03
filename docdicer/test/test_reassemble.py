import pytest

from docdicer.dicerlib.reassemble import contents_cut


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
