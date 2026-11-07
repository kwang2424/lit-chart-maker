"""Quote YAML text values that YAML would misread.

Two traps: ": " inside a value breaks parsing, and " #" starts a comment, so
`checked_in: Project Gutenberg #1232` silently becomes "Project Gutenberg".

Usage: python -I quote_colons.py lists/<author>.yaml   (edits in place, prints what it quoted)
"""
import re, sys

TEXT_KEYS = {"title", "author", "why", "text", "note", "locator", "checked_in", "translation",
             "tier_note", "scope", "url", "reviewed_by"}
p = sys.argv[1]
out = []
for line in open(p):
    m = re.match(r"^(\s*(?:- )?([a-z_]+): )(.*)$", line.rstrip("\n"))
    if m and m.group(3)[:1] not in "'\"[>|{" and (
        ": " in m.group(3) or (" #" in m.group(3) and m.group(2) in TEXT_KEYS)
    ):
        val = m.group(3).replace("\\", "\\\\").replace('"', '\\"')
        line = f'{m.group(1)}"{val}"\n'
        print("quoted:", line.strip()[:80])
    out.append(line)
open(p, "w").write("".join(out))
