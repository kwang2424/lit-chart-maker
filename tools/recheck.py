#!/usr/bin/env python3
"""Re-check quoted phrases against the sources they cite.

Most `why` and tip texts quote their source ("…"). Sources change: the SEP revises
entries, syllabi move. This fetches each cited source that can be fetched and checks
that every quoted phrase still appears in it.

Fetchable sources:
  - a source with a `url` (encyclopedia entries, syllabi, interviews; HTML or PDF)
  - a citation whose `checked_in` names a Project Gutenberg text ("Project Gutenberg #1232")

Usage:
  python tools/recheck.py                 # check everything (uses a local cache)
  python tools/recheck.py --list hobbes   # one list
  python tools/recheck.py --refresh       # ignore the cache and fetch again

Exit code 1 if a quote is missing from every source of its claim that could be fetched.
Quotes that can't match for a known reason (an OCR slip, a typo in the source) are listed,
with the reason, in tools/recheck_known.yaml.
Sources that can't be fetched (blocked, offline, no URL) are reported but don't fail.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import build as b
import citations

CACHE = b.ROOT / ".cache" / "recheck"
UA = "Mozilla/5.0 (compatible; reading-order-recheck; +https://github.com/kwang2424/lit-chart-maker)"

GUTENBERG = re.compile(r"Project Gutenberg #(\d+)")
ARCHIVE = re.compile(r"archive\.org/details/[^/?#\s,;]+")
QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')


def normalize(text: str) -> str:
    """Lowercase letters and digits only, with no spaces at all.

    Dropping spaces makes the match robust to what scanned and web texts do to words:
    hyphenation across lines ("profes- sion"), tags inside words, odd apostrophes."""
    text = html.unescape(text).replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    text = unicodedata.normalize("NFKD", text).lower()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"-\s*\n\s*", "", text)               # words hyphenated across lines
    return re.sub(r"[^a-z0-9]+", "", text)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    return re.sub(r"<[^>]+>", " ", raw)


def fragments(quote: str) -> list[str]:
    """Split a quote at ellipses and editorial brackets; keep pieces worth checking."""
    parts = re.split(r"…|\.\.\.|\[[^\]]*\]", quote)
    return [p.strip() for p in parts if len(p.split()) >= 2]


def quotes_in(text: str) -> list[str]:
    return [a or c for a, c in QUOTE.findall(text or "")]


def ssl_context():
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        if os.environ.get(var) and Path(os.environ[var]).exists():
            return ssl.create_default_context(cafile=os.environ[var])
    return ssl.create_default_context()


def fetch(url: str, refresh: bool) -> str | None:
    """Text of a URL (HTML or PDF), normalized; None if it can't be fetched."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
    if path.exists() and not refresh:
        return normalize(path.read_text(encoding="utf-8"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40, context=ssl_context()) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
    except Exception:
        return None
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        if not shutil.which("pdftotext"):
            return None
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(body)
            f.flush()
            out = subprocess.run(["pdftotext", "-q", f.name, "-"], capture_output=True)
        text = out.stdout.decode("utf-8", "ignore")
    else:
        text = html_to_text(body.decode("utf-8", "ignore"))
    path.write_text(text, encoding="utf-8")   # cache the raw text; matching rules can change
    return normalize(text)


def text_url(url: str) -> str:
    """The plain-text version of a book page, where there is one."""
    m = re.search(r"gutenberg\.org/ebooks/(\d+)", url)
    if m:
        return f"https://www.gutenberg.org/cache/epub/{m.group(1)}/pg{m.group(1)}.txt"
    m = re.search(r"archive\.org/details/([^/?#\s]+)", url)
    if m:
        return f"https://archive.org/download/{m.group(1)}/{m.group(1)}_djvu.txt"
    return url


def urls_for(cite: dict, sources: dict) -> list[str]:
    out = []
    checked = cite.get("checked_in") or ""
    m = GUTENBERG.search(checked)
    if m:
        out.append(text_url(f"gutenberg.org/ebooks/{m.group(1)}"))
    m = ARCHIVE.search(checked)
    if m:
        out.append(text_url(m.group(0)))
    src = sources.get(cite.get("source"), {})
    extra = src.get("text_url") or []
    for url in ([src["url"]] if src.get("url") else []) + ([extra] if isinstance(extra, str) else extra):
        out.append(text_url(url))
    return list(dict.fromkeys(out))


def collect(lists: dict, only: str | None):
    """(where, quote, [urls]) for every quoted phrase in a claim that cites something."""
    for lid, data in lists.items():
        if only and lid != only:
            continue
        for w in data["works"]:
            items = [(f"{lid}:{w['id']} -> {l['work']}", l.get("why"), l) for l in w.get("after") or []]
            if w.get("start_here"):
                items.append((f"{lid}:{w['id']} (start here)", w["start_here"].get("why"), w["start_here"]))
            items += [(f"{lid}:{w['id']} (tip)", t.get("text"), t) for t in w.get("tips") or []]
            for where, text, claim in items:
                for q in quotes_in(text):
                    if fragments(q):
                        yield where, q, claim


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", help="only this list id")
    ap.add_argument("--refresh", action="store_true", help="fetch again instead of using the cache")
    args = ap.parse_args()

    report = b.Report()
    sources = b.load_sources(report)
    lists = b.load_lists(report)
    items = list(collect(lists, args.list))
    sources_by_claim = {id(c): [u for x in c.get("sources") or [] for u in urls_for(x, sources)] for _, _, c in items}
    all_urls = sorted({u for us in sources_by_claim.values() for u in us})
    with ThreadPoolExecutor(max_workers=12) as pool:
        texts = dict(zip(all_urls, pool.map(lambda u: fetch(u, args.refresh), all_urls)))

    known_path = Path(__file__).with_name("recheck_known.yaml")
    known = {(k["where"], k["quote"]) for k in (b.load_yaml(known_path) or [])} if known_path.exists() else set()
    found = missing = unconfirmed = 0
    problems, notes = [], []
    for where, q, claim in items:
        urls = sources_by_claim[id(claim)]
        got = [texts[u] for u in urls if texts.get(u)]
        lost = [f for f in fragments(q) if not any(normalize(f) in t for t in got)]
        if not lost or (where, q) in known:
            found += 1
        elif len(got) < len(urls) or not urls:
            # It may be in a source we couldn't fetch, or one with no URL to fetch.
            unconfirmed += 1
            notes.append(f"UNCONFIRMED  {where}: \"{q}\"")
        else:
            missing += 1
            problems.append(f"MISSING  {where}\n         \"{q}\"\n         not found in: {', '.join(urls)}")

    dead = [u for u in all_urls if not texts.get(u)]
    for p in problems:
        print(p)
    if notes:
        print(f"\n{len(notes)} quote(s) could not be confirmed (a cited source couldn't be fetched, or has no URL):")
        for n in notes:
            print(f"  {n}")
    if dead:
        print(f"\nCould not fetch {len(dead)} source(s) (blocked, moved or offline):")
        for u in dead:
            print(f"  {u}")
    print(f"\n{found} quote(s) found, {missing} missing, {unconfirmed} unconfirmed.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
