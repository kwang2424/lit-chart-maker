"""The book graph: every sourced "read X before Y" link, across all lists.

The validator guarantees this graph has no cycles (see build.find_global_cycle), so
any book's prerequisites can be laid out in layers, earliest first. The site's
graph page (site/graph.html) draws that for one chosen book at a time.
"""

from __future__ import annotations

import json
from html import escape

import build as b
import connections

# Book shown when the page opens without a #list:work in the URL.
DEFAULT_FOCUS = "freud:beyond-pleasure"


def data(lists: dict) -> dict:
    """Nodes and edges for the page script. Node ids are "list:work"."""
    order = connections.ordered_lists(lists)
    rank = {lid: i for i, lid in enumerate(order)}
    nodes = {}
    for lid in order:
        d = lists[lid]
        for w in d["works"]:
            nodes[f"{lid}:{w['id']}"] = {
                "t": w["title"], "l": lid, "y": w.get("year"), "tier": w["tier"],
            }
    edges = []
    for lid, d in lists.items():
        for w in d["works"]:
            for link in w.get("after") or []:
                tl, tw = b.resolve(link["work"], lid)
                edges.append({"a": f"{tl}:{tw}", "b": f"{lid}:{w['id']}",
                              "s": link["strength"], "why": " ".join(link["why"].split())})
    thinkers = {lid: {"name": lists[lid]["title"], "rank": rank[lid], "n": len(order)} for lid in order}
    return {"nodes": nodes, "edges": edges, "thinkers": thinkers, "focus": DEFAULT_FOCUS}


def linked(lists: dict) -> set[str]:
    """Books that take part in at least one link."""
    s = set()
    for a, c in b.global_edges(lists):
        s.add(a)
        s.add(c)
    return s


def page_body(lists: dict) -> str:
    d = data(lists)
    have = linked(lists)
    groups = []
    for lid in connections.ordered_lists(lists):
        opts = "".join(
            f'<option value="{lid}:{w["id"]}">{escape(w["title"])}</option>'
            for w in lists[lid]["works"] if f'{lid}:{w["id"]}' in have
        )
        if opts:
            groups.append(f'<optgroup label="{escape(lists[lid]["title"])}">{opts}</optgroup>')
    payload = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    n_edges = len(d["edges"])
    n_cross = sum(1 for e in d["edges"] if e["a"].split(":")[0] != e["b"].split(":")[0])
    return (
        "<h1>What to read first</h1>"
        f"<p>Pick a book to see everything the sources say to read before it, across all "
        f"{len(lists)} thinkers, earliest first. Each line is one sourced link ({n_edges} in all, "
        f"{n_cross} between thinkers); the graph has no loops, so there is always a place to start. "
        "Tap a book to follow its own prerequisites.</p>"
        '<p class="sans"><label for="focus" class="meta">Book</label><br>'
        f'<select id="focus" class="gselect">{"".join(groups)}</select></p>'
        '<p class="sans meta muted gkey"><span class="k required"></span> required '
        '<span class="k helpful"></span> helpful <span class="k context"></span> context</p>'
        '<p id="gsummary" class="sans meta"></p>'
        '<div id="graph" class="graph"><svg class="gedges" aria-hidden="true"></svg><div class="glayers"></div></div>'
        '<h2 id="gwhy-h">Why these come first</h2><ul id="gwhy" class="links"></ul>'
        "<noscript><p>This page needs JavaScript to draw the graph. Each list page shows the same "
        "links under “Read first”.</p></noscript>"
        f'<script id="gdata" type="application/json">{payload}</script>'
        '<script src="graph.js"></script>'
    )


