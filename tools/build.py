#!/usr/bin/env python3
"""Validate reading lists and generate reading orders.

Usage:
  python tools/build.py            # validate, then write generated/*.md
  python tools/build.py --check    # validate, and fail if generated/ is out of date
  python tools/build.py --strict   # also fail on unverified citations

How the order is computed:
  - `required` and `helpful` links are hard rules: X always comes before Y.
  - `context` links are soft: they only affect where optional books get placed.
  - The core path orders core works, preferring easier, earlier books when free to choose.
  - A core work with a sourced `start_here` goes first.
  - Non-core works are slotted in around that spine: just before the core book they
    lead into, or (for the author's own books) after the latest core book published
    before them, or right after the core books they depend on.
"""

from __future__ import annotations

import argparse
import heapq
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LISTS_DIR = ROOT / "lists"
SOURCES_FILE = ROOT / "sources" / "sources.yaml"
OUT_DIR = ROOT / "generated"

TIERS = ["core", "extended", "optional"]
KINDS = ["primary", "secondary", "background"]
STRENGTHS = ["required", "helpful", "context"]
HARD = {"required", "helpful"}
STATUSES = ["draft", "reviewed", "stable"]
POSITIONS = ["start", "end"]
SOURCE_TIER_NAMES = {1: "author", 2: "scholarly", 3: "syllabus", 4: "community"}
STRONG_SOURCE_TIERS = {1, 2}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sources(report: Report) -> dict:
    sources = {}
    for s in load_yaml(SOURCES_FILE) or []:
        sid = s.get("id")
        where = f"sources.yaml: {sid or s}"
        if not sid:
            report.error(f"{where}: missing id")
            continue
        if sid in sources:
            report.error(f"{where}: duplicate source id")
        if s.get("tier") not in SOURCE_TIER_NAMES:
            report.error(f"{where}: tier must be one of {sorted(SOURCE_TIER_NAMES)}")
        if not s.get("title"):
            report.error(f"{where}: missing title")
        sources[sid] = s
    return sources


def load_lists(report: Report) -> dict:
    lists = {}
    for path in sorted(LISTS_DIR.glob("*.yaml")):
        data = load_yaml(path) or {}
        lid = data.get("id")
        if lid != path.stem:
            report.error(f"{path.name}: id '{lid}' must match the file name '{path.stem}'")
            lid = path.stem
        lists[lid] = data
    return lists


def resolve(ref: str, list_id: str) -> tuple[str, str]:
    """'genealogy' -> (this list, 'genealogy'); 'nietzsche:genealogy' -> ('nietzsche', 'genealogy')."""
    if ":" in ref:
        lid, wid = ref.split(":", 1)
        return lid, wid
    return list_id, ref


def validate(lists: dict, sources: dict, report: Report, strict: bool) -> None:
    all_ids = {lid: {w.get("id") for w in (d.get("works") or [])} for lid, d in lists.items()}

    for lid, data in lists.items():
        for key in ("title", "scope", "status", "works"):
            if not data.get(key):
                report.error(f"{lid}: missing '{key}'")
        if data.get("status") not in STATUSES:
            report.error(f"{lid}: status must be one of {STATUSES}")
        must_verify = strict or data.get("status") == "stable"

        seen = set()
        works = data.get("works") or []
        by_id = {w.get("id"): w for w in works}
        for w in works:
            wid = w.get("id")
            where = f"{lid}:{wid}"
            if not wid:
                report.error(f"{lid}: a work is missing its id ({w.get('title')})")
                continue
            if wid in seen:
                report.error(f"{where}: duplicate id")
            seen.add(wid)
            if not w.get("title"):
                report.error(f"{where}: missing title")
            if w.get("tier") not in TIERS:
                report.error(f"{where}: tier must be one of {TIERS}")
            if w.get("kind") not in KINDS:
                report.error(f"{where}: kind must be one of {KINDS}")
            d = w.get("difficulty")
            if not isinstance(d, int) or not 1 <= d <= 5:
                report.error(f"{where}: difficulty must be a whole number from 1 to 5")
            if w.get("position") is not None and w.get("position") not in POSITIONS:
                report.error(f"{where}: position must be one of {POSITIONS}")
            if w.get("start_here") is not None:
                sh = w["start_here"]
                if not isinstance(sh, dict) or not (sh.get("why") or "").strip():
                    report.error(f"{where}: start_here needs a 'why'")
                else:
                    check_citations(sh, f"{where} (start_here)", True, sources, report, must_verify)

            for link in w.get("after") or []:
                ref = link.get("work", "")
                lwhere = f"{where} -> {ref}"
                tl, tw = resolve(ref, lid)
                if tl not in all_ids or tw not in all_ids[tl]:
                    report.error(f"{lwhere}: unknown work")
                strength = link.get("strength")
                if strength not in STRENGTHS:
                    report.error(f"{lwhere}: strength must be one of {STRENGTHS}")
                if not (link.get("why") or "").strip():
                    report.error(f"{lwhere}: every link needs a 'why'")
                check_citations(link, lwhere, strength == "required", sources, report, must_verify)

                # The core path must be readable on its own.
                if (
                    w.get("tier") == "core"
                    and strength in HARD
                    and tl == lid
                    and by_id.get(tw, {}).get("tier") not in (None, "core")
                ):
                    report.error(f"{lwhere}: a core work can't depend ('{strength}') on a non-core work")

        cycle = find_cycle(works, lid)
        if cycle:
            report.error(f"{lid}: circular ordering: {' -> '.join(cycle)}")


