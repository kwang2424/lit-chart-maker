# lit-chart-maker

Reading orders for philosophers and thinkers, in the spirit of the old /lit/
reading charts, but with every "read X before Y" backed by a reason and a source.

**Lists:** [Nietzsche](generated/nietzsche.md) · [Jung](generated/jung.md) · [Heidegger](generated/heidegger.md) · [Deleuze](generated/deleuze.md),
and the predecessors they build on, in historical order: [Plato](generated/plato.md) ·
[Spinoza](generated/spinoza.md) · [Hume](generated/hume.md) · [Kant](generated/kant.md) ·
[Hegel](generated/hegel.md) · [Schopenhauer](generated/schopenhauer.md) · [Marx](generated/marx.md) ·
[Bergson](generated/bergson.md) · [Freud](generated/freud.md). All drafts.

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
- **Verification:** each citation starts as `verified: false` until a person
  checks it against the actual text. A list can only be marked `stable` once
  every citation is verified.
- Links can point to other lists, e.g. `nietzsche:genealogy`.

## Charts

`tools/build.py` also draws each list as a chart (`generated/<list>.svg`), shown
at the top of each list page. For a shareable image run `node tools/png.js`
(needs Playwright + Chromium), which writes `generated/<list>.png`.

## Website

`python tools/site.py` builds a static site into `site/`: a home page plus one
page per list, with the chart, filters (core only / unread) and a "read"
checkbox per book that's saved in the browser. On every push to `main`,
`.github/workflows/pages.yml` builds and publishes it to GitHub Pages
(Settings → Pages → Source: GitHub Actions).

## Usage

```sh
pip install -r requirements.txt
python tools/build.py           # validate and regenerate generated/*.md
python tools/build.py --check   # what CI runs
python tools/site.py            # build the website into site/
python -m unittest discover tools
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to add or fix a list. If you use Claude Code, the
`build-reading-list` skill in `.claude/skills/` walks through the full research method.
