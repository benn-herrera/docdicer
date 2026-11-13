import io

from docdicer.dicerlib import manifest


def test_title_is_the_plain_heading_text(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("#   [Spec](x.md) v2  \n\nText.\n", encoding="utf-8")
    assert manifest._title(str(doc)) == "Spec v2"


def test_purpose_is_the_first_sentence_as_plain_text(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# T\n\nThe [outcomes](a.md) and `[kept](b.md)`. More.\n", encoding="utf-8")
    assert manifest._purpose(str(doc)) == "The outcomes and `[kept](b.md)`."


def test_check_written_reports_only_prose_links(tmp_path):
    entry = tmp_path / "entry-point.md"
    entry.write_text(
        "# E\n\nSee [prose](gone.md) and `[span](span.md)`.\n\n```\n[fenced](fenced.md)\n```\n",
        encoding="utf-8",
    )
    out = io.StringIO()
    assert not manifest._check_written([str(entry)], out=out)
    assert [line for line in out.getvalue().splitlines() if "DEAD" in line] == [f"  DEAD {entry} -> gone.md"]
