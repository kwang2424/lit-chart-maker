# Contributing

Disagreements are settled by sources, not by who argues loudest.

## Ways to help

1. **Review a citation.** This is the most useful thing a person can do. Every citation
   so far was checked by Claude (an AI); pages mark these "checked by Claude (AI)". Pick
   one, look up the cited passage in the edition named in `checked_in`, and confirm the
   `why` says what the source says. If it holds, add `reviewed_by: <your name>` under
   that citation. If not, fix the `locator` or the wording, or propose removing the link,
   and explain in your PR.
2. **Challenge an ordering.** Change the link and cite a source of equal or
   higher tier. If scholars genuinely disagree, keep the weaker strength and
   mention both views in the work's `note`.
3. **Add a work or a list.** Copy the structure of `lists/nietzsche.yaml`, whose header
   documents every field. A list of predecessors gets `group: predecessors` and a
   `sequence` number for its place in history.
4. **Add a source to a list's survey.** A course syllabus, an institute's reading
   list or a guide that recommends books can go in the list's `survey:` section:
   which books it includes, the first one, and whether they're in order. Mark
   beginner-only lists with `covers: beginning`, and an expert's top picks with
   `covers: shortlist`. The build turns the survey into the "What the sources say"
   section and warns when our tiers or links disagree with it. If you keep a tier
   anyway, explain why in `tier_note`.

## Rules

- Every link needs a plain-language `why` and at least one source.
- `required` links and `start_here` need an author (tier 1) or scholarly (tier 2) source.
- Core works can't have a `required` link to a non-core work, so the core
  path stands on its own.
- Quote exactly, in the wording of the edition in `checked_in`; mark cuts with "…".
- `verified: true` means the passage was read in that edition. `reviewed_by` is only for
  a person who has checked it themselves; never add it for someone else, or for an AI.
- A list can be marked `reviewed` (or `stable`) only when every citation has `reviewed_by`.
- Prefer the author's own statements, then academic guides, then syllabi and teaching lists.
  Forum lists (tier 4) are hints, not evidence.
- In YAML, quote any value containing ` #` or `: `. An unquoted ` #` starts a comment,
  so `checked_in: Project Gutenberg #1232` would silently lose its number.

## Before opening a PR

```sh
python tools/build.py               # must pass, and regenerates generated/
python -m unittest discover tools
python tools/recheck.py --list <id> # the quotes you added are in their sources
```

Commit the regenerated files along with your YAML changes. CI fails if they're out of date.
If `generated/core-paths.md` changed, say in the PR which core path moved and why.
