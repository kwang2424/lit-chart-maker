#!/usr/bin/env python3
"""Build the static website into site/ (published with GitHub Pages).

Usage:
  python tools/site.py
"""

from __future__ import annotations

import shutil
import sys
from html import escape
from pathlib import Path

import build as b
import chart
import consensus

SITE = b.ROOT / "site"
REPO_URL = "https://github.com/kwang2424/lit-chart-maker"

CSS = """
:root {
  --bg: #f6f1e7; --surface: #fffdf8; --ink: #1f1a14; --muted: #6b6256; --line: #ddd3c3;
  --core: #f4d58d; --core-edge: #8a6d1f; --ext: #d6e6f5; --ext-edge: #3b6a91;
  --opt: #ebe7e0; --opt-edge: #8c8072; --ok: #2f6b3a; --warn: #9a5b00; --link: #6a3d0f;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #17140f; --surface: #211d17; --ink: #efe8dc; --muted: #a89e8f; --line: #3a342b;
    --core: #4a3c18; --core-edge: #d8b45a; --ext: #1c2c3b; --ext-edge: #7fa9cf;
    --opt: #2a2620; --opt-edge: #a89e8f; --ok: #7fc28b; --warn: #e0a54a; --link: #e8c48a;
  }
}
:root[data-theme="dark"] {
  --bg: #17140f; --surface: #211d17; --ink: #efe8dc; --muted: #a89e8f; --line: #3a342b;
  --core: #4a3c18; --core-edge: #d8b45a; --ext: #1c2c3b; --ext-edge: #7fa9cf;
  --opt: #2a2620; --opt-edge: #a89e8f; --ok: #7fc28b; --warn: #e0a54a; --link: #e8c48a;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.55 Georgia, "Times New Roman", serif; }
a { color: var(--link); }
.wrap { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }
header.top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  flex-wrap: wrap; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 24px; }
header.top a.home { font-weight: bold; text-decoration: none; color: var(--ink); }
.sans { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
.muted { color: var(--muted); }
h1 { font-size: 2.1rem; line-height: 1.2; margin: 0 0 8px; }
h2 { font-size: 1.35rem; margin: 40px 0 12px; }
.meta { font-size: 0.9rem; }
.badge { display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 99px;
  border: 1px solid var(--line); background: var(--surface); margin-right: 4px; }
.cards { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.card { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px; text-decoration: none; color: var(--ink); }
.card:hover { border-color: var(--muted); }
.card h3 { margin: 0 0 6px; }
.chart { display: block; width: 100%; height: auto; border-radius: 10px; border: 1px solid var(--line); }
details.chart-box { margin: 20px 0; }
details.chart-box summary { cursor: pointer; }
ol.core { padding-left: 1.4em; }
ol.core li { margin: 4px 0; }
.controls { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 16px; }
.controls button { font: inherit; font-size: 0.85rem; padding: 6px 12px; border-radius: 99px;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink); cursor: pointer; }
.controls button[aria-pressed="true"] { background: var(--ink); color: var(--bg); }
.work { background: var(--surface); border: 1px solid var(--line); border-left: 6px solid var(--opt-edge);
  border-radius: 10px; padding: 14px 16px; margin: 12px 0; }
.work.core { border-left-color: var(--core-edge); }
.work.extended { border-left-color: var(--ext-edge); }
.work h3 { margin: 0; font-size: 1.1rem; display: flex; gap: 10px; align-items: baseline; }
.work .num { font-family: -apple-system, Helvetica, Arial, sans-serif; font-size: 0.8rem; font-weight: bold;
  min-width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center;
  justify-content: center; background: var(--opt-edge); color: var(--bg); flex: none; }
.work.core .num { background: var(--core-edge); }
.work.extended .num { background: var(--ext-edge); }
.work .sub { margin: 2px 0 8px 36px; }
.work .body { margin-left: 36px; }
.work p { margin: 6px 0; }
.work.read { opacity: 0.55; }
.work label.done { float: right; font-size: 0.8rem; cursor: pointer; }
.start { background: var(--core); border-radius: 8px; padding: 8px 10px; margin: 8px 0; }
ul.links { padding-left: 1.1em; margin: 6px 0; }
ul.links li { margin: 6px 0; }
.strength { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
details.src summary { cursor: pointer; font-size: 0.85rem; color: var(--muted); }
ul.cites { font-size: 0.85rem; padding-left: 1.1em; }
.ok { color: var(--ok); } .warn { color: var(--warn); }
.hidden { display: none; }
footer { margin-top: 48px; font-size: 0.85rem; }
ul.consensus { list-style: none; padding: 0; margin: 12px 0; }
ul.consensus li { margin: 10px 0; }
.bar { height: 8px; background: var(--line); border-radius: 99px; overflow: hidden; margin: 4px 0 2px; }
.bar span { display: block; height: 100%; background: var(--core-edge); }
"""

