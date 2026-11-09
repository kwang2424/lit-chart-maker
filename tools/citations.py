"""Who checked each citation, and how that is shown.

A citation records `verified: true` once its passage has been read in the edition
named in `checked_in`. So far that reading has been done by Claude (an AI), not by a
person. A person who re-checks a citation adds `reviewed_by: <their name>`.

  sources:
    - source: sep-hobbes
      locator: "§1 Life and Works"
      verified: true                 # the passage was read and supports the claim
      checked_in: SEP entry, accessed 2026-11
      reviewed_by: Jane Doe          # optional: a person has checked it too

A list can be marked `reviewed` or `stable` only once every citation has a
`reviewed_by`.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

AI_CHECKER = "Claude (AI)"


def claims(data: dict) -> list[dict]:
    """Every claim in a list that carries `sources`: links, start_here notes and tips."""
    out = []
    for w in data.get("works") or []:
        out += list(w.get("after") or [])
        if w.get("start_here"):
            out.append(w["start_here"])
        out += list(w.get("tips") or [])
    if data.get("beginner"):
        out.append(data["beginner"])
    return out


def all_cites(data: dict) -> list[dict]:
    """Every citation in a list, including survey entries (each is itself a citation)."""
    cites = [c for cl in claims(data) for c in (cl.get("sources") or [])]
    return cites + list(data.get("survey") or [])


def counts(data: dict) -> dict:
    cites = all_cites(data)
    return {
        "total": len(cites),
        "checked": sum(1 for c in cites if c.get("verified")),
        "reviewed": sum(1 for c in cites if c.get("verified") and c.get("reviewed_by")),
    }


def summary(data: dict) -> str:
    """One line for page headers, e.g. '24 citations · 24 checked by Claude (AI) · 0 reviewed by a person'."""
    n = counts(data)
    ai = n["checked"] - n["reviewed"]
    parts = [f"{n['total']} citations"]
    if ai:
        parts.append(f"{ai} checked by {AI_CHECKER}")
    parts.append(f"{n['reviewed']} reviewed by a person")
    if n["checked"] < n["total"]:
        parts.append(f"{n['total'] - n['checked']} not yet checked")
    return " · ".join(parts)


def mark_text(c: dict) -> str:
    if not c.get("verified"):
        return "⚠️ not yet checked"
    if c.get("reviewed_by"):
        return f"✓ reviewed by {c['reviewed_by']} in {c['checked_in']}"
    return f"✓ checked by {AI_CHECKER} in {c['checked_in']}; not yet reviewed by a person"


def mark_html(c: dict) -> str:
    if not c.get("verified"):
        return '<span class="warn">⚠ not yet checked</span>'
    if c.get("reviewed_by"):
        return (f'<span class="ok">✓ reviewed by {escape(c["reviewed_by"])}</span> '
                f'<span class="muted">in {escape(c["checked_in"])}</span>')
    return (f'<span class="ai">✓ checked by {AI_CHECKER}</span> '
            f'<span class="muted">in {escape(c["checked_in"])}; not yet reviewed by a person</span>')


def validate(data: dict, report) -> None:
    lid = data["id"]
    for c in all_cites(data):
        if c.get("reviewed_by") and not c.get("verified"):
            report.error(f"{lid}: citation '{c.get('source')}' has reviewed_by but is not verified")
    if data.get("status") in ("reviewed", "stable"):
        n = counts(data)
        if n["reviewed"] < n["total"]:
            report.error(f"{lid}: status '{data['status']}' needs every citation reviewed by a person "
                         f"({n['reviewed']}/{n['total']} have reviewed_by)")


REPO_URL = "https://github.com/kwang2424/lit-chart-maker"


def review_url(where: str, claim_text: str, c: dict, source: dict) -> str:
    """A pre-filled 'Review a citation' issue (form in .github/ISSUE_TEMPLATE/citation-review.yml)."""
    label = f"{where} — {source.get('author', '')}, {source.get('title', '')}".strip(", ")
    params = {
        "template": "citation-review.yml",
        "title": f"Citation review: {where} ({c.get('source')})",
        "citation": f"{where} | source: {c.get('source')}",
        "claim": " ".join((claim_text or "").split())[:1500],
        "locator": f"{c.get('locator', '')} — {label}"[:300],
    }
    return f"{REPO_URL}/issues/new?{urlencode(params)}"
