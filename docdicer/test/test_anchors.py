import pytest

from docdicer.dicerlib.anchors import github_anchor, heading_anchor_list


@pytest.mark.parametrize(
    "text, anchor",
    [
        pytest.param("Hello World", "hello-world", id="lowered-spaces-made-hyphens"),
        pytest.param("API & Usage!", "api--usage", id="punctuation-deleted-spaces-kept"),
        pytest.param("snake_case-name", "snake_case-name", id="underscore-and-hyphen-kept"),
        pytest.param("`code` span", "code-span", id="backticks-deleted"),
        pytest.param("Step 2.1", "step-21", id="dot-deleted"),
        pytest.param("Café Über", "café-über", id="non-ascii-letters-kept-and-lowered"),
        pytest.param("x٣", "x٣", id="non-ascii-digit-kept"),
        pytest.param("[Plan Status Form](x)", "plan-status-form", id="link-reduced-to-text"),
    ],
)
def test_github_anchor(text, anchor):
    assert github_anchor(text) == anchor


@pytest.mark.parametrize(
    "lines, anchors",
    [
        pytest.param(
            ["# Setup", "## Setup", "### Setup"], [(1, "setup"), (2, "setup-1"), (3, "setup-2")], id="third-repeat"
        ),
        pytest.param(["## A b", "text", "## a-b"], [(1, "a-b"), (3, "a-b-1")], id="repeat-by-anchor-not-text"),
        pytest.param(["## Title ##", "### Other #"], [(1, "title"), (2, "other")], id="closing-hashes-removed"),
        pytest.param(["   ## Three", "    ## Four"], [(1, "three")], id="up-to-three-leading-spaces"),
        pytest.param(["###### Six", "####### Seven"], [(1, "six")], id="levels-1-to-6"),
        pytest.param(["#hashtag", "# Real"], [(2, "real")], id="no-space-not-a-heading"),
        pytest.param(["# A", "```", "# A", "```", "# A"], [(1, "a"), (5, "a-1")], id="fenced-not-counted"),
    ],
)
def test_heading_anchor_list(lines, anchors):
    assert [(no, anchor.name) for no, anchor in heading_anchor_list(lines)] == anchors
