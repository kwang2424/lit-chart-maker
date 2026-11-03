"""Survey of what independent sources recommend, and the consensus it implies.

Each list can have a `survey:` section. Every entry is one source (a syllabus,
the author's own advice, an encyclopedia, a guide) and records what it says:

  survey:
    - source: syl-bard-pl320          # id in sources/sources.yaml
      starts_with: birth-of-tragedy  # optional: the first book it has you read
      includes: [birth-of-tragedy, gay-science, ...]   # books it assigns/recommends
      ordered: true                  # true if `includes` is in its reading order
      covers: beginning              # optional: a beginner's list; counts toward starts only
      locator: course schedule
      verified: true
      checked_in: syllabus PDF, Fall 2025

From these we compute, per book, how many sources include it and how many
start with it, and we check our tiers and links against that consensus.
"""

from __future__ import annotations

from html import escape

CORE_SHARE = 0.75   # included by at least this share of sources -> should probably be core
WEAK_SHARE = 0.34   # core works included by fewer than this share get a warning
MIN_SOURCES = 4     # don't second-guess tiers with fewer sources than this
DISAGREE_SHARE = 0.75  # a hard link that this share of ordered sources reverse gets a warning


def validate(data: dict, sources: dict, report, must_verify: bool, check_citations) -> None:
    lid = data["id"]
    ids = {w["id"] for w in data.get("works") or []}
    seen = set()
    for i, s in enumerate(data.get("survey") or []):
        where = f"{lid}: survey entry {i + 1} ({s.get('source')})"
        sid = s.get("source")
        if sid in seen:
            report.error(f"{where}: the same source is surveyed twice")
        seen.add(sid)
        inc = s.get("includes") or []
        if not inc:
            report.error(f"{where}: needs 'includes' (the books it recommends)")
        for w in inc:
            if w not in ids:
                report.error(f"{where}: unknown work '{w}'")
        if s.get("covers", "full") not in ("full", "beginning"):
            report.error(f"{where}: covers must be 'full' or 'beginning'")
        if len(set(inc)) != len(inc):
            report.error(f"{where}: a work is listed twice in 'includes'")
        st = s.get("starts_with")
        if st is not None and st not in inc:
            report.error(f"{where}: starts_with '{st}' must also be in 'includes'")
        # Reuse the citation rules: the survey entry is itself a citation.
        claim = {"sources": [{k: s.get(k) for k in ("source", "locator", "verified", "checked_in")}]}
        check_citations(claim, where, False, sources, report, must_verify)

    stats = compute(data)
    if stats["n"] >= MIN_SOURCES:
        by_id = {w["id"]: w for w in data["works"]}
        for wid, st in stats["works"].items():
            if wid not in by_id:  # already reported as an unknown work
                continue
            tier = by_id[wid]["tier"]
            if by_id[wid].get("tier_note"):
                continue
            if st["share"] >= CORE_SHARE and tier != "core":
                report.warn(f"{lid}:{wid}: included by {st['count']}/{stats['n']} surveyed sources but tier is '{tier}'")
        for w in data["works"]:
            if w.get("tier_note"):
                continue
            if w["tier"] == "core" and stats["works"].get(w["id"], {}).get("share", 0) < WEAK_SHARE:
                report.warn(f"{lid}:{w['id']}: core, but few surveyed sources include it")
        for a, b, agree, total in disagreements(data):
            report.warn(f"{lid}: link {a} -> {b} is reversed by {total - agree}/{total} ordered sources")


def full_lists(data: dict) -> list:
    """Survey entries that cover a whole course of reading (not just where to begin)."""
    return [s for s in data.get("survey") or [] if s.get("covers", "full") == "full"]


def compute(data: dict) -> dict:
    survey = data.get("survey") or []
    full = full_lists(data)
    n = len(full)
    works: dict[str, dict] = {}
    for s in full:
        for w in s.get("includes") or []:
            works.setdefault(w, {"count": 0, "starts": 0, "mentions": 0})["count"] += 1
    for s in survey:
        for w in s.get("includes") or []:
            works.setdefault(w, {"count": 0, "starts": 0, "mentions": 0})["mentions"] += 1
        if s.get("starts_with"):
            works.setdefault(s["starts_with"], {"count": 0, "starts": 0, "mentions": 0})["starts"] += 1
    for st in works.values():
        st["share"] = st["count"] / n if n else 0
    return {"n": n, "n_all": len(survey), "works": works}


def pair_order(data: dict, a: str, b: str) -> tuple[int, int]:
    """Among ordered sources that include both, how many put a before b."""
    agree = total = 0
    for s in data.get("survey") or []:
        inc = s.get("includes") or []
        if s.get("ordered") and a in inc and b in inc:
            total += 1
            agree += inc.index(a) < inc.index(b)
    return agree, total


def disagreements(data: dict):
    lid = data["id"]
    for w in data["works"]:
        for l in w.get("after") or []:
            if ":" in l["work"] or l.get("strength") not in ("required", "helpful"):
                continue
            agree, total = pair_order(data, l["work"], w["id"])
            if total >= 3 and (total - agree) / total >= DISAGREE_SHARE:
                yield l["work"], w["id"], agree, total