def check_citations(claim: dict, where: str, needs_strong: bool, sources: dict, report: Report, must_verify: bool) -> None:
    cites = claim.get("sources") or []
    if not cites:
        report.error(f"{where}: needs at least one source")
    tiers = []
    for c in cites:
        sid = c.get("source")
        if sid not in sources:
            report.error(f"{where}: unknown source '{sid}' (add it to sources/sources.yaml)")
            continue
        tiers.append(sources[sid].get("tier"))
        if c.get("verified") and not (c.get("checked_in") or "").strip():
            report.error(f"{where}: verified citation '{sid}' must say which edition it was checked in ('checked_in')")
        if not c.get("verified"):
            msg = f"{where}: citation '{sid}' not yet verified"
            (report.error if must_verify else report.warn)(msg)
    if needs_strong and not STRONG_SOURCE_TIERS & set(tiers):
        report.error(f"{where}: needs an author (tier 1) or scholarly (tier 2) source")


def hard_edges(works: list, list_id: str):
    """Yield (before, after) pairs within this list for required/helpful links."""
    for w in works:
        for link in w.get("after") or []:
            tl, tw = resolve(link.get("work", ""), list_id)
            if tl == list_id and link.get("strength") in HARD:
                yield tw, w["id"]


def all_edges(works: list, list_id: str):
    for w in works:
        for link in w.get("after") or []:
            tl, tw = resolve(link.get("work", ""), list_id)
            if tl == list_id:
                yield tw, w["id"]


def find_cycle(works: list, list_id: str) -> list | None:
    succ: dict[str, list] = {w.get("id"): [] for w in works}
    for a, b in hard_edges(works, list_id):
        succ.setdefault(a, []).append(b)
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(n):
        state[n] = 1
        stack.append(n)
        for m in succ.get(n, []):
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if m not in state:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        state[n] = 2
        return None

    for n in succ:
        if n not in state:
            found = visit(n)
            if found:
                return found
    return None


