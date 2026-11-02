import copy
import unittest

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

    def test_required_needs_strong_source(self):
        self.link("twilight", work="genealogy", strength="required", why="x", sources=[{"source": "forum"}])
        self.assertTrue(any("'required' link needs" in e for e in errors(self.bad, self.sources)))

    def test_core_cannot_depend_on_noncore(self):
        self.link("zarathustra", work="birth-of-tragedy", strength="helpful", why="x",
                  sources=[{"source": "sep-nietzsche"}])
        self.assertTrue(any("core work can't depend" in e for e in errors(self.bad, self.sources)))

    def test_unknown_refs(self):
        self.link("gay-science", work="nope", strength="context", why="x", sources=[{"source": "missing"}])
        errs = errors(self.bad, self.sources)
        self.assertTrue(any("unknown work" in e for e in errs))
        self.assertTrue(any("unknown source" in e for e in errs))

    def test_order_respects_hard_links(self):
        data = self.lists["nietzsche"]
        _, full = b.compute_order(data)
        pos = {n: i for i, n in enumerate(full)}
        for a, c in b.hard_edges(data["works"], "nietzsche"):
            self.assertLess(pos[a], pos[c], f"{a} should come before {c}")

    def test_stable_requires_verified(self):
        self.bad["nietzsche"]["status"] = "stable"
        self.assertTrue(any("not yet verified" in e for e in errors(self.bad, self.sources)))


if __name__ == "__main__":
    unittest.main()
