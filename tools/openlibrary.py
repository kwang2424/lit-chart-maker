#!/usr/bin/env python3
"""Match each book to its Open Library work, for the site's "Find it" links.

The site checks Open Library (read free / borrow online) from the reader's browser, so it
needs each book's Open Library work id. A title search in the browser can land on the
wrong book (a commentary, or the original-language edition), so the matches are made
here, written to sources/openlibrary.yaml, and reviewed like any other data.

Usage:
  python tools/openlibrary.py            # match books that have no entry yet
  python tools/openlibrary.py --all      # re-match everything (keeps manual entries)

Each entry: `work` (list:work), `ol` (Open Library work id, or null if none fits),
`ol_title` and `ol_author` (what was matched, for review), and `checked: true` once a
person or a manual edit has confirmed it; the script never overwrites checked entries.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

import yaml

import build as b

OUT = b.ROOT / "sources" / "openlibrary.yaml"
API = "https://openlibrary.org/search.json"
UA = "reading-order-maker (https://github.com/kwang2424/lit-chart-maker)"


def plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"^(the|a|an) ", "", text)


def title_match(ours: str, theirs: str) -> float:
    """1.0 for the same title; also counts 'Symposium' within 'Symposium and Other Dialogues'."""
    a, b_ = plain(ours), plain(main_title(theirs))
    sim = difflib.SequenceMatcher(None, a, b_).ratio()
    if a and (b_.startswith(a + " ") or b_.endswith(" " + a) or f" {a} " in f" {b_} "):
        sim = max(sim, 0.9)
    return sim


def main_title(title: str) -> str:
    """'Either/Or: A Fragment of Life' -> 'Either/Or'; drops quotes and bracketed notes."""
    t = re.sub(r"\([^)]*\)", "", title).strip().strip('"\'“”')
    t = re.split(r":\s", t)[0]
    return t.strip().strip('"\'“”')


def surname(author: str) -> str:
    a = re.sub(r"\([^)]*\)", "", author or "")
    a = re.split(r",| and | & ", a)[0].strip()
    return a.split()[-1] if a else ""


def search(title: str, last: str, english: bool = False) -> list[dict]:
    q = f'title:"{title}"' + (f" author:{last}" if last else "") + (" language:eng" if english else "")
    url = API + "?" + urllib.parse.urlencode({
        "q": q, "limit": 10,
        "fields": "key,title,author_name,first_publish_year,edition_count,ebook_access,language",
    })
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r).get("docs", [])
        except Exception:
            time.sleep(2 * (attempt + 1))
    return []


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def english_edition_titles(work_key: str) -> list[str]:
    d = get(f"https://openlibrary.org{work_key}/editions.json?limit=200")
    return [e.get("title", "") for e in d.get("entries", [])
            if any(l.get("key") == "/languages/eng" for l in e.get("languages") or [])]


def best_main_record(title: str, last: str) -> dict | None:
    """Open Library files many classics under the original-language title (Plato's
    Symposium is "Συμπόσιον"), and that main record holds most English editions. A plain
    search ranks those records first; accept one if it has an English edition with our title."""
    d = get(API + "?" + urllib.parse.urlencode({
        "q": f"{title} {last}".strip(), "limit": 10,
        "fields": "key,title,author_name,edition_count,ebook_access,language"}))
    docs = [x for x in d.get("docs", []) if not last or plain(last) in plain(" ".join(x.get("author_name") or []))]
    docs.sort(key=lambda x: -(x.get("edition_count") or 0))
    for x in docs[:4]:
        if title_match(title, x.get("title", "")) >= 0.85 and "eng" in (x.get("language") or []):
            return x
        if any(title_match(title, t) >= 0.85 for t in english_edition_titles(x["key"])):
            return x
    return None


def best(work: dict) -> dict:
    title, last = main_title(work["title"]), surname(work.get("author", ""))
    main = best_main_record(title, last)
    if main:
        return {"ol": main["key"].split("/")[-1], "ol_title": main.get("title"),
                "ol_author": (main.get("author_name") or [""])[0],
                "note": None if title_match(title, main.get("title", "")) >= 0.85 else "matched via an English edition"}
    docs = search(title, last) + search(title, last, english=True)
    scored = []
    for d in docs:
        names = " ".join(d.get("author_name") or [])
        if last and plain(last) not in plain(names):
            continue
        sim = title_match(title, d.get("title", ""))
        english = "eng" in (d.get("language") or [])
        scored.append((sim >= 0.85, english, sim, d.get("edition_count") or 0, d))
    if not scored:
        return {"ol": None, "note": "no match"}
    scored.sort(key=lambda x: x[:4], reverse=True)
    good, english, sim, _, d = scored[0]
    return {
        "ol": d["key"].split("/")[-1] if good else None,
        "ol_title": d.get("title"),
        "ol_author": (d.get("author_name") or [""])[0],
        "note": None if good and english else ("weak title match" if not good else "no English edition listed"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    lists = b.load_lists(b.Report())
    old = {e["work"]: e for e in (b.load_yaml(OUT) or [])} if OUT.exists() else {}
    out = []
    for lid in sorted(lists):
        for w in lists[lid]["works"]:
            key = f"{lid}:{w['id']}"
            if key in old and (old[key].get("checked") or not args.all):
                out.append(old[key])
                continue
            m = best(w)
            entry = {"work": key, "ol": m["ol"]}
            for k in ("ol_title", "ol_author", "note"):
                if m.get(k):
                    entry[k] = m[k]
            out.append(entry)
            print(f"{key:45} {entry['ol'] or '-':14} {m.get('ol_title') or ''} {('[' + m['note'] + ']') if m.get('note') else ''}")
            time.sleep(0.4)
    header = ("# Open Library work ids for the site's \"Find it\" links. Generated by tools/openlibrary.py,\n"
              "# then reviewed: fix a wrong `ol`, set it to null if no edition fits, and add `checked: true`.\n\n")
    OUT.write_text(header + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"wrote {OUT.relative_to(b.ROOT)} ({len(out)} books)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
