"""Topic charts: what well-known courses on a topic assign, in an order the sources support.

A topic (topics/<id>.yaml) lists the courses it is built from and which books on this
site each assigns (`includes`, as list:work), plus what else they assign that isn't on
the site yet (`others`, plain text). The chart is every book any course assigns:
  - core: assigned by at least half the courses; also read: the rest;
  - in an order that respects every sourced link between them (the same links as the
    reading plans), with earlier thinkers, then earlier books, first where no link decides.

  id: existentialism
  title: Existentialism
  scope: >
    One or two sentences on what the topic covers.
  courses:
    - source: syl-bard-colony          # id in sources/sources.yaml
      includes: [kierkegaard:fear-trembling, sartre:humanism]
      others: [Camus, The Stranger]
      locator: schedule
      verified: true
      checked_in: Course syllabus (PDF, Spring 2024), accessed 2026-11
"""

from __future__ import annotations

import heapq
from html import escape
from pathlib import Path

import build as b
import connections
import findit

TOPICS_DIR = b.ROOT / "topics"
FIELDS = {"topic": {"id", "title", "scope", "courses"},
          "course": {"source", "includes", "others", "locator", "verified", "checked_in", "reviewed_by"}}


def load() -> dict:
    out = {}
    for path in sorted(TOPICS_DIR.glob("*.yaml")):
        data = b.load_yaml(path) or {}
        out[data.get("id") or path.stem] = data
    return out


