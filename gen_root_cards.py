#!/usr/bin/env python3
"""Generate a sheet of flash cards, one per root, as a single SVG.

Each card follows ~/DailyPurge/RootCard.svg: the Latin form in bold across the
top, the Han character large in the middle, and the two glosses stacked at the
bottom.  Cards are laid out on a grid (14 x 14 by default, which is exactly the
196 roots); if the roots ever outgrow one page, extra pages are stacked below
with a gap between them.

Usage:  python3 gen_root_cards.py [-o root_cards.svg] [--cols 14] [--rows 14]
"""

import argparse
import csv
from xml.sax.saxutils import escape

import pikotika

# --- card geometry, in points, copied from RootCard.svg -------------------
CELL_W, CELL_H = 82, 106      # one grid cell, card plus its margin
MARGIN = 5                    # gap from cell edge to card edge
CARD_W, CARD_H = 72, 96
CORNER = 12
STROKE = 2

# One very light pastel per category, spread around the hue wheel so that
# categories landing next to each other on the sheet (roots.tsv is sorted by
# category) never share a neighborhood of hue.  Particles keep the original
# neutral gray -- they are not a semantic field like the rest.
FILL = "#EBEBEB"
CATEGORY_FILL = {
    "Body and life": "#FBDFDF",
    "Color": "#D4FADD",
    "Feelings": "#FAD4F8",
    "Food": "#FAEAD4",
    "General heads": "#FBDFEC",
    "Grammar and logic": "#F5D4FA",
    "Made things": "#FAFBDF",
    "Material": "#D4FAF8",
    "Nature": "#E6FBDF",
    "Particles": FILL,
    "People and society": "#FAE0D4",
    "Places, arts, appearance": "#F1FBDF",
    "Qualities": "#E8D4FA",
    "Quantity": "#DFE3FB",
    "Shape": "#FAF3D4",
    "Space and direction": "#DFF4FB",
    "Time direction": "#D4E4FA",
    "Verbs": "#E5DFFB",
}

CX = MARGIN + CARD_W / 2      # card center line
LATIN_Y = 22.5                # baseline of the Latin form
HAN_Y = 64.5                  # baseline of the Han character
GLOSS_Y1, GLOSS_Y2 = 82.5, 94.5   # baselines of the two glosses
GLOSS_Y_SOLO = 88.5           # baseline when there is only one gloss

LATIN_SIZE = 11
HAN_SIZE = 36
GLOSS_SIZE = 11
TEXT_MAX_W = CARD_W - 6       # shrink text that would touch the border

SANS = "Arial, Helvetica, sans-serif"
SANS_BOLD = SANS
HAN_FONT = "Hiragino Sans, Hiragino Sans GB, Noto Sans CJK JP, sans-serif"

CARD_PATH = (
    "M{x0},{y0} L{x1},{y0} C{c1},{y0} {x2},{c2} {x2},{y1} "
    "L{x2},{y2} C{x2},{c3} {c1},{y3} {x1},{y3} "
    "L{x0},{y3} C{c0},{y3} {xl},{c3} {xl},{y2} "
    "L{xl},{y1} C{xl},{c2} {c0},{y0} {x0},{y0} z"
)


def card_outline():
    """Rounded-rect path for one card, in card-local coordinates."""
    left, top = MARGIN, MARGIN
    right, bottom = left + CARD_W, top + CARD_H
    k = CORNER * 0.4477  # cubic approximation of a quarter circle
    return CARD_PATH.format(
        xl=left, x0=left + CORNER, x1=right - CORNER, x2=right,
        y0=top, y1=top + CORNER, y2=bottom - CORNER, y3=bottom,
        c0=left + k, c1=right - k, c2=top + k, c3=bottom - k,
    )


def fitted_size(text, size):
    """Back off the font size for the few strings too wide for a card."""
    if not text:
        return size
    width = len(text) * size * 0.55  # Arial averages a bit over half an em
    if width <= TEXT_MAX_W:
        return size
    return round(size * TEXT_MAX_W / width, 2)


def text_el(s, y, size, family, bold=False):
    weight = ' font-weight="bold"' if bold else ""
    return (
        f'<text x="{CX}" y="{y}" text-anchor="middle" '
        f'font-family="{family}" font-size="{fitted_size(s, size)}"'
        f'{weight} fill="#000000">{escape(s)}</text>'
    )


def card(root):
    """SVG fragment for one card, drawn at the origin of its own cell."""
    fill = CATEGORY_FILL.get(root["category"], FILL)
    parts = [f'<path d="{card_outline()}" fill="{fill}" stroke="#000000" '
             f'stroke-width="{STROKE}"/>']
    parts.append(text_el(root["form"], LATIN_Y, LATIN_SIZE, SANS_BOLD, bold=True))
    if root["han"]:
        parts.append(text_el(root["han"], HAN_Y, HAN_SIZE, HAN_FONT))
    glosses = [g.replace("_", " ") for g in (root["gloss"], root["gloss2"]) if g]
    if len(glosses) == 1:
        parts.append(text_el(glosses[0], GLOSS_Y_SOLO, GLOSS_SIZE, SANS))
    else:
        for gloss, y in zip(glosses, (GLOSS_Y1, GLOSS_Y2)):
            parts.append(text_el(gloss, y, GLOSS_SIZE, SANS))
    return parts


def build(roots, cols, rows):
    per_page = cols * rows
    pages = (len(roots) + per_page - 1) // per_page
    page_h = rows * CELL_H
    gap = CELL_H // 2
    width = cols * CELL_W
    height = pages * page_h + (pages - 1) * gap

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
    ]
    for i, root in enumerate(roots):
        page, slot = divmod(i, per_page)
        row, col = divmod(slot, cols)
        x = col * CELL_W
        y = page * (page_h + gap) + row * CELL_H
        out.append(f'  <g transform="translate({x}, {y})">')
        out.extend("    " + p for p in card(root))
        out.append("  </g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default="root_cards.svg")
    ap.add_argument("--cols", type=int, default=14)
    ap.add_argument("--rows", type=int, default=14)
    args = ap.parse_args()

    with open("roots.tsv", newline="", encoding="utf-8") as f:
        roots = list(csv.DictReader(f, **pikotika.TSV))

    svg = build(roots, args.cols, args.rows)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{len(roots)} cards -> {args.out}")


if __name__ == "__main__":
    main()
