""""Find it": where to get each book: free online, borrow online, your library, nearby libraries.

Static links are written into the page, so they work without JavaScript:
  - Open Library (the matched work, from sources/openlibrary.yaml)
  - WorldCat (libraries near you that hold it)

When a reader opens "Find it", the page script checks, from their browser:
  - Open Library: whether the book can be read free or borrowed online
  - Libby (OverDrive): e-book and audiobook availability at the reader's chosen library
    (NYPL and other large systems listed below, or any Libby library code)
and, for NYPL, Brooklyn and Boston, links to their print catalogues. Nothing is sent anywhere
except those public catalogue searches; the chosen library is kept in the browser.
"""

from __future__ import annotations

import json
from html import escape
from urllib.parse import quote, quote_plus

import build as b
from openlibrary import OUT as OL_FILE, main_title, surname

# Libby library codes (checked against OverDrive's public library API). Readers can enter any other.
LIBRARIES = [
    ("nypl", "New York Public Library"),
    ("brooklyn", "Brooklyn Public Library"),
    ("queens", "Queens Public Library"),
    ("lapl", "Los Angeles Public Library"),
    ("chipublib", "Chicago Public Library"),
    ("sfpl", "San Francisco Public Library"),
    ("spl", "Seattle Public Library"),
    ("bpl", "Boston Public Library"),
    ("dcpl", "DC Public Library"),
    ("multcolib", "Multnomah County Library"),
    ("denver", "Denver Public Library"),
]


def load_ol() -> dict:
    if not OL_FILE.exists():
        return {}
    return {e["work"]: e.get("ol") for e in (b.load_yaml(OL_FILE) or [])}


def load_pages() -> dict:
    """Typical page count per book (median across its Open Library editions), where known."""
    if not OL_FILE.exists():
        return {}
    return {e["work"]: e["pages"] for e in (b.load_yaml(OL_FILE) or []) if e.get("pages")}


def entry(lid: str, w: dict, ol: dict) -> dict:
    t, a = main_title(w["title"]), surname(w.get("author", ""))
    return {"t": t, "a": a, "ol": ol.get(f"{lid}:{w['id']}")}


def data(lists: dict) -> dict:
    import topics                        # here, not at the top: topics imports this module
    ol = load_ol()
    out = {f"{lid}:{w['id']}": entry(lid, w, ol) for lid, d in lists.items() for w in d["works"]}
    for tid, t in topics.load().items():
        for w in t.get("works") or []:
            out[f"{tid}:{w['id']}"] = entry(tid, w, ol)
    return out


def worldcat(t: str, a: str) -> str:
    return "https://search.worldcat.org/search?q=" + quote_plus(f"ti:{t}" + (f" au:{a}" if a else ""))


def static_html(key: str, e: dict) -> str:
    """The "Find it" box with links that need no script; the script adds live checks."""
    links = []
    if e["ol"]:
        links.append(f'<a class="olstatic" href="https://openlibrary.org/works/{escape(e["ol"])}">Open Library</a>')
    links.append(f'<a href="{escape(worldcat(e["t"], e["a"]))}">Libraries near you (WorldCat)</a>')
    return (f'<details class="find sans" data-find="{escape(key)}"><summary>Find it</summary>'
            f'<div class="findlive meta"></div><p class="meta">{" · ".join(links)}</p></details>')


def script_data(lists: dict) -> str:
    payload = {"books": data(lists), "libraries": LIBRARIES}
    return "window.FIND = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"


