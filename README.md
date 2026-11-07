# lit-chart-maker

Reading orders for philosophers and thinkers, in the spirit of the old /lit/
reading charts, but with every "read X before Y" backed by a reason and a source.

**Lists:** every list's core path is in [generated/core-paths.md](generated/core-paths.md),
and each list has its own page in `generated/` (e.g. [Nietzsche](generated/nietzsche.md),
[Kant](generated/kant.md)). The website shows them with charts, a map of how the
thinkers connect, and a "what to read first" page for any book. All lists are drafts.

## How it works

Each list is a YAML file in `lists/`. Instead of a fixed order, it records
*links* between works: "read X before Y", how much that matters, why, and
who says so. The reading order is computed from those links, so it can't
contradict itself.

- **Link strength:** `required` (Y doesn't make sense without X), `helpful`
  (X makes Y much better), `context` (nice background).
- **Tiers:** `core` (the short path), `extended`, `optional`.
- **Sources** live in `sources/sources.yaml`, ranked: 1 author's own words,
  2 scholarly guides, 3 teaching (university syllabi, institutes' reading lists), 4 community lists.
  A `required` link needs a tier 1 or 2 source.
- **Survey:** each list records what independent syllabi and guides assign and where they
  start; the build warns where our tiers or links disagree with them.
- **Links across lists** (e.g. `nietzsche:genealogy`) connect thinkers. The whole book
  graph must have no loops, so there is always somewhere to start.
- The format is documented at the top of `lists/nietzsche.yaml`; unknown field names are errors.

## Who checked what

Every citation names the edition its passage was checked in (`checked_in`). So far that
checking has been done by Claude, an AI: it read each passage and recorded where. Pages
say so ("checked by Claude (AI)"). When a person re-checks a citation they add
`reviewed_by: <name>`, and a list can be marked `reviewed` only once every citation has
been reviewed by a person. See [CONTRIBUTING.md](CONTRIBUTING.md).

Quotes are also re-checked by machine: `python tools/recheck.py` fetches every cited
source it can (encyclopedia entries, syllabi, Project Gutenberg and archive.org texts)
and confirms each quoted phrase is still there. It runs monthly on GitHub Actions.

## Website

`python tools/site.py` builds a static site into `site/`: a home page, one page per list
(chart, core path, survey, full order with "read" checkboxes saved in the browser), a map
of connections between thinkers, a "what to read first" graph for any book, and a
reading-plan page: pick the books you want to reach and get one ordered checklist across
every thinker, with the essential chain marked apart from background reading. On every
push to `main`, `.github/workflows/pages.yml` publishes it to GitHub Pages.

## Usage

```sh
pip install -r requirements.txt
python tools/build.py           # validate and regenerate generated/
python tools/build.py --check   # what CI runs
python -m unittest discover tools
python tools/site.py            # build the website into site/
python tools/recheck.py         # confirm quotes against their sources (needs network)
node tools/png.js               # optional: chart images for sharing (needs Playwright)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to add or fix a list. If you use Claude Code, the
`build-reading-list` skill in `.claude/skills/` walks through the full research method.
