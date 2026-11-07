"""Reading plans across thinkers: pick the books you want to reach, get one ordered checklist.

The plan is every book the sources say to read before your goals (following links of the
chosen strength, across all lists), in an order that respects every link: earlier
thinkers first where the links leave a choice. It uses the same "read" marks as the list
pages, and the page address records the plan, so it can be bookmarked or shared.
"""

from __future__ import annotations

import json
from html import escape

import connections
import graph

# Starting points offered on an empty plan: (label, goals). Only goals that exist are shown.
PRESETS = [
    ("Being and Time", ["heidegger:being-and-time"]),
    ("Anti-Oedipus", ["deleuze:anti-oedipus"]),
    ("Discipline and Punish", ["foucault:discipline-punish"]),
    ("Of Grammatology", ["derrida:grammatology"]),
    ("Being and Nothingness", ["sartre:being-nothingness"]),
    ("The Human Condition", ["arendt:human-condition"]),
    ("Capital", ["marx:capital-1"]),
    ("Beyond the Pleasure Principle", ["freud:beyond-pleasure"]),
]


def page_body(lists: dict) -> str:
    d = graph.data(lists)
    groups = []
    for lid in connections.ordered_lists(lists):
        opts = "".join(f'<option value="{lid}:{w["id"]}">{escape(w["title"])}</option>' for w in lists[lid]["works"])
        groups.append(f'<optgroup label="{escape(lists[lid]["title"])}">{opts}</optgroup>')
    presets = "".join(
        f'<button type="button" data-goals="{",".join(g)}">{escape(label)}</button>'
        for label, g in PRESETS if all(x in d["nodes"] for x in g)
    )
    payload = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    return (
        "<h1>Make a reading plan</h1>"
        "<p>Choose the books you want to reach. The plan lists everything the sources say to read "
        "before them, across every thinker on this site, in an order that respects every link. "
        "Tick books as you read them: the marks are shared with the list pages and saved in this "
        "browser. The page address saves the plan, so you can bookmark or share it.</p>"
        '<p class="meta muted">Books marked <em>background</em> lead to your goal only through context links: '
        "useful, but you can skip them. Choose “Required + helpful” to see only the essential chain.</p>"
        '<p class="sans"><label for="pick" class="meta">Add a goal</label><br>'
        f'<select id="pick" class="gselect"><option value="">Choose a book…</option>{"".join(groups)}</select></p>'
        '<div id="goals" class="goals sans"></div>'
        f'<div id="presets" class="controls sans"><span class="meta muted">Or start with:</span>{presets}</div>'
        '<div class="controls sans" role="group" aria-label="Which links to follow">'
        '<button data-min="required" aria-pressed="false">Required only</button>'
        '<button data-min="helpful" aria-pressed="false">Required + helpful</button>'
        '<button data-min="context" aria-pressed="true">All links</button></div>'
        '<p class="sans meta"><label><input type="checkbox" id="hideread"> Hide books I\'ve read</label></p>'
        '<p id="psummary" class="sans meta"></p>'
        '<div class="bar" id="pbar" aria-hidden="true"><span></span></div>'
        '<ol id="plan" class="plan"></ol>'
        "<noscript><p>This page needs JavaScript. Each list page shows the same links under "
        "“Read first”.</p></noscript>"
        f'<script id="gdata" type="application/json">{payload}</script>'
        '<script src="plan.js"></script>'
    )


