"""Connections between lists: the cross-list links ("read X's book before Y's").

Every link in a list's `after:` that points into another list (e.g. `kant:prolegomena`)
is a connection. This module collects them in both directions and draws the map.
"""

from __future__ import annotations

import json
from html import escape

ROW_H = 46
LEFT = 178          # width reserved for names
ARC_MAX = 190       # widest an arc may bulge, so the map fits a phone screen


def collect(lists: dict) -> list[dict]:
    """All cross-list links as dicts: from_list, from_work, to_list, to_work, strength, why."""
    out = []
    for lid, data in lists.items():
        for w in data["works"]:
            for l in w.get("after") or []:
                if ":" not in l["work"]:
                    continue
                fl, fw = l["work"].split(":", 1)
                src = next((x for x in lists.get(fl, {}).get("works", []) if x["id"] == fw), {})
                out.append({"from_list": fl, "from_work": fw, "to_list": lid, "to_work": w["id"],
                            "strength": l["strength"], "why": l["why"].strip(),
                            "core": src.get("tier") == "core" and w.get("tier") == "core"})
    return out


def title_of(lists, lid, wid):
    return next(w["title"] for w in lists[lid]["works"] if w["id"] == wid)


def born_label(data) -> str:
    b = data.get("born")
    if b is None:
        return ""
    return f"c. {-b} BCE" if b < 0 else f"b. {b}"


def ordered_lists(lists: dict) -> list[str]:
    return sorted(lists, key=lambda lid: (lists[lid].get("born", 9999), lists[lid]["title"]))


def render_map_svg(lists: dict) -> str:
    links = collect(lists)
    order = ordered_lists(lists)
    row = {lid: i for i, lid in enumerate(order)}
    pairs: dict[tuple, list] = {}
    for l in links:
        pairs.setdefault((l["from_list"], l["to_list"]), []).append(l)
    width = LEFT + ARC_MAX + 20
    height = len(order) * ROW_H + 30
    y = lambda lid: 24 + row[lid] * ROW_H
    out = [f'<svg class="connmap" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-label="Map of connections between thinkers">']
    # Arcs first so names sit on top.
    for (a, b), ls in sorted(pairs.items(), key=lambda kv: -abs(row[kv[0][0]] - row[kv[0][1]])):
        y1, y2 = sorted((y(a), y(b)))
        span = y2 - y1
        rx = min(span / 2, ARC_MAX)
        sw = 1.2 + 1.1 * (len(ls) - 1)
        tip = f"{lists[a]['title']} → {lists[b]['title']}: {len(ls)} link{'s' if len(ls) > 1 else ''}"
        # Each link's strength and whether both books are core, so the page can filter.
        data = escape(json.dumps([[l["strength"][0], int(l["core"])] for l in ls]))
        out.append(
            f'<path d="M{LEFT},{y1} A{rx:.1f},{span / 2:.1f} 0 0 1 {LEFT},{y2}" class="arc" '
            f'data-links="{data}" data-pair="{escape(lists[a]["title"])} → {escape(lists[b]["title"])}" '
            f'style="stroke-width:{sw:.1f}"><title>{escape(tip)}</title></path>'
        )
    for lid in order:
        d = lists[lid]
        cls = "node thinker" if d.get("group", "thinkers") == "thinkers" else "node"
        out.append(
            f'<a href="{lid}.html"><g class="{cls}">'
            f'<circle cx="{LEFT}" cy="{y(lid)}" r="6"/>'
            f'<text x="{LEFT - 12}" y="{y(lid) + 5}" text-anchor="end">{escape(d["title"])}</text>'
            f'<text x="{LEFT - 12}" y="{y(lid) + 19}" text-anchor="end" class="born">{escape(born_label(d))}</text>'
            f'</g></a>'
        )
    out.append("</svg>")
    return "\n".join(out)


def _rows_html(items, lists, side):
    rows = []
    for l in items:
        other = l["from_list"] if side == "in_from" else l["to_list"]
        ow = l["from_work"] if side == "in_from" else l["to_work"]
        here = l["to_work"] if side == "in_from" else l["from_work"]
        here_list = l["to_list"] if side == "in_from" else l["from_list"]
        rows.append(
            f'<li><a href="{other}.html#{ow}"><em>{escape(title_of(lists, other, ow))}</em></a> '
            f'<span class="muted">({escape(lists[other]["title"])})</span> '
            f'→ <a href="{here_list}.html#{here}"><em>{escape(title_of(lists, here_list, here))}</em></a>'
            f' <span class="strength">{escape(l["strength"])}</span><br>'
            f'<span class="meta">{escape(l["why"])}</span></li>'
        )
    return "".join(rows)


def section_html(lid: str, lists: dict) -> str:
    links = collect(lists)
    builds_on = [l for l in links if l["to_list"] == lid]
    built_by = [l for l in links if l["from_list"] == lid]
    if not builds_on and not built_by:
        return ""
    h = ['<h2 id="connections">Connections</h2>',
         '<p class="meta muted">Links to and from other thinkers on this site. '
         '<a href="map.html">See the full map</a>.</p>']
    if builds_on:
        h.append(f"<h3>Builds on</h3><ul class=\"links\">{_rows_html(builds_on, lists, 'in_from')}</ul>")
    if built_by:
        h.append(f"<h3>Who builds on {escape(lists[lid]['title'])}</h3>"
                 f"<ul class=\"links\">{_rows_html(built_by, lists, 'out_to')}</ul>")
    return "".join(h)


