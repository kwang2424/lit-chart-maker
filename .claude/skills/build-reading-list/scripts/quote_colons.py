"""Quote YAML scalar values that contain ": " (which otherwise break parsing).

Usage: python -I quote_colons.py lists/<author>.yaml   (edits in place, prints what it quoted)
"""
import re, sys
p = sys.argv[1]
out = []
for line in open(p):
    m = re.match(r"^(\s*(?:- )?[a-z_]+: )(.*)$", line.rstrip("\n"))
    if m and ": " in m.group(2) and m.group(2)[:1] not in "'\"[>|{":
        val = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
        line = f'{m.group(1)}"{val}"\n'
        print("quoted:", line.strip()[:80])
    out.append(line)
open(p, "w").write("".join(out))