JS = r"""
(function () {
  var D = JSON.parse(document.getElementById('gdata').textContent);
  var pred = {};
  D.edges.forEach(function (e) { (pred[e.b] = pred[e.b] || []).push(e); });
  var RANK = { required: 2, helpful: 1, context: 0 };
  var S = { goals: [], min: 'context', hide: false };

  function readHash() {
    var h = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var i = kv.indexOf('='); if (i > 0) h[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
    });
    S.goals = (h.goals || '').split(',').filter(function (g) { return D.nodes[g]; });
    S.min = RANK[h.min] !== undefined ? h.min : 'context';
  }
  function writeHash() {
    var h = '#goals=' + S.goals.map(function (g) { return encodeURIComponent(g).replace(/%3A/g, ':'); }).join(',') + '&min=' + S.min;
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  try { S.hide = localStorage.getItem('plan-hide-read') === '1'; } catch (e) {}

  // "Read" marks: the same storage the list pages use, one object per list.
  var marks = {};
  function readMarks(lid) {
    if (!marks[lid]) { try { marks[lid] = JSON.parse(localStorage.getItem('read:' + lid) || '{}'); } catch (e) { marks[lid] = {}; } }
    return marks[lid];
  }
  function isRead(id) { var p = id.split(':'); return !!readMarks(p[0])[p[1]]; }
  function setRead(id, v) {
    var p = id.split(':'), m = readMarks(p[0]); m[p[1]] = v;
    try { localStorage.setItem('read:' + p[0], JSON.stringify(m)); } catch (e) {}
  }

  function ok(e) { return RANK[e.s] >= RANK[S.min]; }
  function plan() {
    var inPlan = {}, stack = S.goals.slice();
    S.goals.forEach(function (g) { inPlan[g] = 1; });
    while (stack.length) {
      var x = stack.pop();
      (pred[x] || []).forEach(function (e) { if (ok(e) && !inPlan[e.a]) { inPlan[e.a] = 1; stack.push(e.a); } });
    }
    // Order: every link respected; where free, earlier thinkers first, then earlier books.
    var ids = Object.keys(inPlan), indeg = {}, out = [];
    ids.forEach(function (id) { indeg[id] = 0; });
    var need = {};   // for each book, the plan books it is read for: [{b, e}]
    ids.forEach(function (b) {
      (pred[b] || []).forEach(function (e) {
        if (ok(e) && inPlan[e.a]) { indeg[b]++; (need[e.a] = need[e.a] || []).push(e); }
      });
    });
    function key(id) { var n = D.nodes[id]; return [D.thinkers[n.l].rank, n.y || 9999, n.t]; }
    function cmp(a, b) { var ka = key(a), kb = key(b); for (var i = 0; i < 3; i++) { if (ka[i] < kb[i]) return -1; if (ka[i] > kb[i]) return 1; } return 0; }
    var ready = ids.filter(function (id) { return !indeg[id]; }).sort(cmp);
    while (ready.length) {
      var id = ready.shift(); out.push(id);
      (need[id] || []).forEach(function (e) { if (--indeg[e.b] === 0) { ready.push(e.b); ready.sort(cmp); } });
    }
    // Essential: reaches a goal through required or helpful links only. The rest is background.
    var essential = {}, st = S.goals.slice();
    S.goals.forEach(function (g) { essential[g] = 1; });
    while (st.length) {
      var y = st.pop();
      (pred[y] || []).forEach(function (e) {
        if (RANK[e.s] >= 1 && inPlan[e.a] && !essential[e.a]) { essential[e.a] = 1; st.push(e.a); }
      });
    }
    return { order: out, need: need, essential: essential };
  }

  function url(id) { var p = id.split(':'); return p[0] + '.html#' + p[1]; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var listEl = document.getElementById('plan');
  function render() {
    writeHash();
    document.querySelectorAll('[data-min]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.min === S.min ? 'true' : 'false'); });
    document.getElementById('hideread').checked = S.hide;
    document.getElementById('presets').style.display = S.goals.length ? 'none' : '';
    var gEl = document.getElementById('goals');
    gEl.innerHTML = S.goals.map(function (g) {
      var n = D.nodes[g];
      return '<span class="chip">' + esc(n.t) + ' <span class="muted">(' + esc(D.thinkers[n.l].name) + ')</span>' +
        '<button type="button" aria-label="Remove ' + esc(n.t) + '" data-remove="' + esc(g) + '">×</button></span>';
    }).join('');

    var P = plan(), total = P.order.length, done = 0, thinkers = {};
    listEl.innerHTML = '';
    P.order.forEach(function (id, i) {
      var n = D.nodes[id], read = isRead(id), goal = S.goals.indexOf(id) >= 0;
      thinkers[n.l] = 1; if (read) done++;
      var li = document.createElement('li');
      var bg = !P.essential[id];
      li.className = 'pitem' + (read ? ' read' : '') + (goal ? ' goal' : '') + (bg ? ' bg' : '') + (S.hide && read ? ' hidden' : '');
      var why = (P.need[id] || []).map(function (e) {
        return '<li><span class="strength">' + e.s + '</span> before <a href="' + url(e.b) + '"><em>' + esc(D.nodes[e.b].t) +
          '</em></a><br><span class="meta">' + esc(e.why) + '</span></li>';
      }).join('');
      li.innerHTML =
        '<label class="done sans muted"><input type="checkbox"' + (read ? ' checked' : '') + '> read</label>' +
        '<span class="pnum sans">' + (i + 1) + '</span>' +
        '<a href="' + url(id) + '" class="ptitle">' + esc(n.t) + '</a>' +
        '<div class="sans meta muted">' + esc(D.thinkers[n.l].name) + (n.y ? ' · ' + n.y : '') +
        (n.tier === 'core' ? ' · core' : '') + (goal ? ' · <strong>your goal</strong>' : '') +
        (bg ? ' · <span class="bgtag">background</span>' : '') + '</div>' +
        (why ? '<details class="src"><summary>Why it comes first (' + (P.need[id] || []).length + ')</summary><ul class="links">' + why + '</ul></details>' : '');
      li.querySelector('input').addEventListener('change', function (ev) { setRead(id, ev.target.checked); render(); });
      listEl.appendChild(li);
    });
    var sum = document.getElementById('psummary');
    if (!S.goals.length) {
      sum.textContent = 'Add a book to start a plan.';
    } else {
      var first = P.order.filter(function (id) { return !isRead(id); })[0];
      var nbg = P.order.filter(function (id) { return !P.essential[id]; }).length;
      sum.innerHTML = total + ' book' + (total === 1 ? '' : 's') + ' from ' + Object.keys(thinkers).length + ' thinker' +
        (Object.keys(thinkers).length === 1 ? '' : 's') + (nbg ? ' (' + (total - nbg) + ' essential, ' + nbg + ' background)' : '') +
        ' · ' + done + ' read' +
        (first ? ' · next: <a href="' + url(first) + '"><em>' + esc(D.nodes[first].t) + '</em></a>' : ' · all read') +
        (total === S.goals.length && S.min !== 'context' ? '. No ' + (S.min === 'required' ? 'required' : 'required or helpful') +
          ' links lead into ' + (S.goals.length === 1 ? 'this book' : 'these books') + '; try “All links” for background reading.' : '');
    }
    document.querySelector('#pbar span').style.width = (total ? Math.round(100 * done / total) : 0) + '%';
    document.getElementById('pbar').style.display = total ? '' : 'none';
  }

  document.getElementById('pick').addEventListener('change', function (ev) {
    var v = ev.target.value;
    if (v && S.goals.indexOf(v) < 0) S.goals.push(v);
    ev.target.value = ''; render();
  });
  document.getElementById('goals').addEventListener('click', function (ev) {
    var g = ev.target.getAttribute('data-remove');
    if (g) { S.goals = S.goals.filter(function (x) { return x !== g; }); render(); }
  });
  document.querySelectorAll('#presets [data-goals]').forEach(function (b) {
    b.addEventListener('click', function () { S.goals = b.dataset.goals.split(','); render(); });
  });
  document.querySelectorAll('[data-min]').forEach(function (b) {
    b.addEventListener('click', function () { S.min = b.dataset.min; render(); });
  });
  document.getElementById('hideread').addEventListener('change', function (ev) {
    S.hide = ev.target.checked; try { localStorage.setItem('plan-hide-read', S.hide ? '1' : '0'); } catch (e) {}
    render();
  });
  window.addEventListener('hashchange', function () { readHash(); render(); });
  readHash(); render();
})();
"""

CSS = """
.goals { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
.chip { display: inline-flex; align-items: baseline; gap: 6px; padding: 4px 6px 4px 12px; border-radius: 99px;
  background: var(--core); border: 1px solid var(--core-edge); font-size: 0.85rem; max-width: 100%; }
.chip button { font: inherit; border: 0; background: none; color: var(--ink); cursor: pointer; font-size: 1.1rem;
  line-height: 1; padding: 0 4px; }
ol.plan { list-style: none; padding: 0; margin: 16px 0; }
.pitem { position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 12px 10px 48px; margin: 8px 0; }
.pitem.goal { border-color: var(--core-edge); background: var(--core); }
.pitem.read { opacity: 0.55; }
.pitem.bg { border-style: dashed; }
.pitem.bg .ptitle { font-weight: normal; }
.bgtag { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.pitem .pnum { position: absolute; left: 12px; top: 11px; min-width: 26px; height: 26px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: bold;
  background: var(--opt-edge); color: var(--bg); }
.pitem.goal .pnum { background: var(--core-edge); }
.pitem .ptitle { font-weight: bold; }
.pitem label.done { float: right; font-size: 0.8rem; cursor: pointer; margin-left: 8px; }
#pbar { max-width: 320px; }
"""
