import pytest

from docdicer.dicerlib.linkscan import link_targets, plain_text


@pytest.mark.parametrize(
    "line, targets",
    [
        pytest.param("see [a](b.md) here", ["b.md"], id="link"),
        pytest.param("![alt](img.png)", ["img.png"], id="image"),
        pytest.param("[a](b.md) and [c](d.md)", ["b.md", "d.md"], id="two-in-order"),
        pytest.param("[a](b(c).md)", ["b(c"], id="target-ends-at-first-paren"),
        pytest.param('[a](b.md "title")', ['b.md "title"'], id="title-not-interpreted"),
        pytest.param("[a](<b c.md>)", ["<b c.md>"], id="angle-brackets-not-interpreted"),
        pytest.param("\\[a](b.md)", ["b.md"], id="escape-not-interpreted"),
        pytest.param("[a][ref] and [ref]: b.md", [], id="reference-style-not-a-link"),
        pytest.param("<https://e.com/x>", [], id="autolink-not-a-link"),
        pytest.param("[a] (b.md)", [], id="space-before-paren"),
        pytest.param("`[a](b.md)` and [c](d.md)", ["d.md"], id="code-span"),
        pytest.param("``x ` [a](b.md)`` [c](d.md)", ["d.md"], id="code-span-closes-on-same-length-run"),
        pytest.param("x ` [a](b.md)", ["b.md"], id="unmatched-backtick-literal"),
    ],
)
def test_link_targets(line: str, targets: list[str]) -> None:
    assert link_targets(line) == targets


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("[a](x) b", "a b", id="link-reduced-to-text"),
        pytest.param("`[a](x)` b", "`[a](x)` b", id="code-span-kept"),
        pytest.param("[a](x) and [b](y)", "a and b", id="every-link-reduced"),
        pytest.param("![alt](i.png)", "!alt", id="image-bang-precedes-link"),
        pytest.param("no links", "no links", id="no-links-unchanged"),
    ],
)
def test_plain_text(text, expected):
    assert plain_text(text) == expected
