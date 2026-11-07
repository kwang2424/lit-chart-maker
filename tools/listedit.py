"""Small helpers for editing list files without disturbing their layout or comments.

Loading and re-dumping YAML would lose the comments and folded text, so these edit the
text directly. Typical use, from the repository root:

    import sys; sys.path.insert(0, "tools")
    from listedit import add_after
    add_after("spinoza", "ttp", "hobbes:leviathan", "context",
              'The SEP: "Spinoza was clearly influenced by his reading of that British thinker".',
              "sep-spinoza", "§3.2 The State", "SEP entry, accessed 2026-11")

Then run `python tools/build.py` to validate and regenerate.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

LISTS = Path(__file__).resolve().parent.parent / "lists"


def fold(text: str, indent: str) -> str:
    return textwrap.fill(" ".join(text.split()), width=88, initial_indent=indent, subsequent_indent=indent)


def quoted(value: str) -> str:
    """A YAML double-quoted scalar (safe for ': ', ' #' and quotes)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def block_span(text: str, work_id: str) -> tuple[int, int]:
    """Start and end of a work's block (after its `- id:` line) in a list file."""
    m = re.search(rf"^  - id: {re.escape(work_id)}\n", text, re.M)
    if not m:
        raise KeyError(work_id)
    start = m.end()
    nxt = re.search(r"^  - id: |^  # ", text[start:], re.M)
    return start, start + (nxt.start() if nxt else len(text) - start)


def add_after(list_id: str, work_id: str, target: str, strength: str, why: str,
              source: str, locator: str, checked_in: str) -> None:
    """Add a "read `target` first" link to a work, citing one source."""
    path = LISTS / f"{list_id}.yaml"
    text = path.read_text(encoding="utf-8")
    start, end = block_span(text, work_id)
    block = text[start:end]
    item = (f"      - work: {target}\n        strength: {strength}\n        why: >\n{fold(why, ' ' * 10)}\n"
            f"        sources:\n          - source: {source}\n            locator: {quoted(locator)}\n"
            f"            verified: true\n            checked_in: {quoted(checked_in)}\n")
    if "\n    after:\n" in "\n" + block:
        j = ("\n" + block).index("\n    after:\n") + len("\n    after:\n") - 1
        block = block[:j] + item + block[j:]
    else:
        block = block.rstrip("\n") + "\n    after:\n" + item + ("\n" if block.endswith("\n\n") else "")
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def add_work(list_id: str, before_work_id: str, yaml_text: str) -> None:
    """Insert a work's YAML (starting `  - id: ...`) just before another work."""
    path = LISTS / f"{list_id}.yaml"
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^  - id: {re.escape(before_work_id)}\n", text, re.M)
    if not m:
        raise KeyError(before_work_id)
    path.write_text(text[:m.start()] + yaml_text.rstrip("\n") + "\n\n" + text[m.start():], encoding="utf-8")
