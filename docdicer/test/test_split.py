import io

from docdicer.dicerlib.outline import Outline, plan_sections
from docdicer.dicerlib.split import contents_block


def _outline(lines):
    sections, ok = plan_sections(lines, err=io.StringIO())
    assert ok
    return Outline(sections)


_DOC = [
    "# Doc",
    "## 1. Intro",
    "### 1.1 Scope",
    "#### Detail",
    "### 1.2 Terms",
    "## Notes",
]


def test_entry_point_lists_every_section_indented_by_depth():
    outline = _outline(_DOC)
    assert contents_block(outline, outline.sections[0]) == [
        "Contents:",
        "",
        "- [§1 Intro](1-intro/index.md)",
        "  - [§1.1 Scope](1-intro/1.1-scope/index.md)",
        "    - [§1.1 Detail](1-intro/1.1-scope/detail.md)",
        "  - [§1.2 Terms](1-intro/1.2-terms.md)",
        "- [Notes](notes.md)",
    ]


def test_index_lists_direct_children_relative_to_its_directory():
    outline = _outline(_DOC)
    assert contents_block(outline, outline.sections[1]) == [
        "Contents:",
        "",
        "- [§1.1 Scope](1.1-scope/index.md)",
        "- [§1.2 Terms](1.2-terms.md)",
    ]
    assert contents_block(outline, outline.sections[2]) == ["Contents:", "", "- [§1.1 Detail](detail.md)"]


def test_entry_point_with_nothing_to_list():
    outline = _outline(["# Doc", "text"])
    assert contents_block(outline, outline.sections[0]) == ["Contents:", ""]
