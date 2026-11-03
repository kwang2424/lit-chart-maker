"""Convert an HTML page to plain text, keeping h1-h4 headings as "#### " lines.

Usage: python -I html_to_text.py page.html > page.txt
"""
import re, sys, html
t = open(sys.argv[1], errors="ignore").read()
t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
t = re.sub(r"<h([1-4])[^>]*>(.*?)</h\1>", lambda m: "\n#### " + re.sub("<[^>]+>", "", m.group(2)) + "\n", t, flags=re.S)
t = re.sub(r"<br\s*/?>|</(p|tr|li|div)>", "\n", t)
t = re.sub(r"<[^>]+>", " ", t); t = html.unescape(t)
t = re.sub(r"[ \t]+", " ", t); print(re.sub(r"\n\s*\n+", "\n", t))