JS = r"""
(function () {
  var D = JSON.parse(document.getElementById('gdata').textContent);
  var pred = {}, succ = {};
  D.edges.forEach(function (e) {
    (pred[e.b] = pred[e.b] || []).push(e);
    (succ[e.a] = succ[e.a] || []).push(e);
  });
  var sel = document.getElementById('focus');
  var box = document.getElementById('graph');
  var layersEl = box.querySelector('.glayers');
  var svg = box.querySelector('svg');
  var NS = 'http://www.w3.org/2000/svg';

  function ancestors(id) {
    var seen = {}, stack = [id];
    while (stack.length) {
      var x = stack.pop();
      (pred[x] || []).forEach(function (e) { if (!seen[e.a]) { seen[e.a] = 1; stack.push(e.a); } });
    }
    return seen;
  }
  function label(id) {
    var n = D.nodes[id], th = D.thinkers[n.l];
    return { title: n.t, who: th.name + (n.y ? ' · ' + n.y : ''), hue: Math.round(360 * th.rank / th.n) };
  }
  function url(id) { var p = id.split(':'); return p[0] + '.html#' + p[1]; }

  function render(focus) {
    if (!D.nodes[focus]) focus = D.focus;
    sel.value = focus;
    var anc = ancestors(focus), inSub = Object.assign({}, anc); inSub[focus] = 1;
    // Longest path from a starting book, within the prerequisites only.
    var rank = {};
    function r(id) {
      if (rank[id] !== undefined) return rank[id];
      rank[id] = 0;
      var m = -1;
      (pred[id] || []).forEach(function (e) { if (inSub[e.a]) m = Math.max(m, r(e.a)); });
      return (rank[id] = m + 1);
    }
    Object.keys(inSub).forEach(r);
    var top = rank[focus];
    var next = (succ[focus] || []).map(function (e) { return e.b; });
    var layers = [];
    Object.keys(inSub).forEach(function (id) { (layers[rank[id]] = layers[rank[id]] || []).push(id); });
    if (next.length) layers.push(next.filter(function (id, i) { return next.indexOf(id) === i; }));
    // Order each layer by where its prerequisites sit, then by thinker and year.
    var pos = {};
    layers.forEach(function (ids, li) {
      ids.sort(function (a, b) {
        var ka = baryOf(a, li), kb = baryOf(b, li);
        if (ka !== kb) return ka - kb;
        var na = D.nodes[a], nb = D.nodes[b];
        return (D.thinkers[na.l].rank - D.thinkers[nb.l].rank) || ((na.y || 0) - (nb.y || 0));
      });
      ids.forEach(function (id, i) { pos[id] = ids.length > 1 ? i / (ids.length - 1) : 0.5; });
    });
    function baryOf(id, li) {
      var ps = li === top + 1 ? [focus] : (pred[id] || []).filter(function (e) { return inSub[e.a]; }).map(function (e) { return e.a; });
      var xs = ps.map(function (p) { return pos[p]; }).filter(function (v) { return v !== undefined; });
      return xs.length ? xs.reduce(function (s, v) { return s + v; }, 0) / xs.length : 0.5;
    }

    layersEl.innerHTML = '';
    layers.forEach(function (ids, li) {
      var row = document.createElement('div');
      row.className = 'glayer';
      var cap = document.createElement('div');
      cap.className = 'gcap sans meta muted';
      cap.textContent = li === top ? 'Your book' : li > top ? 'Leads on to' : 'Step ' + (li + 1);
      row.appendChild(cap);
      var wrapr = document.createElement('div');
      wrapr.className = 'gnodes';
      ids.forEach(function (id) {
        var lb = label(id), a = document.createElement('a');
        a.className = 'gnode sans' + (id === focus ? ' focus' : '') + ' ' + D.nodes[id].tier;
        a.href = '#' + id;
        a.dataset.id = id;
        a.style.setProperty('--h', lb.hue);
        a.innerHTML = '<span class="gt"></span><span class="gw"></span>';
        a.querySelector('.gt').textContent = lb.title;
        a.querySelector('.gw').textContent = lb.who;
        wrapr.appendChild(a);
      });
      row.appendChild(wrapr);
      layersEl.appendChild(row);
    });

    var n = Object.keys(anc).length;
    var who = {};
    Object.keys(anc).forEach(function (id) { who[D.nodes[id].l] = 1; });
    var f = label(focus);
    document.getElementById('gsummary').textContent = n
      ? n + ' book' + (n > 1 ? 's' : '') + ' before ' + f.title + ', from ' + Object.keys(who).length +
        ' thinker' + (Object.keys(who).length > 1 ? 's' : '') + '; the longest chain is ' + top + ' step' + (top > 1 ? 's' : '') + '.'
      : 'The sources name nothing to read before ' + f.title + '.';

    var ul = document.getElementById('gwhy');
    ul.innerHTML = '';
    (pred[focus] || []).forEach(function (e) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + e.a; a.textContent = D.nodes[e.a].t;
      var s = document.createElement('span'); s.className = 'strength'; s.textContent = ' ' + e.s;
      var p = document.createElement('div'); p.className = 'meta'; p.textContent = e.why;
      var more = document.createElement('a'); more.href = url(focus); more.className = 'meta';
      more.textContent = 'sources on the ' + D.thinkers[D.nodes[focus].l].name + ' page';
      li.appendChild(a); li.appendChild(s); li.appendChild(p); li.appendChild(more);
      ul.appendChild(li);
    });
    if (!ul.children.length) ul.innerHTML = '<li class="muted">Nothing listed.</li>';
    drawEdges(inSub, focus, next);
  }

  function drawEdges(inSub, focus, next) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var bb = box.getBoundingClientRect();
    svg.setAttribute('width', bb.width); svg.setAttribute('height', bb.height);
    svg.setAttribute('viewBox', '0 0 ' + bb.width + ' ' + bb.height);
    var el = {};
    box.querySelectorAll('.gnode').forEach(function (a) { el[a.dataset.id] = a.getBoundingClientRect(); });
    D.edges.forEach(function (e) {
      var keep = (inSub[e.a] && inSub[e.b]) || (e.a === focus && next.indexOf(e.b) >= 0);
      if (!keep || !el[e.a] || !el[e.b]) return;
      var A = el[e.a], B = el[e.b];
      var x1 = A.left + A.width / 2 - bb.left, y1 = A.bottom - bb.top;
      var x2 = B.left + B.width / 2 - bb.left, y2 = B.top - bb.top;
      var dy = Math.max(24, (y2 - y1) / 2);
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + (y1 + dy) + ' ' + x2 + ',' + (y2 - dy) + ' ' + x2 + ',' + y2);
      p.setAttribute('class', 'gedge ' + e.s + (e.b === focus || e.a === focus ? ' near' : ''));
      svg.appendChild(p);
    });
  }

  function current() { return decodeURIComponent(location.hash.slice(1)) || D.focus; }
  sel.addEventListener('change', function () { location.hash = sel.value; });
  window.addEventListener('hashchange', function () { render(current()); window.scrollTo(0, box.offsetTop - 80); });
  var t;
  window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(function () { render(current()); }, 150); });
  render(current());
})();
"""