def section_md(lid: str, lists: dict) -> list[str]:
    links = collect(lists)
    builds_on = [l for l in links if l["to_list"] == lid]
    built_by = [l for l in links if l["from_list"] == lid]
    if not builds_on and not built_by:
        return []
    out = ["## Connections", ""]
    if builds_on:
        out += ["**Builds on**", ""]
        for l in builds_on:
            out.append(f"- *{title_of(lists, l['from_list'], l['from_work'])}* ({lists[l['from_list']]['title']}) → "
                       f"*{title_of(lists, lid, l['to_work'])}* — {l['strength']}. {l['why']}")
        out.append("")
    if built_by:
        out += [f"**Who builds on {lists[lid]['title']}**", ""]
        for l in built_by:
            out.append(f"- *{title_of(lists, lid, l['from_work'])}* → *{title_of(lists, l['to_list'], l['to_work'])}* "
                       f"({lists[l['to_list']]['title']}) — {l['strength']}. {l['why']}")
        out.append("")
    return out


def map_page_body(lists: dict) -> str:
    links = collect(lists)
    pairs = {}
    for l in links:
        pairs.setdefault((l["from_list"], l["to_list"]), []).append(l)
    order = ordered_lists(lists)
    rank = {lid: i for i, lid in enumerate(order)}
    items = []
    for (a, b), ls in sorted(pairs.items(), key=lambda kv: (rank[kv[0][1]], rank[kv[0][0]])):
        inner = "".join(
            f'<li data-s="{l["strength"]}" data-core="{int(l["core"])}"><a href="{a}.html#{l["from_work"]}"><em>{escape(title_of(lists, a, l["from_work"]))}</em></a> → '
            f'<a href="{b}.html#{l["to_work"]}"><em>{escape(title_of(lists, b, l["to_work"]))}</em></a> '
            f'<span class="strength">{escape(l["strength"])}</span><br><span class="meta">{escape(l["why"])}</span></li>'
            for l in ls)
        items.append(f'<details class="src pairbox"><summary><strong>{escape(lists[a]["title"])}</strong> → '
                     f'<strong>{escape(lists[b]["title"])}</strong> <span class="muted pcount">({len(ls)})</span></summary>'
                     f'<ul class="links">{inner}</ul></details>')
    hub = sorted(order, key=lambda lid: -sum(1 for l in links if lid in (l["from_list"], l["to_list"])))[:3]
    return (
        "<h1>How they connect</h1>"
        f"<p>Each arc is a sourced link between two thinkers' books: read the older one before the newer. "
        f"Thicker arcs carry more links. {len(links)} links connect {len(pairs)} pairs; the most connected "
        f"are {', '.join(escape(lists[h]['title']) for h in hub)}. Tap a name to open its list.</p>"
        + FILTERS +
        '<p id="mapsummary" class="sans meta"></p>'
        f"{render_map_svg(lists)}"
        "<h2>Every connection</h2>" + "".join(items) +
        '<script src="map.js"></script>'
    )


FILTERS = (
    '<div class="controls sans" role="group" aria-label="Which links to show">'
    '<button data-min="required" aria-pressed="false">Required only</button>'
    '<button data-min="helpful" aria-pressed="false">Required + helpful</button>'
    '<button data-min="context" aria-pressed="true">All links</button></div>'
    '<p class="sans meta"><label><input type="checkbox" id="gcore"> Only links between core books</label></p>'
)

MAP_JS = r"""
(function () {
  var RANK = { r: 2, h: 1, c: 0 }, MIN = { required: 2, helpful: 1, context: 0 };
  var F = { min: 'context', core: false };
  try { var s = JSON.parse(localStorage.getItem('map-filters') || 'null'); if (s) F = s; } catch (e) {}
  function keep(strength, core) { return RANK[strength] >= MIN[F.min] && (!F.core || core); }
  function apply() {
    var shownLinks = 0, pairs = 0;
    document.querySelectorAll('svg.connmap path.arc').forEach(function (p) {
      var n = JSON.parse(p.dataset.links).filter(function (l) { return keep(l[0], l[1]); }).length;
      p.style.display = n ? '' : 'none';
      p.style.strokeWidth = (1.2 + 1.1 * Math.max(0, n - 1)).toFixed(1);
      if (n) { shownLinks += n; pairs += 1; }
    });
    document.querySelectorAll('details.pairbox').forEach(function (d) {
      var n = 0;
      d.querySelectorAll('li[data-s]').forEach(function (li) {
        var k = keep(li.dataset.s[0], li.dataset.core === '1');
        li.style.display = k ? '' : 'none'; if (k) n++;
      });
      d.style.display = n ? '' : 'none';
      var c = d.querySelector('.pcount'); if (c) c.textContent = '(' + n + ')';
    });
    var m = document.getElementById('mapsummary');
    if (m) m.textContent = 'Showing ' + shownLinks + ' link' + (shownLinks === 1 ? '' : 's') + ' between ' + pairs + ' pair' + (pairs === 1 ? '' : 's') + '.';
    document.querySelectorAll('[data-min]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.min === F.min ? 'true' : 'false'); });
    var cb = document.getElementById('gcore'); if (cb) cb.checked = !!F.core;
  }
  function setF(k, v) { F[k] = v; try { localStorage.setItem('map-filters', JSON.stringify(F)); } catch (e) {} apply(); }
  document.querySelectorAll('[data-min]').forEach(function (b) { b.addEventListener('click', function () { setF('min', b.dataset.min); }); });
  var cb = document.getElementById('gcore'); if (cb) cb.addEventListener('change', function () { setF('core', cb.checked); });
  apply();
})();
"""
