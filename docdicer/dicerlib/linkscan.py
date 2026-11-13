"""The one scanner of a line's links and section references, the reduction of links to their text,
and the collection of a line's link targets."""

import re
from typing import Callable, Optional

_SECTION_REF = re.compile(r"§[0-9]+(?:\.[0-9]+)*")

# (raw link, text, target, rest of the line after the link) -> replacement
OnLink = Callable[[str, str, str, str], str]
# (reference, line, offset after the reference, output so far) -> (replacement, offset to resume at)
OnRef = Callable[[str, str, int, str], tuple[str, int]]


def scan(s: str, on_link: OnLink, on_ref: Optional[OnRef] = None) -> str:
    """Rewrite the prose of one line: code spans pass through, each `[text](target)` is replaced by
    on_link and, given on_ref, each `§N` reference by on_ref."""
    if "](" not in s and (on_ref is None or "§" not in s):
        return s
    out = []
    p, n = 0, len(s)
    while p < n:
        c = s[p]
        if c == "`":
            q = p
            while q < n and s[q] == "`":
                q += 1
            close = s.find(s[p:q], q)
            end = q if close < 0 else close + q - p
            out.append(s[p:end])
            p = end
            continue
        if c == "[":
            bracket = s.find("]", p)
            paren = s.find(")", bracket + 2) if bracket >= 0 and s.startswith("](", bracket) else -1
            if paren >= 0:
                out.append(on_link(s[p : paren + 1], s[p + 1 : bracket], s[bracket + 2 : paren], s[paren + 1 :]))
                p = paren + 1
                continue
        if on_ref is not None:
            m = _SECTION_REF.match(s, p)
            if m:
                text, p = on_ref(m.group(), s, m.end(), "".join(out))
                out.append(text)
                continue
        out.append(c)
        p += 1
    return "".join(out)


def plain_text(s: str) -> str:
    """s with each link outside code spans replaced by its text."""
    return scan(s, lambda raw, text, target, after: text)


def link_targets(line: str) -> list[str]:
    """The target of every link in the prose of a line, in order."""
    found = []

    def collect(raw: str, text: str, target: str, after: str) -> str:
        found.append(target)
        return raw

    scan(line, collect)
    return found
