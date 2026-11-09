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

A topic can also hold books that have no thinker list here (`works`), such as Boethius's
Consolation or Sir Gawain. Courses refer to them by bare id; other topics can include them
as <topic>:<work>. Each takes the same fields as a list work's essentials, and the same
sourced `after` links:

  order: year                          # optional: earlier books first where no link decides
  works:
    - id: consolation
      title: The Consolation of Philosophy
      author: Boethius
      year: 524                        # for ordering; `date` is shown instead if given
      date: c. 524
      after:
        - work: augustine-free-choice  # or list:work, or another-topic:work
          strength: context
          why: ...
          sources: [{source, locator, verified, checked_in}]
"""

from __future__ import annotations

import heapq
from html import escape
from pathlib import Path

import build as b
import connections
import findit

TOPICS_DIR = b.ROOT / "topics"
FIELDS = {"topic": {"id", "title", "scope", "courses", "works", "order"},
          "course": {"source", "includes", "others", "locator", "verified", "checked_in", "reviewed_by"},
          "work": {"id", "title", "author", "year", "date", "note", "after"},
          "link": {"work", "strength", "why", "sources"}}


def load() -> dict:
    out = {}
    for path in sorted(TOPICS_DIR.glob("*.yaml")):
        data = b.load_yaml(path) or {}
        out[data.get("id") or path.stem] = data
    return out


def ref(r: str, tid: str) -> str:
    """A book reference as list:work or topic:work; bare ids are this topic's own works."""
    return r if ":" in r else f"{tid}:{r}"


def catalog(lists: dict, topics: dict) -> dict:
    """Every book a topic can include: key -> {title, author, year, date, lid, w, href}."""
    out = {}
    for lid, d in lists.items():
        for w in d["works"]:
            out[f"{lid}:{w['id']}"] = {"title": w["title"], "author": w.get("author") or d["title"],
                                       "year": w.get("year") or d.get("born"), "date": w.get("year"),
                                       "lid": lid, "w": w, "href": f"{lid}.html#{w['id']}"}
    for tid, t in topics.items():
        for w in t.get("works") or []:
            out[f"{tid}:{w['id']}"] = {"title": w["title"], "author": w.get("author", ""), "year": w.get("year"),
                                       "date": w.get("date") or w.get("year"), "lid": None, "w": w,
                                       "href": f"topic-{tid}.html#{w['id']}"}
    return out