def validate(topics: dict, lists: dict, sources: dict, report) -> None:
    books = {f"{lid}:{w['id']}" for lid, d in lists.items() for w in d["works"]}
    for tid, t in topics.items():
        where = f"topics/{tid}.yaml"
        unknown = set(t) - FIELDS["topic"]
        if unknown:
            report.error(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
        for key in ("title", "scope", "courses"):
            if not t.get(key):
                report.error(f"{where}: missing '{key}'")
        seen = set()
        for i, c in enumerate(t.get("courses") or [], 1):
            cw = f"{where}: course {i} ({c.get('source')})"
            if set(c) - FIELDS["course"]:
                report.error(f"{cw}: unknown field(s) {', '.join(sorted(set(c) - FIELDS['course']))}")
            if c.get("source") in seen:
                report.error(f"{cw}: the same course is listed twice")
            seen.add(c.get("source"))
            if not c.get("includes"):
                report.error(f"{cw}: needs 'includes'")
            for ref in c.get("includes") or []:
                if ref not in books:
                    report.error(f"{cw}: unknown book '{ref}' (use list:work)")
            b.check_citations({"sources": [{k: c[k] for k in ("source", "locator", "verified", "checked_in", "reviewed_by") if k in c}]},
                              cw, False, sources, report, False)


def chart(topic: dict, lists: dict) -> dict:
    """Books with course counts, in reading order, plus the links between them."""
    courses = topic.get("courses") or []
    n = len(courses)
    count: dict[str, int] = {}
    for c in courses:
        for ref in c.get("includes") or []:
            count[ref] = count.get(ref, 0) + 1
    books = set(count)
    rank = {lid: i for i, lid in enumerate(connections.ordered_lists(lists))}
    works = {f"{lid}:{w['id']}": (lid, w) for lid, d in lists.items() for w in d["works"]}
    links = [(a, c, s, why) for a, c, s, why in edges(lists) if a in books and c in books]
    succ: dict[str, list] = {x: [] for x in books}
    indeg = {x: 0 for x in books}
    for a, c, _, _ in links:
        succ[a].append(c)
        indeg[c] += 1

    def key(x):
        lid, w = works[x]
        return (rank[lid], w.get("year") or 9999, w["title"])

    heap = [(key(x), x) for x in books if not indeg[x]]
    heapq.heapify(heap)
    order = []
    while heap:
        _, x = heapq.heappop(heap)
        order.append(x)
        for y in succ[x]:
            indeg[y] -= 1
            if not indeg[y]:
                heapq.heappush(heap, (key(y), y))
    core = {x for x in books if count[x] * 2 >= n}
    others: dict[str, int] = {}
    for c in courses:
        for o in c.get("others") or []:
            others[o] = others.get(o, 0) + 1
    return {"order": order, "count": count, "n": n, "core": core, "links": links, "works": works, "others": others}


def edges(lists: dict):
    for lid, d in lists.items():
        for w in d["works"]:
            for l in w.get("after") or []:
                tl, tw = b.resolve(l["work"], lid)
                yield f"{tl}:{tw}", f"{lid}:{w['id']}", l["strength"], " ".join(l["why"].split())


def page_body(tid: str, topic: dict, lists: dict, sources: dict) -> str:
    c = chart(topic, lists)
    ol = findit.load_ol()
    pages = findit.load_pages()
    core_goals = ",".join(x for x in c["order"] if x in c["core"])
    h = [f"<h1>{escape(topic['title'])}</h1>",
         f'<p class="sans meta muted"><span class="badge">topic</span>{len(c["order"])} books on this site · '
         f'built from {c["n"]} courses</p>',
         f"<p>{escape(' '.join(topic['scope'].split()))}</p>",
         '<p class="meta">Books that at least half the courses assign are marked <strong>core</strong>. The order '
         "follows the sourced links between these books (the same links as each thinker's page); where no link "
         "decides, earlier thinkers come first.</p>",
         reading_time([x for x in c["order"] if x in c["core"]], c["order"], pages),
         f'<p class="sans"><a href="plan.html#goals={escape(core_goals)}&min=context">Make the core books a reading plan →</a></p>',
         '<ol class="plan">']
    for i, x in enumerate(c["order"], 1):
        lid, w = c["works"][x]
        into = [(a, s, why) for a, y, s, why in c["links"] if y == x]
        why = "".join(
            f'<li><span class="strength">{escape(s)}</span> after <a href="{a.split(":")[0]}.html#{a.split(":")[1]}">'
            f'<em>{escape(c["works"][a][1]["title"])}</em></a><br><span class="meta">{escape(t)}</span></li>'
            for a, s, t in into)
        core = x in c["core"]
        h.append(
            f'<li class="pitem{" goal" if core else ""}"><span class="pnum sans">{i}</span>'
            f'<a class="ptitle" href="{lid}.html#{w["id"]}">{escape(w["title"])}</a>'
            f'<div class="sans meta muted">{escape(lists[lid]["title"])}{" · " + str(w["year"]) if w.get("year") else ""}'
            f'{" · ~" + str(pages[x]) + " pp." if pages.get(x) else ""}'
            f' · assigned by {c["count"][x]} of {c["n"]} courses{" · <strong>core</strong>" if core else ""}</div>'
            + (f'<details class="src"><summary>Why here ({len(into)})</summary><ul class="links">{why}</ul></details>' if into else "")
            + findit.static_html(x, findit.entry(lid, w, ol)) + "</li>")
    h.append("</ol>")
    if c["others"]:
        items = "".join(f"<li>{escape(o)}{f' <span class=muted>({k} courses)</span>' if k > 1 else ''}</li>"
                        for o, k in sorted(c["others"].items(), key=lambda kv: (-kv[1], kv[0])))
        h.append("<h2>Also read in these courses (not yet on this site)</h2>"
                 f'<ul class="links">{items}</ul>')
    rows = []
    for course in topic["courses"]:
        s = sources[course["source"]]
        title = escape(f"{s.get('author', '')}, {s['title']}".lstrip(", "))
        if s.get("url"):
            title = f'<a href="{escape(s["url"])}">{title}</a>'
        books = ", ".join(escape(c["works"][r][1]["title"]) for r in course["includes"])
        rows.append(f"<li><strong>{title}</strong><br><span class=\"meta\">{books}</span><br>"
                    f'<span class="meta muted">{escape(course.get("locator", ""))}</span></li>')
    h.append(f'<h2>Courses</h2><ul class="cites">{"".join(rows)}</ul>')
    h.append('<script src="find.js"></script>')
    return "\n".join(h)


def weeks(pages: int, pace: int = 20) -> str:
    days = -(-pages // pace)
    return f"{days} days" if days < 14 else f"{round(days / 7)} weeks" if days < 70 else f"{round(days / 30.4)} months"


def reading_time(core: list, books: list, pages: dict) -> str:
    """One line: about how long the core books and all books take at 20 pages a day."""
    def total(xs):
        return sum(pages.get(x, 0) for x in xs), sum(1 for x in xs if not pages.get(x))
    (cp, cu), (ap, au) = total(core), total(books)
    if not ap:
        return ""
    def part(label, n, p, u):
        more = f", plus {u} book{'s' if u > 1 else ''} with no page count" if u else ""
        return f"{label} ({n}): about {p:,} pages, roughly {weeks(p)} at 20 pages a day{more}"
    parts = ([part("Core books", len(core), cp, cu)] if core and cp else []) + [part("All books", len(books), ap, au)]
    return (f'<p class="sans meta muted">{escape("; ".join(parts))}. Page counts are the typical length '
            "of each book's editions on Open Library, so this is a rough guide.</p>")


def card(tid: str, topic: dict, lists: dict) -> str:
    c = chart(topic, lists)
    first = c["works"][c["order"][0]][1]["title"] if c["order"] else ""
    return (f'<a class="card" href="topic-{tid}.html"><h3>{escape(topic["title"])}</h3>'
            f'<div class="sans meta muted"><span class="badge">topic</span>{len(c["order"])} books · {c["n"]} courses</div>'
            f'<p class="meta">Starts with <em>{escape(first)}</em></p></a>')
