"""Draw a reading list as a /lit/-style chart (SVG).

Layout: three columns (extended | core | optional). Works go top to bottom in
reading order; works in different columns can share a row when neither has to
come first. Solid arrows are required/helpful links, dashed are context.
"""

from __future__ import annotations

from html import escape

COLS = {"extended": 0, "core": 1, "optional": 2}
COL_LABELS = ["Extended", "Core path", "Optional & background"]
CARD_W, CARD_H = 300, 96
GAP_X, GAP_Y = 56, 34
MAX_ARROW_ROWS = 2  # longer links become an "after:" note instead of an arrow
MARGIN = 40
HEADER_H = 150
FOOTER_H = 70

THEME = {
    "bg": "#f6f1e7",
    "ink": "#1f1a14",
    "muted": "#6b6256",
    "line": "#8c8072",
    "core": ("#f4d58d", "#8a6d1f"),
    "extended": ("#d6e6f5", "#3b6a91"),
    "optional": ("#ebe7e0", "#8c8072"),
}


def wrap(text: str, width: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def layout(order: list[str], by_id: dict, hard_preds: dict) -> dict[str, tuple[int, int]]:
    """Return {work id: (column, row)}."""
    place: dict[str, tuple[int, int]] = {}
    col_next = [0, 0, 0]
    floor = 0
    for n in order:
        col = COLS[by_id[n]["tier"]]
        row = max(col_next[col], floor)
        for p in hard_preds.get(n, []):
            if p in place:
                row = max(row, place[p][1] + 1)
        place[n] = (col, row)
        col_next[col] = row + 1
        floor = row
    return place


def render_svg(data: dict, order: list[str], core_order: list[str], hard: list, soft: list, lists: dict) -> str:
    lid = data["id"]
    by_id = {w["id"]: w for w in data["works"]}
    hard_preds: dict[str, list] = {}
    for a, b in hard:
        hard_preds.setdefault(b, []).append(a)
    place = layout(order, by_id, hard_preds)
    rows = max(r for _, r in place.values()) + 1
    width = MARGIN * 2 + CARD_W * 3 + GAP_X * 2
    height = HEADER_H + rows * (CARD_H + GAP_Y) + FOOTER_H
    core_num = {n: i + 1 for i, n in enumerate(core_order)}
    full_num = {n: i + 1 for i, n in enumerate(order)}

    def xy(n):
        c, r = place[n]
        return MARGIN + c * (CARD_W + GAP_X), HEADER_H + r * (CARD_H + GAP_Y)

    t = THEME
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Georgia, \'Times New Roman\', serif">',
        "<defs>",
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["line"]}"/></marker>',
        "</defs>",
        f'<rect width="100%" height="100%" fill="{t["bg"]}"/>',
        f'<text x="{width / 2}" y="62" text-anchor="middle" font-size="38" font-weight="bold" '
        f'fill="{t["ink"]}">{escape(data["title"])}</text>',
        f'<text x="{width / 2}" y="94" text-anchor="middle" font-size="17" fill="{t["muted"]}">'
        f"A reading order. Follow the numbers; gold boxes are the core path.</text>",
    ]
    for i, label in enumerate(COL_LABELS):
        x = MARGIN + i * (CARD_W + GAP_X) + CARD_W / 2
        out.append(
            f'<text x="{x}" y="{HEADER_H - 18}" text-anchor="middle" font-size="15" '
            f'letter-spacing="2" fill="{t["muted"]}">{label.upper()}</text>'
        )

    # Links first, so cards sit on top.
    def edge(a, b, dashed):
        if a not in place or b not in place:
            return
        ax, ay = xy(a)
        bx, by = xy(b)
        x1, y1 = ax + CARD_W / 2, ay + CARD_H
        x2, y2 = bx + CARD_W / 2, by - 3
        if place[a][1] == place[b][1]:  # same row: connect sides
            left = ax < bx
            x1, y1 = (ax + CARD_W if left else ax), ay + CARD_H / 2
            x2, y2 = (bx if left else bx + CARD_W), by + CARD_H / 2
            d = f"M{x1},{y1} L{x2 - (3 if left else -3)},{y2}"
        else:
            dy = max(30, (y2 - y1) / 2)
            d = f"M{x1},{y1} C{x1},{y1 + dy} {x2},{y2 - dy} {x2},{y2}"
        style = 'stroke-dasharray="5 5" opacity="0.55"' if dashed else 'opacity="0.9"'
        out.append(
            f'<path d="{d}" fill="none" stroke="{t["line"]}" stroke-width="1.6" {style} marker-end="url(#arrow)"/>'
        )

    # Keep the picture readable: drop links implied by others, draw short ones as
    # arrows, and list long ones as an "after:" note above the card.
    succ: dict[str, set] = {}
    for a, b in hard:
        succ.setdefault(a, set()).add(b)

    def implied(a, b):
        todo = [m for m in succ.get(a, ()) if m != b]
        seen = set()
        while todo:
            m = todo.pop()
            if m == b:
                return True
            if m not in seen:
                seen.add(m)
                todo.extend(succ.get(m, ()))
        return False

    def span(a, b):
        return abs(place[b][1] - place[a][1])

    notes: dict[str, list] = {}
    hard_set = set(hard)
    for a, b in hard:
        if implied(a, b):
            continue
        if span(a, b) <= MAX_ARROW_ROWS:
            edge(a, b, False)
        else:
            notes.setdefault(b, []).append(by_id[a]["title"])
    for a, b in soft:
        if (a, b) not in hard_set and span(a, b) <= 1:
            edge(a, b, True)

    for n in order:
        w = by_id[n]
        x, y = xy(n)
        fill, stroke = t[w["tier"]]
        sw = 2.5 if w["tier"] == "core" else 1.5
        out.append(
            f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )
        badge = str(full_num[n])
        out.append(f'<circle cx="{x + 22}" cy="{y + 22}" r="14" fill="{stroke}"/>')
        out.append(
            f'<text x="{x + 22}" y="{y + 27}" text-anchor="middle" font-size="14" font-weight="bold" '
            f'fill="#fff" font-family="Helvetica, Arial, sans-serif">{badge}</text>'
        )
        title_lines = wrap(w["title"], 30, 2)
        for i, line in enumerate(title_lines):
            out.append(
                f'<text x="{x + 44}" y="{y + 27 + i * 19}" font-size="16" font-weight="bold" '
                f'fill="{t["ink"]}">{escape(line)}</text>'
            )
        sub = ", ".join(str(v) for v in (w.get("author", "").split(" (")[0], w.get("year")) if v)
        sub_y = y + 27 + len(title_lines) * 19 + 2
        if sub:
            out.append(
                f'<text x="{x + 44}" y="{sub_y}" font-size="13" fill="{t["muted"]}">{escape(wrap(sub, 38, 1)[0])}</text>'
            )
        dots = "●" * w["difficulty"] + "○" * (5 - w["difficulty"])
        tags = [f"difficulty {dots}"]
        if n in core_num:
            tags.insert(0, f"core #{core_num[n]}")
        if w.get("start_here"):
            tags.insert(0, "★ start here")
        out.append(
            f'<text x="{x + 14}" y="{y + CARD_H - 12}" font-size="12" fill="{t["muted"]}" '
            f'font-family="Helvetica, Arial, sans-serif">{escape("  ·  ".join(tags))}</text>'
        )
        ext = [
            l["work"] for l in (w.get("after") or []) if ":" in l["work"] and l.get("strength") in ("required", "helpful")
        ]
        names = list(notes.get(n, []))
        if ext or names:
            for ref in ext:
                ol, ow = ref.split(":", 1)
                other = next(x for x in lists[ol]["works"] if x["id"] == ow)
                names.append(f"{other['title']} ({lists[ol]['title'].split()[-1]})")
            out.append(
                f'<text x="{x + CARD_W - 10}" y="{y - 6}" text-anchor="end" font-size="12" font-style="italic" '
                f'fill="{t["muted"]}">{escape(wrap("after: " + "; ".join(names), 54, 1)[0])}</text>'
            )

    fy = height - FOOTER_H + 30
    out.append(
        f'<text x="{width / 2}" y="{fy}" text-anchor="middle" font-size="13" fill="{t["muted"]}">'
        f"Solid arrow: read first (required / helpful). Dashed: useful context. "
        f"Every link is sourced — see generated/{lid}.md</text>"
    )
    out.append(
        f'<text x="{width / 2}" y="{fy + 20}" text-anchor="middle" font-size="12" fill="{t["muted"]}">'
        f"Status: {escape(data['status'])} · github.com/kwang2424/reading-order-maker</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"
