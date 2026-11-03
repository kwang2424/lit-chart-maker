"""Audit the evidence behind every list: sources used per tier, survey size, and weak spots.

Usage: python -I .claude/skills/build-reading-list/scripts/source_inventory.py   (run from the repo root)

Flags: survey sources with no year in their title (age unknown), older than 15 years,
or from non-university bodies (adult education, private institutes, beginner sites).
"""
import collections, glob, re
import yaml

NONUNIV = ("osher", "olli-dc", "lifelong learning", "brooklyn institute", "melbourne school", "jung society",
           "jungian center", "senior college", "hackett")
src = {s["id"]: s for s in yaml.safe_load(open("sources/sources.yaml"))}
print(f"{'list':13} {'t1':>3} {'t2':>3} {'t3':>3} {'survey':>6}  flags")
for path in sorted(glob.glob("lists/*.yaml")):
    d = yaml.safe_load(open(path))
    ids = set()
    for w in d["works"]:
        claims = (w.get("after") or []) + (w.get("tips") or []) + ([w["start_here"]] if w.get("start_here") else [])
        ids |= {c["source"] for cl in claims for c in cl.get("sources") or []}
    survey = [s["source"] for s in d.get("survey") or []]
    tiers = collections.Counter(src[i]["tier"] for i in ids | set(survey))
    flags = []
    for sid in survey:
        text = f"{src[sid].get('author', '')} {src[sid]['title']}".lower()
        year = re.search(r"(19|20)\d\d", text)
        if any(m in text for m in NONUNIV):
            flags.append(f"{sid}:non-university")
        elif not year:
            flags.append(f"{sid}:undated")
        elif int(year.group()) < 2011:
            flags.append(f"{sid}:{year.group()}")
    if len(survey) < 4:
        flags.insert(0, f"THIN({len(survey)})")
    print(f"{d['id']:13} {tiers[1]:>3} {tiers[2]:>3} {tiers[3]:>3} {len(survey):>6}  {' '.join(flags)}")
