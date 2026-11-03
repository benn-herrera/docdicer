#!/usr/bin/env python3
"""docdicer: split markdown documents by heading into trees of small linked files (see README.md).

Exit status: 0 on success, 1 when a check or step fails, 2 on bad arguments.
"""

import argparse
import os
import sys
from typing import Optional, TextIO

from . import __version__
from .dicerlib.dicedoc import dice_doc, verify
from .dicerlib.linkcheck import check_markdown_links, markdown_files
from .dicerlib.manifest import dice_docs
from .dicerlib.refactor import list_runins, refactor
from .dicerlib.textfile import read_lines
from .dicerlib.treecheck import check_trees


def _keep_list() -> list[str]:
    """Titles never converted: the comma list in DICER_KEEP, default "Open"; empty keeps none."""
    keep = os.environ.get("DICER_KEEP", "Open")
    return keep.split(",") if keep else []


def _refuse_unreadable(roots: list[str], *, err: TextIO) -> bool:
    """Report each markdown file under roots that cannot be read as a file; True if any."""
    unreadable = [f for f in markdown_files(roots) if not (os.path.isfile(f) and os.access(f, os.R_OK))]
    for f in unreadable:
        print(f"cannot read: {f}", file=err)
    return bool(unreadable)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docdicer", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = commands.add_parser("dice-doc", help="dice one document, then check it reassembles and its links resolve")
    p.add_argument("monolith", help="the markdown document to dice")
    p.add_argument("out", help="output directory, absent or empty")
    p.add_argument("map", nargs="?", default="", help="link map TSV")

    p = commands.add_parser("dice-docs", help="dice the documents a manifest TSV lists, then verify them all")
    p.add_argument("manifest", help="manifest TSV naming the documents and their output directories")
    p.add_argument("src", help="directory the manifest's files are read from")
    p.add_argument("work", help="directory for intermediates")

    p = commands.add_parser("verify", help="re-run the checks on trees already built")
    p.add_argument("map", help='link map TSV, or "-" for none')
    p.add_argument("pairs", nargs="+", metavar="monolith out", help="each monolith followed by its output directory")

    p = commands.add_parser("refactor", help="turn bold run-in titles into headings")
    p.add_argument("input", metavar="in", help="the markdown document to read")
    p.add_argument("output", metavar="out", help="where the refactored document is written")
    p.add_argument("items", nargs="?", default="", help='"0" or absent: leave bold list items alone')

    p = commands.add_parser("list", help="classify every bold-led line of a document")
    p.add_argument("doc", help="the markdown document to classify")

    p = commands.add_parser("check-links", help="check the relative links and anchors of markdown files")
    p.add_argument("roots", nargs="+", metavar="root", help="a directory, walked for every .md, or one file")

    p = commands.add_parser(
        "check-tree", help="check every document of a diced tree is linked from its parent and reachable"
    )
    p.add_argument("roots", nargs="+", metavar="root", help="a diced tree's directory, holding its entry-point.md")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="surrogateescape")
    parser = _parser()
    args = parser.parse_args(argv)
    out, err = sys.stdout, sys.stderr
    if args.command == "dice-doc":
        return dice_doc(args.monolith, args.out, args.map, stdout=out, stderr=err)
    if args.command == "dice-docs":
        return dice_docs(args.manifest, args.src, args.work, keep=_keep_list(), stdout=out, stderr=err)
    if args.command == "verify":
        if len(args.pairs) % 2:
            parser.error("verify takes <map|-> followed by <monolith> <out> pairs")
        pairs = list(zip(args.pairs[::2], args.pairs[1::2]))
        return verify("" if args.map == "-" else args.map, pairs, stdout=out, stderr=err)
    if args.command == "refactor":
        items = args.items not in ("", "0")
        return refactor(args.input, args.output, items=items, keep=_keep_list(), out=out, err=err)
    if args.command == "check-links":
        missing = [root for root in args.roots if not os.path.exists(root)]
        if missing:
            parser.error(f"no such root: {', '.join(missing)}")
        if _refuse_unreadable(args.roots, err=err):
            return 2
        return 0 if check_markdown_links(args.roots, out=out, err=err) else 1
    if args.command == "check-tree":
        missing = [root for root in args.roots if not os.path.isdir(root)]
        if missing:
            parser.error(f"no such directory: {', '.join(missing)}")
        if _refuse_unreadable(args.roots, err=err):
            return 2
        return 0 if check_trees(args.roots, out=out, err=err) else 1
    try:
        lines = read_lines(args.doc)
    except OSError:
        print(f"not a file: {args.doc}", file=err)
        return 2
    for row in list_runins(lines, name=args.doc, keep=_keep_list()):
        print(row, file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
