#!/usr/bin/env python3
"""The second check: does each cited source actually support its claim?

tools/recheck.py confirms that quoted words still appear in their sources. It can't
tell whether a paraphrase is fair. This tool prepares, for each claim, the passages of
its cited sources most likely to bear on it ("evidence packets"), so a reviewer (so far
Claude, in a separate pass from the one that wrote the claim) can judge it. Verdicts are
recorded in sources/verification.yaml:

  - claim: "hobbes:leviathan -> machiavelli:prince"   # as listed by this tool
    hash: 3f2a9c1e                                     # of the claim text and citations
    verdict: supported        # supported | overstated | unsupported | unclear
    note: optional explanation, required unless supported
    checked: 2026-11
    by: Claude (second AI check)

A verdict only counts while its hash matches: editing a claim or its citations sends it
back for checking. This is still an AI checking AI work; the site shows it separately
from review by a person, and flagged claims are opened as GitHub issues for people.

Usage:
  python tools/verify_claims.py --status              # how many claims are checked
  python tools/verify_claims.py --prepare 40 --out packets.md
                                                      # next 40 unchecked claims, most
                                                      # important first (required links,
                                                      # start-here notes, core books)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import build as b
import recheck

OUT = b.ROOT / "sources" / "verification.yaml"
VERDICTS = ("supported", "overstated", "unsupported", "unclear")
STOP = set("""a an the and or of to in on for with by as at from that this these those is are was
were be been being it its into than then so not no but also which who whom whose what when
where how why his her their them they he she we you our your i me my one ones only more most
very can could would should may might must will shall do does did has have had there here
about after before over under between through during each other such same both all any some
book books work works read reads reading first later early""".split())


def claims(lists: dict):
    """(id, kind, text, citations, priority) for every claim, most important first."""
    out = []
    for lid, d in lists.items():
        for w in d["works"]:
            core = w.get("tier") == "core"
            base = f"{lid}:{w['id']}"
            if w.get("start_here"):
                out.append((f"{base} (start here)", "start_here", w["start_here"].get("why", ""),
                            w["start_here"].get("sources") or [], 1))
            for l in w.get("after") or []:
                rank = {"required": 0, "helpful": 2, "context": 4}[l["strength"]] + (0 if core else 1)
                out.append((f"{base} -> {l['work']}", l["strength"], l.get("why", ""), l.get("sources") or [], rank))
            for i, t in enumerate(w.get("tips") or [], 1):
                out.append((f"{base} (tip {i})", "tip", t.get("text", ""), t.get("sources") or [], 6))
        if d.get("beginner"):
            bg = d["beginner"]
            out.append((f"{lid} (beginner)", "beginner", bg.get("why", ""), bg.get("sources") or [], 1))
    return sorted(out, key=lambda c: (c[4], c[0]))


def claim_hash(text: str, cites: list) -> str:
    key = json.dumps([" ".join(text.split()), [(c.get("source"), c.get("locator")) for c in cites]])
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def load_verdicts() -> dict:
    return {e["claim"]: e for e in (b.load_yaml(OUT) or [])} if OUT.exists() else {}


def current(verdicts: dict, cid: str, h: str) -> dict | None:
    v = verdicts.get(cid)
    return v if v and v.get("hash") == h else None


def raw_text(url: str) -> str | None:
    recheck.fetch(url, refresh=False)          # makes sure it is cached
    path = recheck.CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
    return path.read_text(encoding="utf-8") if path.exists() else None


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zà-ÿ]+", text.lower()) if w not in STOP and len(w) > 2]


def excerpts(text: str, claim_text: str, n: int = 2, width: int = 900) -> list[str]:
    """The n windows of the source that share the most distinctive words with the claim
    (quoted phrases count extra)."""
    flat = re.sub(r"\s+", " ", text)
    targets = set(words(claim_text))
    quoted = [q for q in recheck.quotes_in(claim_text) if len(q.split()) >= 2]
    if not targets:
        return []
    step = width // 3
    scored = []
    low = flat.lower()
    for start in range(0, max(1, len(flat) - width), step):
        win = low[start:start + width]
        ws = set(words(win))
        score = len(targets & ws) + sum(5 for q in quoted if recheck.normalize(q) in recheck.normalize(win))
        scored.append((score, start))
    scored.sort(reverse=True)
    picked: list[int] = []
    for score, start in scored:
        if score == 0 or len(picked) >= n:
            break
        if all(abs(start - p) >= width for p in picked):
            picked.append(start)
    return ["…" + flat[p:p + width].strip() + "…" for p in sorted(picked)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--prepare", type=int, default=0, help="write packets for the next N unchecked claims")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    report = b.Report()
    sources = b.load_sources(report)
    lists = b.load_lists(report)
    verdicts = load_verdicts()
    allc = claims(lists)
    todo = [c for c in allc if not current(verdicts, c[0], claim_hash(c[2], c[3]))]

    if args.status or not args.prepare:
        counts = {}
        for c in allc:
            v = current(verdicts, c[0], claim_hash(c[2], c[3]))
            k = v["verdict"] if v else "not checked"
            counts[k] = counts.get(k, 0) + 1
        print(f"{len(allc)} claims: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        return 0

    out = []
    for cid, kind, text, cites, _ in todo[:args.prepare]:
        out.append(f"## {cid}\n\nkind: {kind} · hash: {claim_hash(text, cites)}\n\n**Claim:** {' '.join(text.split())}\n")
        for c in cites:
            s = sources.get(c.get("source"), {})
            out.append(f"**Source:** {c.get('source')} — {s.get('author', '')}, {s.get('title', '')} "
                       f"(tier {s.get('tier')}) · locator: {c.get('locator', '')} · checked in: {c.get('checked_in', '')}")
            got = False
            for url in recheck.urls_for(c, sources):
                t = raw_text(url)
                if not t:
                    continue
                for e in excerpts(t, text):
                    out.append(f"> {e}")
                    got = True
                break
            if not got:
                out.append("> (no fetchable text; judge from the locator, or mark unclear)")
            out.append("")
    text = "\n".join(out)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(todo[:args.prepare])} packets to {args.out}; {len(todo)} claims unchecked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
