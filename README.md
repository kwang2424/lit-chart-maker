# reading-order-maker

Reading orders for philosophers and thinkers, in the spirit of the old /lit/
reading charts, but with every "read X before Y" backed by a reason and a source.

**Lists:** [Nietzsche](generated/nietzsche.md) · [Deleuze](generated/deleuze.md) (both drafts). Jung is planned.

## How it works

Each list is a YAML file in `lists/`. Instead of a fixed order, it records
*links* between works: "read X before Y", how much that matters, why, and
who says so. The reading order is computed from those links, so it can't
contradict itself.

- **Link strength:** `required` (Y doesn't make sense without X), `helpful`
  (X makes Y much better), `context` (nice background).
- **Tiers:** `core` (the short path), `extended`, `optional`.
- **Sources** live in `sources/sources.yaml`, ranked: 1 author's own words,
  2 scholarly guides, 3 university syllabi, 4 community lists.
  A `required` link needs a tier 1 or 2 source.
- **Verification:** each citation starts as `verified: false` until a person
  checks it against the actual text. A list can only be marked `stable` once
  every citation is verified.
- Links can point to other lists, e.g. `nietzsche:genealogy`.

## Charts

`tools/build.py` also draws each list as a chart (`generated/<list>.svg`), shown
at the top of each list page. For a shareable image run `node tools/png.js`
(needs Playwright + Chromium), which writes `generated/<list>.png`.

## Usage

```sh
pip install -r requirements.txt
python tools/build.py           # validate and regenerate generated/*.md
python tools/build.py --check   # what CI runs
python -m unittest discover tools
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to add or fix a list.