def ranked(data: dict) -> list[tuple[str, dict]]:
    stats = compute(data)
    return sorted(stats["works"].items(),
                  key=lambda kv: (-kv[1]["mentions"], -kv[1]["starts"], -kv[1]["count"], kv[0]))


def source_label(sid: str, sources: dict) -> str:
    s = sources[sid]
    return f"{s['author']}, {s['title']}" if s.get("author") else s["title"]


KIND_NAMES = {1: ("statement by the author", "statements by the author"),
              2: ("scholarly guide", "scholarly guides"),
              3: ("course or teaching list", "course syllabi and teaching lists"),
              4: ("community list", "community lists")}


def describe(data: dict, sources: dict) -> str:
    counts: dict[int, int] = {}
    for s in data.get("survey") or []:
        t = sources[s["source"]]["tier"]
        counts[t] = counts.get(t, 0) + 1
    parts = [f"{n} {KIND_NAMES[t][n != 1]}" for t, n in sorted(counts.items())]
    return ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]


def render_md(data: dict, sources: dict, tier_names: dict) -> list[str]:
    survey = data.get("survey") or []
    if not survey:
        return []
    by_id = {w["id"]: w for w in data["works"]}
    stats = compute(data)
    n = stats["n_all"]
    out = [
        "## What the sources say",
        "",
        f"We surveyed {n} independent sources ({describe(data, sources)}) and recorded "
        "which books each one assigns or recommends, and where it starts.",
        "",
        "| Book | Recommended by | First book in |",
        "|---|---|---|",
    ]
    m = stats["n_all"]
    for wid, st in ranked(data):
        out.append(f"| {by_id[wid]['title']} | {st['mentions']}/{m} | {st['starts'] or ''} |")
    out += ["", "**Sources surveyed**", ""]
    for s in survey:
        src = sources[s["source"]]
        seq = " → ".join(by_id[w]["title"] for w in s["includes"]) if s.get("ordered") else \
            ", ".join(by_id[w]["title"] for w in s["includes"])
        mark = f"✓ checked in {s['checked_in']}" if s.get("verified") else "⚠️ unverified"
        kind = " (beginner's list)" if s.get("covers") == "beginning" else ""
        out.append(f"- **{source_label(s['source'], sources)}** [{tier_names[src['tier']]}]{kind}: {seq}. {mark}")
    out.append("")
    return out


def render_html(data: dict, sources: dict, tier_names: dict) -> str:
    survey = data.get("survey") or []
    if not survey:
        return ""
    by_id = {w["id"]: w for w in data["works"]}
    stats = compute(data)
    n = stats["n_all"]
    rows = []
    m = stats["n_all"]
    for wid, st in ranked(data):
        pct = round(100 * st["mentions"] / m)
        start = f' <span class="badge">first book in {st["starts"]}</span>' if st["starts"] else ""
        rows.append(
            f'<li><a href="#{wid}">{escape(by_id[wid]["title"])}</a>{start}'
            f'<div class="bar" aria-label="{st["mentions"]} of {m}"><span style="width:{pct}%"></span></div>'
            f'<span class="sans meta muted">recommended by {st["mentions"]}/{m} sources</span></li>'
        )
    srcs = []
    for s in survey:
        src = sources[s["source"]]
        title = escape(source_label(s["source"], sources))
        if src.get("url"):
            title = f'<a href="{escape(src["url"])}">{title}</a>'
        joiner = " → " if s.get("ordered") else ", "
        kind = " (beginner's list)" if s.get("covers") == "beginning" else ""
        seq = joiner.join(escape(by_id[w]["title"]) for w in s["includes"])
        mark = (f'<span class="ok">✓ checked in {escape(s["checked_in"])}</span>' if s.get("verified")
                else '<span class="warn">⚠ not yet verified</span>')
        srcs.append(f'<li><strong>{title}</strong> <span class="muted">[{tier_names[src["tier"]]}]{kind}</span><br>'
                    f'<span class="meta">{seq}</span><br><span class="meta">{mark}</span></li>')
    return (
        "<h2>What the sources say</h2>"
        f"<p>We surveyed {n} independent sources ({escape(describe(data, sources))}) and recorded which books "
        "each assigns or recommends, and where it starts. Bars show how many include each book.</p>"
        f'<ul class="consensus">{"".join(rows)}</ul>'
        f'<details class="src"><summary>{n} sources surveyed</summary><ul class="cites">{"".join(srcs)}</ul></details>'
    )


def positions(data: dict) -> dict[str, float]:
    """Average relative position (0 = first, 1 = last) of each book across ordered sources."""
    acc: dict[str, list] = {}
    for s in data.get("survey") or []:
        inc = s.get("includes") or []
        if s.get("ordered") and len(inc) > 1:
            for i, w in enumerate(inc):
                acc.setdefault(w, []).append(i / (len(inc) - 1))
    # One course is too noisy to move a book; require at least two.
    return {w: sum(v) / len(v) for w, v in acc.items() if len(v) >= 2}