def validate(topics: dict, lists: dict, sources: dict, report) -> None:
    books = set(catalog(lists, topics))
    for tid, t in topics.items():
        where = f"topics/{tid}.yaml"
        unknown = set(t) - FIELDS["topic"]
        if unknown:
            report.error(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
        for key in ("title", "scope", "courses"):
            if not t.get(key):
                report.error(f"{where}: missing '{key}'")
        if tid in lists:
            report.error(f"{where}: a topic can't share its id with a list")
        if t.get("order") not in (None, "year"):
            report.error(f"{where}: order must be 'year'")
        ids = set()
        for w in t.get("works") or []:
            ww = f"{where}: work '{w.get('id')}'"
            if set(w) - FIELDS["work"]:
                report.error(f"{ww}: unknown field(s) {', '.join(sorted(set(w) - FIELDS['work']))}")
            if not w.get("id") or not w.get("title"):
                report.error(f"{ww}: needs 'id' and 'title'")
            if w.get("id") in ids:
                report.error(f"{ww}: duplicate id")
            ids.add(w.get("id"))
            for l in w.get("after") or []:
                lw = f"{ww} -> {l.get('work')}"
                if set(l) - FIELDS["link"]:
                    report.error(f"{lw}: unknown field(s) {', '.join(sorted(set(l) - FIELDS['link']))}")
                if ref(l.get("work", ""), tid) not in books:
                    report.error(f"{lw}: unknown book")
                if l.get("strength") not in ("required", "helpful", "context"):
                    report.error(f"{lw}: strength must be required, helpful or context")
                if not (l.get("why") or "").strip():
                    report.error(f"{lw}: needs a 'why'")
                b.check_citations(l, lw, l.get("strength") == "required", sources, report, False)
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
            for r in c.get("includes") or []:
                if ref(r, tid) not in books:
                    report.error(f"{cw}: unknown book '{r}' (use list:work, or a work id from this topic)")
            b.check_citations({"sources": [{k: c[k] for k in ("source", "locator", "verified", "checked_in", "reviewed_by") if k in c}]},
                              cw, False, sources, report, False)
        if not report.errors:
            c = chart(t, lists, topics)
            if len(c["order"]) < len(c["count"]):
                report.error(f"{where}: the links between its books form a loop")


def chart(topic: dict, lists: dict, topics: dict | None = None) -> dict:
    """Books with course counts, in reading order, plus the links between them."""
    topics = load() if topics is None else topics
    tid = topic["id"]
    courses = topic.get("courses") or []
    n = len(courses)
    count: dict[str, int] = {}
    for c in courses:
        for r in c.get("includes") or []:
            count[ref(r, tid)] = count.get(ref(r, tid), 0) + 1
    books = set(count)
    rank = {lid: i for i, lid in enumerate(connections.ordered_lists(lists))}
    works = catalog(lists, topics)
    links = [(a, c, s, why) for a, c, s, why in edges(lists, topics) if a in books and c in books]
    succ: dict[str, list] = {x: [] for x in books}
    indeg = {x: 0 for x in books}
    for a, c, _, _ in links:
        succ[a].append(c)
        indeg[c] += 1

    def key(x):
        e = works[x]
        if topic.get("order") == "year":
            return (e["year"] if e["year"] is not None else 9999, e["title"])
        return (rank.get(e["lid"], len(rank)), e["year"] or 9999, e["title"])

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


def edges(lists: dict, topics: dict | None = None):
    for lid, d in lists.items():
        for w in d["works"]:
            for l in w.get("after") or []:
                tl, tw = b.resolve(l["work"], lid)
                yield f"{tl}:{tw}", f"{lid}:{w['id']}", l["strength"], " ".join(l["why"].split())
    for tid, t in (topics or {}).items():
        for w in t.get("works") or []:
            for l in w.get("after") or []:
                yield ref(l["work"], tid), f"{tid}:{w['id']}", l["strength"], " ".join(l["why"].split())


def topic_links(topics: dict) -> dict:
    """(before, after) -> the link dict, for links defined in topics (they carry their sources)."""
    return {(ref(l["work"], tid), f"{tid}:{w['id']}"): l
            for tid, t in topics.items() for w in t.get("works") or [] for l in w.get("after") or []}


def page_body(tid: str, topic: dict, lists: dict, sources: dict, cites=None) -> str:
    """The topic page. `cites(link, where)` renders a link's sources (the site passes its own)."""
    topics = load()
    topics[tid] = topic
    c = chart(topic, lists, topics)
    tl = topic_links(topics)
    ol = findit.load_ol()
    pages = findit.load_pages()
    W = c["works"]
    core_goals = ",".join(x for x in c["order"] if x in c["core"] and W[x]["lid"])
    by_year = topic.get("order") == "year"
    h = [f"<h1>{escape(topic['title'])}</h1>",
         f'<p class="sans meta muted"><span class="badge">topic</span>{len(c["order"])} books · '
         f'built from {c["n"]} courses</p>',
         f"<p>{escape(' '.join(topic['scope'].split()))}</p>",
         '<p class="meta">Books that at least half the courses assign are marked <strong>core</strong>. The order '
         "follows the sourced links between these books; where no link decides, "
         + ("earlier books come first.</p>" if by_year else "earlier thinkers come first.</p>"),
         reading_time([x for x in c["order"] if x in c["core"]], c["order"], pages)]
    if core_goals:
        h.append(f'<p class="sans"><a href="plan.html#goals={escape(core_goals)}&min=context">'
                 "Make the core books on thinkers' pages a reading plan →</a></p>")
    h.append('<ol class="plan">')
    for i, x in enumerate(c["order"], 1):
        e = W[x]
        into = [(a, s, why) for a, y, s, why in c["links"] if y == x]
        items = []
        for a, s_, t in into:
            link = tl.get((a, x))
            src = cites(link, f"{x} -> {a}") if (cites and link) else ""
            items.append(f'<li><span class="strength">{escape(s_)}</span> after <a href="{escape(W[a]["href"])}">'
                         f'<em>{escape(W[a]["title"])}</em></a><br><span class="meta">{escape(t)}</span>{src}</li>')
        core = x in c["core"]
        own = e["lid"] is None and x.startswith(tid + ":")
        title = (f'<span class="ptitle">{escape(e["title"])}</span>' if own
                 else f'<a class="ptitle" href="{escape(e["href"])}">{escape(e["title"])}</a>')
        who = lists[e["lid"]]["title"] if e["lid"] else e["author"]
        note = e["w"].get("note") if own else None
        fe = findit.entry(x.split(":")[0], e["w"], ol)
        h.append(
            f'<li class="pitem{" goal" if core else ""}" id="{escape(x.split(":", 1)[1]) if own else ""}">'
            f'<span class="pnum sans">{i}</span>{title}'
            f'<div class="sans meta muted">{escape(who)}{" · " + escape(str(e["date"])) if e["date"] else ""}'
            f'{" · ~" + str(pages[x]) + " pp." if pages.get(x) else ""}'
            f' · assigned by {c["count"][x]} of {c["n"]} courses{" · <strong>core</strong>" if core else ""}</div>'
            + (f'<p class="meta">{escape(" ".join(note.split()))}</p>' if note else "")
            + (f'<details class="src"><summary>Why here ({len(into)})</summary><ul class="links">{"".join(items)}</ul></details>' if into else "")
            + findit.static_html(x, fe) + "</li>")
    h.append("</ol>")
    if c["others"]:
        items = "".join(f"<li>{escape(o)}{f' <span class=muted>({k} courses)</span>' if k > 1 else ''}</li>"
                        for o, k in sorted(c["others"].items(), key=lambda kv: (-kv[1], kv[0])))
        h.append("<h2>Also read in these courses</h2>"
                 '<p class="meta muted">Shorter pieces and books not yet on this site.</p>'
                 f'<ul class="links">{items}</ul>')
    rows = []
    for course in topic["courses"]:
        s = sources[course["source"]]
        title = escape(f"{s.get('author', '')}, {s['title']}".lstrip(", "))
        if s.get("url"):
            title = f'<a href="{escape(s["url"])}">{title}</a>'
        books = ", ".join(escape(W[ref(r, tid)]["title"]) for r in course["includes"])
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
    first = c["works"][c["order"][0]]["title"] if c["order"] else ""
    return (f'<a class="card" href="topic-{tid}.html"><h3>{escape(topic["title"])}</h3>'
            f'<div class="sans meta muted"><span class="badge">topic</span>{len(c["order"])} books · {c["n"]} courses</div>'
            f'<p class="meta">Starts with <em>{escape(first)}</em></p></a>')
