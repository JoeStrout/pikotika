#!/usr/bin/env python3
"""The Han specimen page: every character the custom font contains.

A proof sheet: every glyph at once, in both weights, generated from roots.tsv
so it cannot drift from what gen_han_font.py ships.  Open it in a browser you
have not tried yet and look -- font handling is where engines differ most, and
a tofu box is obvious to the eye.

(There was briefly an automated per-glyph check here.  It could not work: a
browser whose own CJK fallback is the face we subset from renders a missing
glyph identically to a present one, which is the common case on a machine with
Noto Sans CJK installed.  Coverage is asserted at build time instead, against
the font file itself, where it can actually be established -- see
gen_han_font.verify.)

Not in the site navigation; it lives at /specimen/ for whoever needs it.
"""

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Mirrors gen_han_font.EXTRA, minus the space, split for display.
PARTICLES = [("⊢", "RI", "ri"), ("⇒", "RI-TE", "rite"), (">", "TE", "te")]
EXTRAS = "0123456789.,;:?!"


def roots(t=None):
    with (ROOT / "roots.tsv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t",
                                quoting=csv.QUOTE_NONE, quotechar=None)
        return [r for r in reader if r["han"]]


def tile(char, label, sub=""):
    return (
        '<li class="glyph"><span class="han" data-char="{c}">{c}</span>'
        '<span class="glyph-label">{l}</span>'
        '<span class="glyph-sub">{s}</span></li>'
    ).format(c=html.escape(char), l=html.escape(label), s=html.escape(sub))


def fragment() -> str:
    rows = roots()
    out = ["<h1>Han specimen</h1>",
           '<p class="lede">Every character in Pikotika Han, generated from '
           "<code>roots.tsv</code>. If a box below is empty or shows a dotted "
           "rectangle, the font failed to load or is missing that glyph.</p>"]

    out.append("<h2>Particles</h2><ul class=\"glyphs\">")
    out += [tile(c, g, f) for c, g, f in PARTICLES]
    out.append("</ul>")

    out.append("<h2>Digits and punctuation</h2><ul class=\"glyphs\">")
    out += [tile(c, "", "") for c in EXTRAS]
    out.append("</ul>")

    out.append(f"<h2>Roots ({len(rows)})</h2><ul class=\"glyphs\">")
    out += [tile(r["han"], r["gloss"], r["form"]) for r in rows]
    out.append("</ul>")

    out.append("<h2>In running text</h2>")
    for weight, name in (("400", "Regular"), ("700", "Bold")):
        out.append(
            f'<p class="specimen-line han" style="font-weight:{weight}">'
            f'⊢ 多 好 故 為 不此 选閉. ⊢ 30 内百 雨 可. '
            f'<span class="specimen-weight">{name}</span></p>')
    return "\n".join(out)


if __name__ == "__main__":
    print(fragment())