JS = """
(function () {
  var key = 'read:' + document.body.dataset.list;
  var read = {};
  try { read = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) {}
  function save() { try { localStorage.setItem(key, JSON.stringify(read)); } catch (e) {} }
  document.querySelectorAll('.work').forEach(function (el) {
    var box = el.querySelector('input.done');
    if (!box) return;
    box.checked = !!read[el.id];
    el.classList.toggle('read', box.checked);
    box.addEventListener('change', function () {
      read[el.id] = box.checked; el.classList.toggle('read', box.checked); save();
    });
  });
  var buttons = document.querySelectorAll('.controls button');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      buttons.forEach(function (o) { o.setAttribute('aria-pressed', o === btn ? 'true' : 'false'); });
      var f = btn.dataset.filter;
      document.querySelectorAll('.work').forEach(function (el) {
        var show = f === 'all' || (f === 'core' && el.classList.contains('core')) ||
          (f === 'unread' && !el.classList.contains('read'));
        el.classList.toggle('hidden', !show);
      });
    });
  });
})();
"""


def page(title: str, body: str, list_id: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Sourced reading orders: every 'read X before Y' comes with a reason and a citation.">
<link rel="stylesheet" href="style.css">
</head>
<body data-list="{list_id}">
<div class="wrap">
<header class="top"><a class="home" href="index.html">Reading Orders</a>
<a class="sans meta" href="{REPO_URL}">Contribute on GitHub</a></header>
{body}
<footer class="muted">Every link between books is backed by a source.
Spot a mistake? <a href="{REPO_URL}/blob/main/CONTRIBUTING.md">Help fix it</a>.</footer>
</div>
{'<script src="app.js"></script>' if list_id else ''}
</body>
</html>
"""


def stats(data: dict) -> tuple[int, int]:
    claims = [l for w in data["works"] for l in (w.get("after") or [])]
    claims += [w["start_here"] for w in data["works"] if w.get("start_here")]
    claims += [t for w in data["works"] for t in (w.get("tips") or [])]
    cites = [c for cl in claims for c in (cl.get("sources") or [])]
    cites += list(data.get("survey") or [])
    return sum(1 for c in cites if c.get("verified")), len(cites)


def cite_html(c: dict, sources: dict) -> str:
    s = sources[c["source"]]
    title = escape(s["title"])
    if s.get("url"):
        title = f'<a href="{escape(s["url"])}">{title}</a>'
    text = f"{escape(s.get('author', ''))}, <em>{title}</em>".lstrip(", ")
    if c.get("locator"):
        text += f", {escape(str(c['locator']))}"
    text += f' <span class="muted">[{b.SOURCE_TIER_NAMES[s["tier"]]}]</span>'
    if c.get("verified"):
        text += f' <span class="ok">✓ checked in {escape(c["checked_in"])}</span>'
    else:
        text += ' <span class="warn">⚠ not yet verified</span>'
    return f"<li>{text}</li>"


def cites_block(claim: dict, sources: dict) -> str:
    items = "".join(cite_html(c, sources) for c in claim.get("sources") or [])
    n = len(claim.get("sources") or [])
    return f'<details class="src"><summary>{n} source{"s" if n != 1 else ""}</summary><ul class="cites">{items}</ul></details>'


def list_page(data: dict, lists: dict, sources: dict) -> str:
    lid = data["id"]
    by_id = {w["id"]: w for w in data["works"]}
    core_order, full_order = b.compute_order(data)
    num = {n: i + 1 for i, n in enumerate(full_order)}
    done, total = stats(data)

    def ref_html(ref: str) -> str:
        tl, tw = b.resolve(ref, lid)
        w = next(x for x in lists[tl]["works"] if x["id"] == tw)
        if tl == lid:
            return f'<a href="#{tw}"><em>{escape(w["title"])}</em></a>'
        return f'<a href="{tl}.html#{tw}"><em>{escape(w["title"])}</em></a> <span class="muted">({escape(lists[tl]["title"])} list)</span>'

    h = [
        f"<h1>{escape(data['title'])}</h1>",
        f'<p class="sans meta muted"><span class="badge">{escape(data["status"])}</span>'
        f"{len(full_order)} works · {done}/{total} citations checked</p>",
        f"<p>{escape(data['scope'].strip())}</p>",
        '<details class="chart-box" open><summary class="sans meta">Chart</summary>',
        f'<p><a href="{lid}.svg"><img class="chart" src="{lid}.svg" alt="Reading chart for {escape(data["title"])}"></a></p>',
        "</details>",
        "<h2>Core path</h2><ol class=\"core\">",
    ]
    for n in core_order:
        w = by_id[n]
        star = " ★ start here" if w.get("start_here") else ""
        yr = f'({w["year"]})' if w.get("year") else ""
        h.append(f'<li><a href="#{n}">{escape(w["title"])}</a> <span class="muted">{yr}{star}</span></li>')
    h.append("</ol>")

    h.append(consensus.render_html(data, sources, b.SOURCE_TIER_NAMES))
    h += [
        "<h2>Full reading order</h2>",
        '<div class="controls sans"><button data-filter="all" aria-pressed="true">All</button>'
        '<button data-filter="core" aria-pressed="false">Core only</button>'
        '<button data-filter="unread" aria-pressed="false">Unread</button></div>',
    ]
    for n in full_order:
        w = by_id[n]
        sub = " · ".join(
            escape(str(x)) for x in (w.get("author"), w.get("year"), f"{w['tier']} · {w['kind']}") if x
        )
        dots = "●" * w["difficulty"] + "○" * (5 - w["difficulty"])
        parts = [
            f'<article class="work {w["tier"]}" id="{n}">',
            f'<label class="done sans muted"><input type="checkbox" class="done"> read</label>',
            f'<h3><span class="num">{num[n]}</span>{escape(w["title"])}</h3>',
            f'<div class="sub sans meta muted">{sub} · difficulty {dots}</div>',
            '<div class="body">',
        ]
        if w.get("start_here"):
            parts.append(
                f'<div class="start"><strong>★ Good place to start.</strong> {escape(w["start_here"]["why"].strip())}'
                f'{cites_block(w["start_here"], sources)}</div>'
            )
        if w.get("note"):
            parts.append(f"<p>{escape(w['note'].strip())}</p>")
        if w.get("tier_note"):
            parts.append(f'<p class="meta muted"><em>Why this tier:</em> {escape(w["tier_note"].strip())}</p>')
        if w.get("translation"):
            parts.append(f'<p class="meta"><strong>Translation:</strong> {escape(w["translation"])}</p>')
        if w.get("tips"):
            parts.append('<p class="meta"><strong>Reading tips</strong></p><ul class="links">')
            for t in w["tips"]:
                parts.append(f"<li>{escape(t['text'].strip())}{cites_block(t, sources)}</li>")
            parts.append("</ul>")
        if w.get("after"):
            parts.append('<p class="meta"><strong>Read first</strong></p><ul class="links">')
            for l in w["after"]:
                parts.append(
                    f'<li>{ref_html(l["work"])} <span class="strength">{escape(l["strength"])}</span><br>'
                    f'{escape(l["why"].strip())}{cites_block(l, sources)}</li>'
                )
            parts.append("</ul>")
        parts.append("</div></article>")
        h.append("".join(parts))
    return page(f"{data['title']} reading order", "\n".join(h), lid)


def index_page(lists: dict) -> str:
    h = [
        "<h1>Reading Orders</h1>",
        "<p>Where to start with a thinker, and what to read before what. Inspired by the old "
        "/lit/ reading charts, but every “read X before Y” comes with a reason and a "
        "citation: the author's own words where possible, then scholarly guides.</p>",
    ]

    def card(lid, data):
        core, full = b.compute_order(data)
        done, total = stats(data)
        first = next((w for w in data["works"] if w["id"] == core[0]), None) if core else None
        return (
            f'<a class="card" href="{lid}.html"><h3>{escape(data["title"])}</h3>'
            f'<div class="sans meta muted"><span class="badge">{escape(data["status"])}</span>'
            f"{len(full)} works · {done}/{total} citations checked</div>"
            + (f'<p class="meta">Start with <em>{escape(first["title"])}</em></p>' if first else "")
            + "</a>"
        )

    thinkers = sorted((l for l in lists.items() if l[1].get("group", "thinkers") == "thinkers"),
                      key=lambda kv: (kv[1].get("sequence", 99), kv[1]["title"]))
    preds = sorted((l for l in lists.items() if l[1].get("group") == "predecessors"),
                   key=lambda kv: kv[1].get("sequence", 99))
    h += ["<h2>The thinkers</h2>", '<div class="cards">'] + [card(*l) for l in thinkers] + ["</div>"]
    if preds:
        h += [
            "<h2>Their predecessors, in historical order</h2>",
            "<p>Who Nietzsche, Deleuze and Jung read and argued with. You don't need all of them: "
            "each thinker's page links to the specific books it depends on.</p>",
            '<div class="cards">',
        ] + [card(*l) for l in preds]
    h.append("</div>")
    h.append(
        "<h2>How it works</h2>"
        "<p>Each list records links between books: <strong>required</strong> (the later book doesn't make "
        "sense without the earlier one), <strong>helpful</strong>, or <strong>context</strong>. The order is "
        "computed from those links, so it can't contradict itself. Sources are ranked: the author's own words, "
        "scholarly guides, university syllabi and teaching lists, then community lists. A citation counts as checked only "
        "once someone has looked it up in a named edition.</p>"
    )
    return page("Reading Orders", "\n".join(h))


def main() -> int:
    report = b.Report()
    sources = b.load_sources(report)
    lists = b.load_lists(report)
    b.validate(lists, sources, report, strict=False)
    if report.errors:
        print("\n".join(f"ERROR: {e}" for e in report.errors))
        return 1

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (SITE / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")
    (SITE / "index.html").write_text(index_page(lists), encoding="utf-8")
    for lid, data in lists.items():
        core, full = b.compute_order(data)
        svg = chart.render_svg(
            data, full, core, list(b.hard_edges(data["works"], lid)), list(b.all_edges(data["works"], lid)), lists
        )
        (SITE / f"{lid}.svg").write_text(svg, encoding="utf-8")
        (SITE / f"{lid}.html").write_text(list_page(data, lists, sources), encoding="utf-8")
        png = b.OUT_DIR / f"{lid}.png"
        if png.exists():
            shutil.copy(png, SITE / png.name)
    print(f"built site/ with {len(lists)} list(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
