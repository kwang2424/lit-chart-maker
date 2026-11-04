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


# Shared filter controls for the graph and the map pages.
FILTERS_HTML = (
    '<div class="controls sans" role="group" aria-label="Which links to show">'
    '<button data-min="required" aria-pressed="false">Required only</button>'
    '<button data-min="helpful" aria-pressed="true">Required + helpful</button>'
    '<button data-min="context" aria-pressed="false">All links</button></div>'
    '<p class="sans meta"><label><input type="checkbox" id="gcore"> Core books only</label></p>'
)


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
        "Tap a book to follow its own prerequisites. The filters below hide weaker links and "
        "non-core books; the page remembers your choice.</p>"
        '<p class="sans"><label for="focus" class="meta">Book</label><br>'
        f'<select id="focus" class="gselect">{"".join(groups)}</select></p>'
        + FILTERS_HTML +
        '<p class="sans meta muted gkey"><span class="k required"></span> required '
        '<span class="k helpful"></span> helpful <span class="k context"></span> context '
        '<span class="k via"></span> through hidden books</p>'
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
  var RANK = { required: 2, helpful: 1, context: 0 };

  // Filters: which link strengths count, and whether to show only core books.
  var F = { min: 'helpful', core: false };
  try { var saved = JSON.parse(localStorage.getItem('graph-filters') || 'null'); if (saved) F = saved; } catch (e) {}
  function ok(e) { return RANK[e.s] >= RANK[F.min]; }
  function shown(id, focus) { return id === focus || !F.core || D.nodes[id].tier === 'core'; }

  function ancestors(id) {
    var seen = {}, stack = [id];
    while (stack.length) {
      var x = stack.pop();
      (pred[x] || []).forEach(function (e) { if (ok(e) && !seen[e.a]) { seen[e.a] = 1; stack.push(e.a); } });
    }
    return seen;
  }
  // Nearest shown predecessors of id, walking through hidden books. Returns [{a, s, via}].
  function shownPreds(id, focus) {
    var out = {}, stack = [], seen = {};
    (pred[id] || []).forEach(function (e) { if (ok(e)) stack.push({ a: e.a, s: e.s, via: false }); });
    while (stack.length) {
      var x = stack.pop();
      if (seen[x.a]) continue;
      seen[x.a] = 1;
      if (shown(x.a, focus)) {
        if (!out[x.a] || RANK[x.s] > RANK[out[x.a].s]) out[x.a] = x;
      } else {
        (pred[x.a] || []).forEach(function (e) {
          if (ok(e)) stack.push({ a: e.a, s: RANK[e.s] < RANK[x.s] ? e.s : x.s, via: true });
        });
      }
    }
    return Object.keys(out).map(function (k) { return out[k]; });
  }
  function label(id) {
    var n = D.nodes[id], th = D.thinkers[n.l];
    return { title: n.t, who: th.name + (n.y ? ' · ' + n.y : ''), hue: Math.round(360 * th.rank / th.n) };
  }
  function url(id) { var p = id.split(':'); return p[0] + '.html#' + p[1]; }

  function render(focus) {
    if (!D.nodes[focus]) focus = D.focus;
    sel.value = focus;
    syncControls();
    var anc = ancestors(focus);
    var V = {}; V[focus] = 1;
    Object.keys(anc).forEach(function (id) { if (shown(id, focus)) V[id] = 1; });
    var E = [];
    Object.keys(V).forEach(function (b) {
      shownPreds(b, focus).forEach(function (p) { if (V[p.a]) E.push({ a: p.a, b: b, s: p.s, via: p.via }); });
    });
    var predIn = {};
    E.forEach(function (e) { (predIn[e.b] = predIn[e.b] || []).push(e.a); });
    var rank = {};
    function r(id) {
      if (rank[id] !== undefined) return rank[id];
      rank[id] = 0;
      var m = -1;
      (predIn[id] || []).forEach(function (a) { m = Math.max(m, r(a)); });
      return (rank[id] = m + 1);
    }
    Object.keys(V).forEach(r);
    var top = rank[focus];
    var next = [];
    (succ[focus] || []).forEach(function (e) {
      if (ok(e) && shown(e.b, focus) && next.indexOf(e.b) < 0) { next.push(e.b); E.push({ a: focus, b: e.b, s: e.s, via: false }); }
    });
    var layers = [];
    Object.keys(V).forEach(function (id) { (layers[rank[id]] = layers[rank[id]] || []).push(id); });
    if (next.length) layers.push(next);
    var pos = {};
    function bary(id, li) {
      var ps = li === top + 1 ? [focus] : (predIn[id] || []);
      var xs = ps.map(function (p) { return pos[p]; }).filter(function (v) { return v !== undefined; });
      return xs.length ? xs.reduce(function (s, v) { return s + v; }, 0) / xs.length : 0.5;
    }
    layers.forEach(function (ids, li) {
      ids.sort(function (a, b) {
        var ka = bary(a, li), kb = bary(b, li);
        if (ka !== kb) return ka - kb;
        var na = D.nodes[a], nb = D.nodes[b];
        return (D.thinkers[na.l].rank - D.thinkers[nb.l].rank) || ((na.y || 0) - (nb.y || 0));
      });
      ids.forEach(function (id, i) { pos[id] = ids.length > 1 ? i / (ids.length - 1) : 0.5; });
    });

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
        a.querySelector('.gw').textContent = lb.who + (!F.core && D.nodes[id].tier === 'core' ? ' · core' : '');
        wrapr.appendChild(a);
      });
      row.appendChild(wrapr);
      layersEl.appendChild(row);
    });

    var n = Object.keys(V).length - 1, hiddenN = Object.keys(anc).length - n;
    var who = {};
    Object.keys(V).forEach(function (id) { if (id !== focus) who[D.nodes[id].l] = 1; });
    var f = label(focus), nw = Object.keys(who).length;
    var txt = n
      ? n + ' book' + (n > 1 ? 's' : '') + ' before ' + f.title + ', from ' + nw + ' thinker' + (nw > 1 ? 's' : '') +
        '; the longest chain is ' + top + ' step' + (top > 1 ? 's' : '') + '.'
      : 'With these filters, the sources name nothing to read before ' + f.title + '.';
    if (hiddenN > 0) {
      var viaN = E.filter(function (e) { return e.via; }).length;
      txt += ' ' + hiddenN + ' non-core book' + (hiddenN > 1 ? 's are' : ' is') + ' hidden' +
        (viaN ? '; dotted lines run through them.' : '.');
    }
    document.getElementById('gsummary').textContent = txt;

    var ul = document.getElementById('gwhy');
    ul.innerHTML = '';
    (pred[focus] || []).filter(ok).forEach(function (e) {
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
    if (!ul.children.length) ul.innerHTML = '<li class="muted">Nothing listed with these filters.</li>';
    drawEdges(E, focus);
  }

  function drawEdges(E, focus) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var bb = box.getBoundingClientRect();
    svg.setAttribute('width', bb.width); svg.setAttribute('height', bb.height);
    svg.setAttribute('viewBox', '0 0 ' + bb.width + ' ' + bb.height);
    var el = {};
    box.querySelectorAll('.gnode').forEach(function (a) { el[a.dataset.id] = a.getBoundingClientRect(); });
    E.forEach(function (e) {
      if (!el[e.a] || !el[e.b]) return;
      var A = el[e.a], B = el[e.b];
      var x1 = A.left + A.width / 2 - bb.left, y1 = A.bottom - bb.top;
      var x2 = B.left + B.width / 2 - bb.left, y2 = B.top - bb.top;
      var dy = Math.max(24, (y2 - y1) / 2);
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + (y1 + dy) + ' ' + x2 + ',' + (y2 - dy) + ' ' + x2 + ',' + y2);
      p.setAttribute('class', 'gedge ' + e.s + (e.via ? ' via' : '') + (e.b === focus || e.a === focus ? ' near' : ''));
      svg.appendChild(p);
    });
  }

  function syncControls() {
    document.querySelectorAll('[data-min]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.min === F.min ? 'true' : 'false'); });
    var c = document.getElementById('gcore'); if (c) c.checked = !!F.core;
  }
  function setF(k, v) {
    F[k] = v;
    try { localStorage.setItem('graph-filters', JSON.stringify(F)); } catch (e) {}
    render(current());
  }
  document.querySelectorAll('[data-min]').forEach(function (b) { b.addEventListener('click', function () { setF('min', b.dataset.min); }); });
  var cb = document.getElementById('gcore'); if (cb) cb.addEventListener('change', function () { setF('core', cb.checked); });

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
.gedge.via { stroke-dasharray: 1 4; stroke-linecap: round; }
@media (max-width: 560px) {
  .gnodes { gap: 8px; }
  .gnode { flex: 0 1 calc(50% - 4px); padding: 6px 8px; font-size: 0.8rem; }
}
.gkey .k { display: inline-block; width: 22px; height: 0; vertical-align: middle; margin: 0 4px 0 10px;
  border-top: 2px solid var(--muted); }
.gkey .k.required { border-top: 3px solid var(--core-edge); margin-left: 0; }
.gkey .k.helpful { border-top: 2px solid var(--ext-edge); }
.gkey .k.context { border-top: 2px dashed var(--muted); }
.gkey .k.via { border-top: 2px dotted var(--muted); }
"""

