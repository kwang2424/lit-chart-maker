"""Report which section of an encyclopedia entry a phrase appears in, for exact locators.

Usage: python -I find_section.py entry.txt "phrase one" "phrase two" ...
  (entry.txt from html_to_text.py, so headings are "#### " lines)
"""
import sys

lines = open(sys.argv[1], errors="ignore").read().split("\n")
for phrase in sys.argv[2:]:
    section, hits = None, []
    for line in lines:
        if line.startswith("#### "):
            section = line[5:].strip()
        if phrase.lower() in line.lower():
            hits.append(section)
    print(f"{phrase!r}: {', '.join(dict.fromkeys(str(h) for h in hits)) or 'NOT FOUND'}")