JS = r"""
(function () {
  var F = window.FIND || { books: {}, libraries: [] };
  var KEY = 'libby-library';
  function lib() { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } }
  function setLib(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function plain(s) { return String(s || '').toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, ' ').trim().replace(/^(the|a|an) /, ''); }
  function libName(code) {
    for (var i = 0; i < F.libraries.length; i++) if (F.libraries[i][0] === code) return F.libraries[i][1];
    return code;
  }
  function getJSON(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }

  function openLibrary(b) {
    if (!b.ol) return Promise.resolve('');
    return getJSON('https://openlibrary.org/search.json?q=key:/works/' + b.ol + '&fields=ebook_access&limit=1')
      .then(function (d) {
        var a = ((d.docs || [])[0] || {}).ebook_access, url = 'https://openlibrary.org/works/' + b.ol;
        if (a === 'public') return '<li><span class="ok">Read free online</span> · <a href="' + url + '">Open Library</a></li>';
        if (a === 'borrowable') return '<li><span class="ok">Borrow online</span> (free account) · <a href="' + url + '">Open Library</a></li>';
        return '<li class="muted">Not readable online at Open Library</li>';
      }).catch(function () { return ''; });
  }

  function libby(b, code) {
    if (!code) return Promise.resolve('');
    var q = b.t + (b.a ? ' ' + b.a : '');
    var link = 'https://libbyapp.com/search/' + encodeURIComponent(code) + '/search/query-' + encodeURIComponent(q) + '/page-1';
    return getJSON('https://thunder.api.overdrive.com/v2/libraries/' + encodeURIComponent(code) + '/media?query=' + encodeURIComponent(q) + '&perPage=12')
      .then(function (d) {
        var t = plain(b.t), a = plain(b.a);
        var hits = (d.items || []).filter(function (x) {
          var title = plain(x.title), who = plain(x.firstCreatorName || '');
          return (title === t || title.indexOf(t + ' ') === 0) && (!a || who.indexOf(a) >= 0);
        });
        var name = esc(libName(code));
        if (!hits.length) return '<li class="muted">Not in ' + name + "'s e-books · <a href=\"" + link + '">search Libby</a></li>';
        var byType = {};
        hits.forEach(function (x) {
          var k = (x.type && x.type.id) === 'audiobook' ? 'audiobook' : 'e-book';
          var s = byType[k] || (byType[k] = { avail: 0, owned: 0, holds: 0, now: false });
          s.avail += x.availableCopies || 0; s.owned += x.ownedCopies || 0; s.holds += x.holdsCount || 0;
          s.now = s.now || !!x.isAvailable;
        });
        var parts = Object.keys(byType).map(function (k) {
          var s = byType[k];
          if (s.now) return '<span class="ok">' + k + ' available</span>' + (s.owned ? ' (' + s.avail + ' of ' + s.owned + ')' : '');
          return k + ': on hold' + (s.holds ? ' (' + s.holds + ' waiting)' : '');
        });
        return '<li>' + name + ': ' + parts.join(', ') + ' · <a href="' + link + '">open in Libby</a></li>';
      }).catch(function () { return '<li class="muted">Couldn\'t reach Libby · <a href="' + link + '">search Libby</a></li>'; });
  }

  // Print catalogues (links only: these catalogues don't let other sites read their copy counts).
  var PRINT = {
    nypl: ['NYPL print', [['branch catalogue', 'https://borrow.nypl.org/search?query={q}&searchType=everything'],
                          ['research libraries', 'https://www.nypl.org/research/research-catalog/search?q={q}']]],
    brooklyn: ['Brooklyn print', [['catalogue', 'https://borrow.bklynlibrary.org/search?query={q}&searchType=everything']]],
    bpl: ['Boston print', [['catalogue', 'https://bpl.bibliocommons.com/v2/search?query={q}&searchType=smart']]]
  };
  function nypl(b, code) {
    var pc = PRINT[code];
    if (!pc) return '';
    var q = encodeURIComponent(b.t + (b.a ? ' ' + b.a : ''));
    return '<li>' + pc[0] + ': ' + pc[1].map(function (l) {
      return '<a href="' + l[1].replace('{q}', q) + '">' + l[0] + '</a>';
    }).join(' · ') + '</li>';
  }

  function picker(code) {
    var opts = '<option value="">Choose your library…</option>' + F.libraries.map(function (l) {
      return '<option value="' + l[0] + '"' + (l[0] === code ? ' selected' : '') + '>' + esc(l[1]) + '</option>';
    }).join('') + '<option value="__other">Other (Libby code)…</option>';
    return '<label class="libpick">Library: <select class="libsel">' + opts + '</select></label>';
  }

  function fill(box) {
    var key = box.getAttribute('data-find'), b = F.books[key], live = box.querySelector('.findlive');
    if (!b || !live) return;
    var code = lib();
    live.innerHTML = picker(code) + '<ul class="findres"><li class="muted">Checking…</li></ul>';
    live.querySelector('.libsel').addEventListener('change', function (ev) {
      var v = ev.target.value;
      if (v === '__other') {
        v = (window.prompt('Your library\'s Libby code (the word after libbyapp.com/library/):') || '').trim().toLowerCase();
      }
      setLib(v);
      document.querySelectorAll('details.find[open]').forEach(fill);
    });
    var st = box.querySelector('.olstatic');
    Promise.all([openLibrary(b), libby(b, code)]).then(function (r) {
      if (st && r[0]) { st.style.display = 'none'; if (st.nextSibling && st.nextSibling.nodeType === 3) st.nextSibling.textContent = ''; }
      live.querySelector('.findres').innerHTML = (r[0] + r[1] + nypl(b, code)) ||
        '<li class="muted">Choose a library to check its e-books.</li>';
    });
  }

  function attach(root) {
    (root || document).querySelectorAll('details.find').forEach(function (d) {
      if (d.dataset.bound) return;
      d.dataset.bound = '1';
      d.addEventListener('toggle', function () { if (d.open) fill(d); });
    });
  }
  window.FindIt = { attach: attach, html: function (key) {
    var b = F.books[key]; if (!b) return '';
    var wc = 'https://search.worldcat.org/search?q=' + encodeURIComponent('ti:' + b.t + (b.a ? ' au:' + b.a : ''));
    return '<details class="find sans" data-find="' + esc(key) + '"><summary>Find it</summary><div class="findlive meta"></div>' +
      '<p class="meta">' + (b.ol ? '<a class="olstatic" href="https://openlibrary.org/works/' + b.ol + '">Open Library</a> · ' : '') +
      '<a href="' + wc + '">Libraries near you (WorldCat)</a></p></details>';
  } };
  attach(document);
})();
"""

CSS = """
details.find { margin: 8px 0 2px; font-size: 0.85rem; }
details.find summary { cursor: pointer; color: var(--link); }
details.find .libpick { display: block; margin: 6px 0; }
details.find select { font: inherit; max-width: 100%; padding: 2px 4px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--surface); color: var(--ink); }
ul.findres { padding-left: 1.1em; margin: 4px 0; }
ul.findres li { margin: 3px 0; }
"""
