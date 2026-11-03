# Contributing

Disagreements are settled by sources, not by who argues loudest.

## Ways to help

1. **Verify a citation.** Find a link marked `verified: false`, check the
   cited passage in the actual text, fix the `locator` (section, page,
   edition) if needed, and set `verified: true`. If the source doesn't
   support the claim, say so in your PR and propose a fix or removal.
2. **Challenge an ordering.** Change the link and cite a source of equal or
   higher tier. If scholars genuinely disagree, keep the weaker strength and
   mention both views in the work's `note`.
3. **Add a work or a list.** Copy the structure of `lists/nietzsche.yaml`.

4. **Add a source to a list's survey.** A course syllabus, an institute's reading
   list or a guide that recommends books can go in the list's `survey:` section:
   which books it includes, the first one, and whether they're in order. Mark
   beginner-only lists with `covers: beginning`. The build turns the survey into
   the "What the sources say" section and warns when our tiers or links disagree
   with it. If you keep a tier anyway, explain why in `tier_note`.

## Rules

- Every link needs a plain-language `why` and at least one source.
- `required` links need an author (tier 1) or scholarly (tier 2) source.
- Core works can't have a `required` link to a non-core work, so the core
  path stands on its own.
- Only mark `verified: true` for passages you have personally checked.
  If you used AI to help draft anything, every citation must still be checked by a person.
- Prefer the author's own statements, then academic guides, then syllabi and teaching lists.
  Forum lists (tier 4) are hints, not evidence.
- Translations are recommendations; mention the edition you checked against.

## Before opening a PR

```sh
python tools/build.py   # must pass, and regenerates generated/
```

Commit the regenerated files along with your YAML changes. CI fails if they're out of date.