CSS = """
select.gselect { font: inherit; font-size: 0.95rem; width: 100%; max-width: 100%; padding: 8px;
  border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); }
.graph { position: relative; margin: 8px 0 24px; }
.graph svg.gedges { position: absolute; left: 0; top: 0; pointer-events: none; overflow: visible; }
.glayer { position: relative; margin: 0 0 34px; }
.gcap { margin: 0 0 6px; }
.gnodes { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.gnode { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 2px;
  max-width: 100%; min-width: 0; flex: 0 1 220px; padding: 8px 10px; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--line);
  border-left: 5px solid hsl(var(--h) 50% var(--gl, 42%)); color: var(--ink); text-decoration: none;
  font-size: 0.85rem; line-height: 1.3; }
.gnode .gw { font-size: 0.75rem; color: var(--muted); }
.gnode.focus { outline: 2px solid var(--core-edge); background: var(--core); }
.gnode:hover { border-color: var(--muted); }
.gedge { fill: none; stroke: var(--muted); stroke-width: 1.2; opacity: 0.45; }
.gedge.required { stroke: var(--core-edge); stroke-width: 2.2; }
.gedge.helpful { stroke: var(--ext-edge); stroke-width: 1.6; }
.gedge.context { stroke-dasharray: 4 4; }
.gedge.near { opacity: 0.9; }
@media (max-width: 560px) {
  .gnodes { gap: 8px; }
  .gnode { flex: 0 1 calc(50% - 4px); padding: 6px 8px; font-size: 0.8rem; }
}
.gkey .k { display: inline-block; width: 22px; height: 0; vertical-align: middle; margin: 0 4px 0 10px;
  border-top: 2px solid var(--muted); }
.gkey .k.required { border-top: 3px solid var(--core-edge); margin-left: 0; }
.gkey .k.helpful { border-top: 2px solid var(--ext-edge); }
.gkey .k.context { border-top: 2px dashed var(--muted); }
"""