def topo(nodes: list[str], edges: list[tuple[str, str]], key) -> list[str]:
    nodeset = set(nodes)
    indeg = {n: 0 for n in nodes}
    succ: dict[str, list] = {n: [] for n in nodes}
    for a, b in edges:
        if a in nodeset and b in nodeset:
            succ[a].append(b)
            indeg[b] += 1
    heap = [(key(n), n) for n in nodes if indeg[n] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        _, n = heapq.heappop(heap)
        out.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(heap, (key(m), m))
    return out


def reachable(start: str, succ: dict) -> set:
    seen, todo = set(), [start]
    while todo:
        for m in succ.get(todo.pop(), []):
            if m not in seen:
                seen.add(m)
                todo.append(m)
    return seen


def compute_order(data: dict) -> tuple[list[str], list[str]]:
    lid = data["id"]
    works = data["works"]
    by_id = {w["id"]: w for w in works}
    hard = list(hard_edges(works, lid))
    soft = list(all_edges(works, lid))
    INF = float("inf")

    def year(w):
        return w.get("year") or 9999

    # Core spine. Hard constraints between core works include those that pass through other works.
    hard_succ: dict[str, list] = {}
    for a, b in hard:
        hard_succ.setdefault(a, []).append(b)
    core = [w["id"] for w in works if w["tier"] == "core"]
    core_set = set(core)
    core_edges = [(a, b) for a in core for b in reachable(a, hard_succ) if b in core_set]
    core_order = topo(
        core,
        core_edges,
        key=lambda n: (0 if by_id[n].get("start_here") else 1, by_id[n]["difficulty"], year(by_id[n])),
    )
    pos = {n: i for i, n in enumerate(core_order)}

    # Where each non-core work fits relative to the spine.
    any_succ: dict[str, list] = {}
    any_pred: dict[str, list] = {}
    for a, b in soft:
        any_succ.setdefault(a, []).append(b)
        any_pred.setdefault(b, []).append(a)
    memo: dict[str, float] = {}
    starts_with_entry = bool(core_order) and bool(by_id[core_order[0]].get("start_here"))

    def prio(n: str, visiting=frozenset()) -> float:
        if n in pos:
            return pos[n]
        if n in memo:
            return memo[n]
        w = by_id[n]
        p = None
        if w.get("position") == "start":
            p = -1.0
        elif w.get("position") == "end":
            p = INF
        if p is None:
            leads_to = [pos[m] for m in reachable(n, any_succ) if m in pos]
            if leads_to:
                p = min(leads_to) - 0.5
        if p is None and w["kind"] == "primary" and w.get("year"):
            # The author's own books: right after the latest core book published before it.
            earlier = [pos[c] for c in core if year(by_id[c]) < w["year"]]
            p = max(earlier) + 0.5 if earlier else -0.5
        if p is None:
            # Prefer the core works it directly builds on; fall back to indirect ones.
            builds_on = [pos[m] for m in any_pred.get(n, []) if m in pos]
            builds_on = builds_on or [pos[m] for m in reachable(n, any_pred) if m in pos]
            if builds_on:
                p = max(builds_on) + 0.5
        if p is None:
            nxt = [prio(m, visiting | {n}) for m in any_succ.get(n, []) if m not in visiting]
            nxt = [x for x in nxt if x != INF]
            p = min(nxt) - 0.1 if nxt else INF
        # A sourced "start here" book stays first; only pinned works go before it.
        if starts_with_entry and p < 0.5 and w.get("position") != "start":
            p = 0.5
        memo[n] = p
        return p

    def sort_year(n: str) -> int:
        # Undated background works sort with the earliest book that uses them.
        w = by_id[n]
        if w.get("year"):
            return w["year"]
        return min((year(by_id[m]) for m in any_succ.get(n, [])), default=9999)

    tier_rank = {t: i for i, t in enumerate(TIERS)}
    full_order = topo(
        [w["id"] for w in works],
        hard,
        key=lambda n: (prio(n), sort_year(n), tier_rank[by_id[n]["tier"]], by_id[n]["difficulty"]),
    )
    return core_order, full_order


# ---------- Rendering ----------

def stars(d: int) -> str:
    return "●" * d + "○" * (5 - d)


def cite(c: dict, sources: dict) -> str:
    s = sources[c["source"]]
    text = f"{s.get('author', '')}, *{s['title']}*".lstrip(", ")
    if c.get("locator"):
        text += f", {c['locator']}"
    text += f" [{SOURCE_TIER_NAMES[s['tier']]}]"
    if c.get("verified"):
        text += f" ✓ checked in {c['checked_in']}"
    else:
        text += " ⚠️ unverified"
    return text


def render(data: dict, lists: dict, sources: dict) -> str:
    lid = data["id"]
    by_id = {w["id"]: w for w in data["works"]}
    core_order, full_order = compute_order(data)

    def label(ref: str) -> str:
        tl, tw = resolve(ref, lid)
        w = next(x for x in lists[tl]["works"] if x["id"] == tw)
        return f"*{w['title']}*" + ("" if tl == lid else f" (from the {lists[tl]['title']} list)")

    claims = [l for w in data["works"] for l in (w.get("after") or [])]
    claims += [w["start_here"] for w in data["works"] if w.get("start_here")]
    cites = [c for l in claims for c in (l.get("sources") or [])]
    verified = sum(1 for c in cites if c.get("verified"))

    out = [
        f"<!-- Generated by tools/build.py from lists/{lid}.yaml. Do not edit by hand. -->",
        f"# {data['title']}: reading order",
        "",
        f"**Status:** {data['status']} · **Citations checked:** {verified}/{len(cites)}",
        "",
        f"**Scope:** {data['scope'].strip()}",
        "",
    ]
    if verified < len(cites):
        out += [
            "> ⚠️ Some citations haven't been checked against the actual text yet. "
            "See [CONTRIBUTING.md](../CONTRIBUTING.md) to help verify them.",
            "",
        ]

    out += ["## Core path", "", "The shortest route through the essentials.", ""]
    for i, n in enumerate(core_order, 1):
        w = by_id[n]
        star = " · ★ start here" if w.get("start_here") else ""
        out.append(f"{i}. **{w['title']}** ({w.get('year', '')}) · difficulty {stars(w['difficulty'])}{star}")
    out.append("")

    out += [
        "## Full path",
        "",
        "Every work, in order. Extended and optional works are placed where they fit best.",
        "",
    ]
    for i, n in enumerate(full_order, 1):
        w = by_id[n]
        meta = [w["tier"], w["kind"], f"difficulty {stars(w['difficulty'])}"]
        byline = f" · {w['author']}" if w.get("author") else ""
        yr = f" ({w['year']})" if w.get("year") else ""
        out.append(f"### {i}. {w['title']}{yr}")
        out.append("")
        out.append(f"`{' · '.join(meta)}`{byline}")
        out.append("")
        if w.get("note"):
            out += [w["note"].strip(), ""]
        if w.get("translation"):
            out += [f"**Translation:** {w['translation']}", ""]
        if w.get("start_here"):
            out += [f"**★ Good place to start.** {w['start_here']['why'].strip()}", ""]
            out += [f"- {cite(c, sources)}" for c in w["start_here"].get("sources") or []]
            out.append("")
        if w.get("after"):
            out.append("**Read first:**")
            out.append("")
            for l in w["after"]:
                out.append(f"- {label(l['work'])} — *{l['strength']}*. {l['why'].strip()}")
                for c in l.get("sources") or []:
                    out.append(f"  - {cite(c, sources)}")
            out.append("")

    out += ["## Map", "", "Solid arrows: required or helpful. Dotted: context.", "", "```mermaid", "graph TD"]
    style = {"core": ":::core", "extended": ":::extended", "optional": ":::optional"}
    for n in full_order:
        w = by_id[n]
        title = w["title"].replace('"', "'")
        out.append(f'  {n.replace("-", "_")}["{title}"]{style[w["tier"]]}')
    for w in data["works"]:
        for l in w.get("after") or []:
            tl, tw = resolve(l["work"], lid)
            if tl != lid:
                continue
            arrow = "-.->" if l["strength"] == "context" else "-->"
            out.append(f'  {tw.replace("-", "_")} {arrow} {w["id"].replace("-", "_")}')
    out += [
        "  classDef core fill:#f4d58d,stroke:#8a6d1f,color:#000",
        "  classDef extended fill:#cfe3f5,stroke:#3b6a91,color:#000",
        "  classDef optional fill:#eeeeee,stroke:#888,color:#000",
        "```",
        "",
    ]

    used = sorted({c["source"] for c in cites}, key=lambda s: (sources[s]["tier"], s))
    out += ["## Sources", ""]
    for sid in used:
        s = sources[sid]
        bits = [x for x in (s.get("author"), f"*{s['title']}*", s.get("publisher"), str(s.get("year", ""))) if x]
        line = f"- **[{SOURCE_TIER_NAMES[s['tier']]}]** {', '.join(bits)}"
        if s.get("url"):
            line += f" — <{s['url']}>"
        out.append(line)
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if generated/ is out of date")
    ap.add_argument("--strict", action="store_true", help="treat unverified citations as errors")
    args = ap.parse_args()

    report = Report()
    sources = load_sources(report)
    lists = load_lists(report)
    validate(lists, sources, report, args.strict)

    for w in report.warnings:
        print(f"warning: {w}")
    for e in report.errors:
        print(f"ERROR: {e}")
    if report.errors:
        print(f"\n{len(report.errors)} error(s).")
        return 1

    stale = []
    OUT_DIR.mkdir(exist_ok=True)
    for lid, data in lists.items():
        text = render(data, lists, sources)
        path = OUT_DIR / f"{lid}.md"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")

    if stale:
        print(f"ERROR: out of date: {', '.join(stale)}. Run `python tools/build.py` and commit the result.")
        return 1
    print(f"OK: {len(lists)} list(s), {len(report.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
