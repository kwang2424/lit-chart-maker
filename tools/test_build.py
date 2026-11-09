import copy
import re
import unittest
import xml.dom.minidom

import chart
import citations
import consensus
import recheck
import findit
import graph
import plan
import topics
import verify_claims

import build as b


def load():
    r = b.Report()
    sources = b.load_sources(r)
    lists = b.load_lists(r)
    sources["forum"] = {"id": "forum", "tier": 4, "title": "A forum post"}
    return lists, sources


def errors(lists, sources):
    r = b.Report()
    b.validate(lists, sources, r, strict=False)
    return r.errors


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.lists, self.sources = load()
        self.bad = copy.deepcopy(self.lists)
        self.works = {w["id"]: w for w in self.bad["nietzsche"]["works"]}

    def link(self, wid, **kw):
        self.works[wid].setdefault("after", []).append(kw)

    def test_real_lists_are_valid(self):
        self.assertEqual(errors(self.lists, self.sources), [])

    def test_cycle(self):
        self.link("bge", work="genealogy", strength="helpful", why="x", sources=[{"source": "forum"}])
        self.assertTrue(any("circular" in e for e in errors(self.bad, self.sources)))

    def test_cycle_across_lists(self):
        # Birth of Tragedy builds on a book in another list; making that book come after
        # Birth of Tragedy closes a loop that no single list's check can see.
        nz_bt = next(l["work"] for l in self.works["birth-of-tragedy"].get("after") or [] if ":" in l["work"])
        src_list, src_work = nz_bt.split(":")
        target = {w["id"]: w for w in self.bad[src_list]["works"]}[src_work]
        target.setdefault("after", []).append(
            {"work": "nietzsche:birth-of-tragedy", "strength": "context", "why": "x", "sources": [{"source": "forum"}]})
        self.assertTrue(any("circular ordering across lists" in e for e in errors(self.bad, self.sources)))

    def test_graph_data_covers_every_link(self):
        d = graph.data(self.lists)
        self.assertEqual(len(d["edges"]), len(list(b.global_edges(self.lists))))
        for e in d["edges"]:
            self.assertIn(e["a"], d["nodes"])
            self.assertIn(e["b"], d["nodes"])
        self.assertIn(d["focus"], graph.linked(self.lists))

    def test_required_needs_strong_source(self):
        self.link("twilight", work="genealogy", strength="required", why="x", sources=[{"source": "forum"}])
        self.assertTrue(any("needs an author (tier 1)" in e for e in errors(self.bad, self.sources)))

    def test_core_cannot_depend_on_noncore(self):
        self.link("zarathustra", work="untimely", strength="required", why="x",
                  sources=[{"source": "sep-nietzsche"}])
        self.assertTrue(any("core work can't depend" in e for e in errors(self.bad, self.sources)))

    def test_unknown_refs(self):
        self.link("gay-science", work="nope", strength="context", why="x", sources=[{"source": "missing"}])
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("unknown work" in e for e in errs))
        self.assertTrue(any("unknown source" in e for e in errs))

    def test_cross_list_links(self):
        self.assertEqual(errors(self.lists, self.sources), [])
        d = {w["id"]: w for w in self.bad["deleuze"]["works"]}
        d["bergsonism"]["after"] = [{"work": "nietzsche:nope", "strength": "context", "why": "x",
                                     "sources": [{"source": "sep-deleuze"}]}]
        self.assertTrue(any("nietzsche:nope: unknown work" in e for e in errors(self.bad, self.sources)))

    def test_order_respects_hard_links(self):
        data = self.lists["nietzsche"]
        _, full = b.compute_order(data)
        pos = {n: i for i, n in enumerate(full)}
        for a, c in b.hard_edges(data["works"], "nietzsche"):
            self.assertLess(pos[a], pos[c], f"{a} should come before {c}")

    def test_verified_needs_checked_in(self):
        self.link("twilight", work="genealogy", strength="context", why="x",
                  sources=[{"source": "sep-nietzsche", "verified": True}])
        self.assertTrue(any("checked_in" in e for e in errors(self.bad, self.sources)))

    def test_start_here_needs_strong_source(self):
        self.works["bge"]["start_here"] = {"why": "x", "sources": [{"source": "forum"}]}
        self.assertTrue(any("start_here" in e and "tier 1" in e for e in errors(self.bad, self.sources)))

    def test_start_here_goes_first(self):
        core, _ = b.compute_order(self.lists["nietzsche"])
        self.assertTrue(self.works["twilight"].get("start_here"))
        self.assertEqual(core[0], "twilight")

    def test_charts_are_valid_svg(self):
        for lid, data in self.lists.items():
            core, full = b.compute_order(data)
            svg = chart.render_svg(data, full, core, list(b.hard_edges(data["works"], lid)),
                                   list(b.all_edges(data["works"], lid)), self.lists)
            xml.dom.minidom.parseString(svg)  # raises if malformed

    def test_survey_rules(self):
        sv = self.bad["nietzsche"]["survey"]
        sv.append({"source": "syl-bard-pl320", "includes": ["nope"], "starts_with": "gay-science"})
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("surveyed twice" in e for e in errs))
        self.assertTrue(any("unknown work 'nope'" in e for e in errs))
        self.assertTrue(any("starts_with 'gay-science' must also be in 'includes'" in e for e in errs))

    def test_survey_counts_and_beginner_lists(self):
        data = {"id": "t", "works": [], "survey": [
            {"source": "a", "includes": ["x", "y"], "starts_with": "x", "ordered": True},
            {"source": "b", "includes": ["y", "x"], "starts_with": "y", "ordered": True},
            {"source": "c", "includes": ["z"], "starts_with": "z", "covers": "beginning"},
        ]}
        st = consensus.compute(data)
        self.assertEqual(st["n"], 2)          # beginner list left out of core shares
        self.assertEqual(st["n_all"], 3)
        self.assertEqual(st["works"]["x"]["count"], 2)
        self.assertEqual(st["works"]["z"]["starts"], 1)
        self.assertEqual(st["works"]["z"]["count"], 0)
        self.assertEqual(consensus.positions(data), {"x": 0.5, "y": 0.5})

    def test_expert_shortlists_count_as_mentions_only(self):
        data = {"id": "t", "works": [], "survey": [
            {"source": "a", "includes": ["x", "y"], "ordered": True},
            {"source": "b", "includes": ["x"], "starts_with": "x", "covers": "shortlist"},
        ]}
        st = consensus.compute(data)
        self.assertEqual(st["n"], 1)          # shortlist left out of core shares
        self.assertEqual(st["n_all"], 2)
        self.assertEqual(st["works"]["x"]["count"], 1)
        self.assertEqual(st["works"]["x"]["mentions"], 2)
        self.assertEqual(st["works"]["x"]["starts"], 1)

    def test_group_rules(self):
        self.bad["plato"]["group"] = "nonsense"
        del self.bad["kant"]["sequence"]
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("plato: group must be" in e for e in errs))
        self.assertTrue(any("kant: predecessor lists need" in e for e in errs))

    def test_all_cross_list_links_resolve(self):
        for lid, data in self.lists.items():
            for w in data["works"]:
                for l in w.get("after") or []:
                    tl, tw = b.resolve(l["work"], lid)
                    self.assertIn(tw, {x["id"] for x in self.lists[tl]["works"]}, f"{lid}:{w['id']} -> {l['work']}")

    def test_stable_requires_verified(self):
        for w in self.bad["nietzsche"]["works"]:
            for l in w.get("after") or []:
                l["sources"][0]["verified"] = False
        self.bad["nietzsche"]["status"] = "stable"
        self.assertTrue(any("not yet verified" in e for e in errors(self.bad, self.sources)))

    def test_unknown_fields_are_errors(self):
        self.works["genealogy"]["tiers"] = "core"
        self.works["genealogy"]["after"][0]["sources"][0]["verifed"] = True
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("unknown field(s) tiers" in e for e in errs))
        self.assertTrue(any("unknown field(s) verifed" in e for e in errs))

    def test_reviewed_status_needs_people(self):
        self.bad["nietzsche"]["status"] = "reviewed"
        self.assertTrue(any("needs every citation reviewed by a person" in e for e in errors(self.bad, self.sources)))
        for c in citations.all_cites(self.bad["nietzsche"]):
            c["reviewed_by"] = "A. Reader"
        self.assertFalse(any("reviewed by a person" in e for e in errors(self.bad, self.sources)))

    def test_citation_labels(self):
        c = {"source": "x", "verified": True, "checked_in": "SEP entry"}
        self.assertIn("checked by Claude (AI)", citations.mark_text(c))
        c["reviewed_by"] = "A. Reader"
        self.assertIn("reviewed by A. Reader", citations.mark_text(c))
        self.assertIn("not yet checked", citations.mark_text({"source": "x"}))

    def test_no_value_is_cut_off_by_a_hash(self):
        # In YAML, " #" starts a comment, so `checked_in: Project Gutenberg #1232` silently
        # loses the number. Such values must be quoted.
        pat = re.compile(r"^\s*(?:- )?(checked_in|locator|why|text|note|title|translation|author|url): [^\"'>|\n].* #")
        for path in sorted(b.LISTS_DIR.glob("*.yaml")) + [b.SOURCES_FILE]:
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(pat.match(line), f"{path.name}:{i}: quote this value: {line.strip()}")

    def test_recheck_matching(self):
        page = recheck.normalize("He wrote: “It ought to be intelli-\ngible to all readers”, Nietzsche’s view…")
        for q in ["It ought to be intelligible to all readers", "Nietzsche's view"]:
            self.assertIn(recheck.normalize(q), page)
        self.assertEqual(recheck.fragments("the first … the second part [sic] of it"), ["the first", "the second part", "of it"])
        self.assertEqual(recheck.text_url("https://www.gutenberg.org/ebooks/1232"),
                         "https://www.gutenberg.org/cache/epub/1232/pg1232.txt")

    def test_plan_presets_exist(self):
        nodes = graph.data(self.lists)["nodes"]
        for label, goals in plan.PRESETS:
            for g in goals:
                self.assertIn(g, nodes, f"plan preset {label!r} points at a missing book")
        self.assertIn('id="plan"', plan.page_body(self.lists))

    def test_openlibrary_matches_point_at_real_works(self):
        entries = b.load_yaml(findit.OL_FILE) or []
        keys = [e["work"] for e in entries]
        self.assertEqual(len(keys), len(set(keys)), "a book is matched twice")
        books = {f"{lid}:{w['id']}" for lid, d in self.lists.items() for w in d["works"]}
        for e in entries:
            self.assertIn(e["work"], books, f"openlibrary.yaml names a missing book: {e['work']}")
            if e.get("ol"):
                self.assertRegex(e["ol"], r"^OL\d+W$")
        html = findit.static_html("hobbes:leviathan", findit.entry("hobbes", {"id": "leviathan", "title": "Leviathan", "author": "Thomas Hobbes"}, {}))
        self.assertIn("worldcat.org", html)

    def test_review_links_use_the_issue_form(self):
        form = b.ROOT / ".github" / "ISSUE_TEMPLATE" / "citation-review.yml"
        fields = {f.get("id") for f in b.load_yaml(form)["body"] if f.get("id")}
        url = citations.review_url("hobbes:leviathan -> machiavelli:prince", "a claim",
                                   {"source": "sep-hobbes", "locator": "§1"}, {"title": "x"})
        self.assertIn("template=citation-review.yml", url)
        for field in ("citation", "claim", "locator"):
            self.assertIn(field, fields)
            self.assertIn(f"{field}=", url)

    def test_second_check_records_are_well_formed(self):
        entries = b.load_yaml(verify_claims.OUT) or []
        ids = {c[0] for c in verify_claims.claims(self.lists)}
        for e in entries:
            self.assertIn(e["verdict"], verify_claims.VERDICTS, e["claim"])
            self.assertIn(e["claim"], ids, f"verification.yaml names a claim that no longer exists: {e['claim']}")
            self.assertRegex(e["hash"], r"^[0-9a-f]{8}$")
            if e["verdict"] != "supported":
                self.assertTrue(e.get("note"), f"{e['claim']}: a non-supported verdict needs a note")

    def test_beginner_picks_are_checked(self):
        self.assertEqual([e for e in errors(self.bad, self.sources) if "beginner" in e], [])
        bg = self.bad["nietzsche"]["beginner"]
        bg["work"] = "nope"
        bg["sources"][0]["verified"] = False
        self.bad["nietzsche"]["status"] = "stable"
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("(beginner): unknown work 'nope'" in e for e in errs))
        self.assertTrue(any("beginner" in e and "not yet verified" in e for e in errs))

    def test_page_counts_are_plausible(self):
        pages = findit.load_pages()
        self.assertGreater(len(pages), 300)
        known = {f"{lid}:{w['id']}" for lid, d in self.lists.items() for w in d["works"]}
        for k, n in pages.items():
            self.assertIn(k, known)
            self.assertTrue(10 <= n <= 2000, f"{k}: {n} pages")
        self.assertNotIn("locke:second-treatise", pages)     # matched to the whole Two Treatises
        self.assertIn("p", graph.data(self.lists)["nodes"]["plato:republic"])

    def test_topics_are_valid_and_ordered(self):
        r = b.Report()
        tops = topics.load()
        topics.validate(tops, self.lists, self.sources, r)
        self.assertEqual(r.errors, [])
        for tid, t in tops.items():
            c = topics.chart(t, self.lists)
            pos = {x: i for i, x in enumerate(c["order"])}
            self.assertEqual(set(pos), set(c["count"]), tid)
            for a_, c_, _, _ in c["links"]:
                self.assertLess(pos[a_], pos[c_], f"{tid}: {a_} must come before {c_}")
        bad = {"x": {"id": "x", "title": "X", "scope": "s", "courses": [
            {"source": "sep-hobbes", "includes": ["hobbes:nope"], "locator": "l", "verified": True, "checked_in": "c"}]}}
        r = b.Report()
        topics.validate(bad, self.lists, self.sources, r)
        self.assertTrue(any("unknown book" in e for e in r.errors))


if __name__ == "__main__":
    unittest.main()
