"""Pepper&Carrot in Pikotika: the comic reader under /comics/.

David Revoy's Pepper&Carrot (https://www.peppercarrot.com) is CC BY 4.0, and
every page of it is an Inkscape SVG: the painted artwork linked in as an image,
the balloons as vector paths over it, and the lettering as flowed text.  The
Pikotika translation keeps that form -- one SVG per page, edited in Inkscape,
under comics/pepper-carrot/<episode>/pk/ -- and this module turns it into web
pages in two halves, which run at different times:

  python3 gen_comics.py   fetches the hi-res artwork each SVG links to, and
                          renders every page *without its flowed text* to WebP
                          under web/comics/.  Needs rsvg-convert and cwebp, and
                          the fonts any unflowed <text> uses (Lavi, for the
                          potion labels in episode 2).
  build.py                calls pages(), which reads the flowed text out of the
                          same SVGs and lays it over those images as HTML, so
                          every word is a chip like anywhere else on the site.

Only flowRoot text is overlaid.  Plain <text> -- a label painted onto a bottle
-- stays in the image, where rsvg-convert draws it.  Later episodes letter
their balloons in SVG 2 flowed text (`<text style="shape-inside:...">`) rather
than flowRoot, and will need that form read as well before they can be added.

Not every flowed box is Pikotika.  Sound effects, a URL, a letter of a
sound effect set on its own: those are listed in comics/pepper-carrot/
lettering.tsv and render as plain text.  Anything else that does not parse
fails the build, so a typo in a balloon cannot ship as a dead chip.
"""

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from html import escape, unescape
from pathlib import Path

import pikotika

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "comics" / "pepper-carrot"
LETTERING = SOURCE / "lettering.tsv"
IMAGES = ROOT / "web" / "comics" / "pepper-carrot"
INDEX_FRAGMENT = ROOT / "web" / "pages" / "comics.html"
INDEX_MARK = "<!--COMIC-EPISODES-->"

INDEX_URL = "/comics/"
EPISODE_URL = "/comics/pepper-carrot/{slug}/"
IMAGE_URL = "/comics/pepper-carrot/{slug}/{name}"
ART_URL = "https://www.peppercarrot.com/0_sources/{episode}/hi-res/gfx-only/{name}"
ORIGINAL_URL = "https://www.peppercarrot.com/en/webcomic/{episode}.html"

# Two renders per page: the small one is what a phone downloads.  `SIZES`
# matches main.wide -- 64rem less the side padding.
WIDTHS = (900, 1800)
SIZES = "(min-width: 64rem) 61.5rem, calc(100vw - 2.5rem)"
WEBP_QUALITY = 80

# P00 is the title strip, whose text becomes the page's <h1>.  A page shorter
# than this is a spacer strip (episode 1 ends with a 50-unit one) and is left
# out, since it would only show as a white bar in the dark theme.
SPACER_HEIGHT = 100

SVG = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
# A box labeled `lettering` in Inkscape (Object Properties > Label) is plain
# text as a whole -- for a list of real people's names, like a credits page's
# patrons, which would otherwise be a hundred rows in lettering.tsv.
INKSCAPE_LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


# --- episodes ---------------------------------------------------------------

def episode_dirs() -> list:
    """Every episode with a translation, in order."""
    return [d for d in sorted(SOURCE.glob("ep[0-9][0-9]_*")) if (d / "pk").is_dir()]


def is_draft(ep_dir: Path) -> bool:
    """An episode mid-translation: `"draft": true` in its pk/info.json keeps
    it off the site, so its untranslated English does not fail the build,
    while gen_comics still fetches and renders its artwork."""
    info = json.loads((ep_dir / "pk" / "info.json").read_text(encoding="utf-8"))
    return bool(info.get("draft"))


def slug_of(ep_dir: Path) -> str:
    return ep_dir.name.split("_")[0]                      # "ep01"


def english_title(ep_dir: Path) -> str:
    """Potion of Flight, out of ep01_Potion-of-Flight -- the upstream folder
    names are the English titles with the punctuation hyphenated away."""
    return ep_dir.name.split("_", 1)[1].replace("-s-", "'s ").replace("-", " ")


def page_svgs(ep_dir: Path) -> list:
    return sorted((ep_dir / "pk").glob("E[0-9][0-9]P[0-9][0-9].svg"))


def is_title(svg: Path) -> bool:
    return svg.stem.endswith("P00")


# --- SVG geometry -----------------------------------------------------------

def multiply(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


TRANSFORM = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def parse_transform(text):
    m = IDENTITY
    for name, args in TRANSFORM.findall(text or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix":
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0])
            n = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:
                n = multiply(multiply((1, 0, 0, 1, v[1], v[2]), n),
                             (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX":
            n = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        else:
            n = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        m = multiply(m, n)
    return m


def parse_style(text) -> dict:
    out = {}
    for decl in (text or "").split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def length(value):
    """A user-unit length out of a style value -- `64px` or `64` -- or None."""
    m = re.fullmatch(r"\s*(-?[\d.]+(?:e-?\d+)?)(px)?\s*", value or "")
    return float(m.group(1)) if m else None


def hidden(el) -> bool:
    style = parse_style(el.get("style"))
    return (style.get("display") == "none" or el.get("display") == "none"
            or style.get("visibility") == "hidden")


def page_box(root, path):
    """(min-x, min-y, width, height) of the page in user units."""
    vb = root.get("viewBox")
    if vb:
        return tuple(float(x) for x in re.split(r"[\s,]+", vb.strip()))
    w, h = length(root.get("width")), length(root.get("height"))
    if w is None or h is None:
        raise SystemExit(f"{path}: page size {root.get('width')!r} x "
                         f"{root.get('height')!r} is not in user units")
    return 0.0, 0.0, w, h


def flow_roots(root):
    """(transform, flowRoot) for every visible flowRoot, in document order."""
    found = []

    def walk(el, ctm):
        for child in el:
            if child.tag in (SVG + "defs", SVG + "metadata") or hidden(child):
                continue
            m = multiply(ctm, parse_transform(child.get("transform")))
            if child.tag == SVG + "flowRoot":
                found.append((m, child))
            elif child.tag in (SVG + "g", SVG + "a", SVG + "switch"):
                walk(child, m)

    x, y, _w, _h = page_box(root, "")
    walk(root, (1, 0, 0, 1, -x, -y))
    return found


def flow_region(flow_root, path):
    """The rectangle a flowRoot flows into: (transform, x, y, w, h)."""
    region = flow_root.find(SVG + "flowRegion")
    rect = region.find(SVG + "rect") if region is not None else None
    if rect is None:
        raise SystemExit(f"{path}: flowed text {flow_root.get('id')} flows "
                         f"into a shape that is not a rectangle, which "
                         f"gen_comics cannot place")
    return (parse_transform(rect.get("transform")),
            float(rect.get("x", 0)), float(rect.get("y", 0)),
            float(rect.get("width")), float(rect.get("height")))


def paragraphs(flow_root) -> list:
    """(style, text) for each line of a flowRoot; a flowPara's own style wins
    over the flowRoot's, as it does in Inkscape."""
    base = parse_style(flow_root.get("style"))
    out = []
    for para in flow_root.iter(SVG + "flowPara"):
        text = "".join(para.itertext())
        # Inkscape gives a flowPara with no text at all no line: a blank line
        # has to hold a space or a no-break space, as the upstream files'
        # do.  Counted as a line, an empty one Inkscape left behind after
        # an edit pushed the rest of its box down (E03P01's `komparyan`).
        if text == "":
            continue
        style = dict(base)
        style.update(parse_style(para.get("style")))
        out.append((style, text))
    return out


# --- CSS ----------------------------------------------------------------------

def num(v) -> str:
    text = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def plain_color(value, fallback):
    """A paint value CSS can use as a color; gradients fall back."""
    if not value or value.startswith("url("):
        return fallback
    return value


def line_css(style: dict, s: float) -> str:
    """Inline CSS for one line, with lengths in cqw: `s` is cqw per user unit,
    so the lettering scales with the page image it sits on."""
    css = []
    family = style.get("font-family", "").strip("'\"")
    if family:
        css.append(f"font-family:'{family}',sans-serif")
    size = length(style.get("font-size"))
    if size:
        css.append(f"font-size:{num(size * s)}cqw")
    lh = style.get("line-height", "")
    if lh.endswith("%"):
        css.append(f"line-height:{num(float(lh[:-1]) / 100)}")
    elif lh.endswith("px") and length(lh) is not None:
        css.append(f"line-height:{num(length(lh) * s)}cqw")
    elif length(lh) is not None:
        css.append(f"line-height:{lh}")
    for prop in ("font-weight", "font-style"):
        if style.get(prop, "normal") != "normal":
            css.append(f"{prop}:{style[prop]}")
    align = style.get("text-align") or {"middle": "center", "end": "end"}.get(
        style.get("text-anchor", ""), "")
    if align and align != "start":
        css.append(f"text-align:{align}")
    fill = style.get("fill", "#000000")
    css.append("color:transparent" if fill == "none"
               else f"color:{plain_color(fill, '#000000')}")
    stroke = style.get("stroke", "none")
    if stroke != "none" and not stroke.startswith("url("):
        width = length(style.get("stroke-width")) or 1.0
        css.append(f"-webkit-text-stroke:{num(width * s)}cqw {stroke}")
    for prop in ("letter-spacing", "word-spacing"):
        v = length(style.get(prop))
        if v and abs(v * s) >= 0.001:
            css.append(f"{prop}:{num(v * s)}cqw")
    return ";".join(css)


def box_css(ctm, region, s: float) -> str:
    """Place a box over the page: its rectangle's top-left carried through
    the full transform, its size in the box's own units, and the rest of the
    transform (rotation, skew, the squash Inkscape leaves behind after a
    resize) applied about that corner."""
    m, x, y, w, h = region
    a, b, c, d, e, f = multiply(ctm, m)
    css = [f"left:{num((a * x + c * y + e) * s)}cqw",
           f"top:{num((b * x + d * y + f) * s)}cqw",
           f"width:{num(w * s)}cqw", f"height:{num(h * s)}cqw"]
    if max(abs(a - 1), abs(b), abs(c), abs(d - 1)) > 1e-4:
        css.append(f"transform:matrix({num(a)},{num(b)},{num(c)},{num(d)},0,0)")
    return ";".join(css)


# --- Pikotika in the lettering -----------------------------------------------

def load_lettering():
    """(words, boxes): lettering that is not Pikotika.  A `word` entry is a
    token that may stand anywhere, a `box` entry the whole text of a box --
    for a real word set as lettering, like the lone `a` of a sound effect
    spelled out a letter at a time, which must still chip in a balloon."""
    words, boxes = set(), set()
    with LETTERING.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, **pikotika.TSV):
            if row["match"] == "word":
                words.add(row["text"])
            elif row["match"] == "box":
                boxes.add(row["text"])
            else:
                raise SystemExit(f"{LETTERING.relative_to(ROOT)}: match must be "
                                 f"`word` or `box`, not {row['match']!r}")
    return words, boxes


def load_names() -> frozenset:
    """The capitalized words of every translation in pk.po: the characters and
    places, which CLAUDE.md keeps out of names.tsv.  They render as plain text,
    with no chip, like the sound effects.  Only capitalized words, since
    `Sitas Komona` also holds the ordinary word **sitas**."""
    names = set()
    text = (SOURCE / "pk.po").read_text(encoding="utf-8")
    for value in re.findall(r'^msgstr "(.*)"$', text, re.M):
        for word in value.split():
            word = word.strip(EDGE_PUNCT)
            if word[:1].isupper():
                names.add(word)
    return frozenset(names)


# `*` is a footnote mark (`60 Ko.*`), punctuation here though not to pikotika.
EDGE_PUNCT = "".join(pikotika.PUNCT) + "\"“”'()*"


def po_entries() -> list:
    """(comments, English, Pikotika) for each pk.po entry, `comments` being
    the `#` lines just above it."""
    entries, comments = [], []
    lines = (SOURCE / "pk.po").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#"):
            comments.append(line)
        elif line.startswith("msgid "):
            english = re.fullmatch(r'msgid "(.*)"', line)
            pk = (re.fullmatch(r'msgstr "(.*)"', lines[i + 1])
                  if i + 1 < len(lines) else None)
            if english and pk and english.group(1):
                entries.append((comments, english.group(1), pk.group(1)))
            comments = []
    return entries


def is_plain_name(comments) -> bool:
    """Marked `# name` by the translator.  A plain `#` comment is the
    translator's own and survives catalog updates; `#.` lines do not."""
    return any(re.match(r"# name\b", c) for c in comments)


def plain_names() -> frozenset:
    """The words of pk.po entries marked `# name`: plain names the roots
    happen to spell -- **Kumin** 'Cumin' reads as *kum* + *in*, 'and in'.
    No rule can tell those from real coinages (**Nasyontesta** 'King' is
    *country-head* on purpose, and sits in the same CHARACTERS section), so
    the translator says which.  They are checked before the roots, as
    lettering, and render plain like any other name: no chip, no popover."""
    out = set()
    for comments, _english, pk in po_entries():
        if is_plain_name(comments):
            out.update(w.strip(EDGE_PUNCT) for w in pk.split() if w[:1].isupper())
    return frozenset(out)


def load_jargon(t) -> dict:
    """The comic's jargon: pk.po terms the roots can spell but the dictionary
    does not record, keyed by lower-case form, as (headword, English, the
    pk.po spelling).  The spelling is kept because case can decide the parse:
    **Torakan** reads as the name Tora + kan, and lower-case *torakan* does
    not parse at all.

    **akuventorotun** parses as *water-air-round*, so it chips -- but the
    lexicon would give it nothing better than that gloss for English, and as
    page prose it would be filed in Vocab as a compound.  So these ship in
    each episode page's own word list instead (page_words), which the popover
    reads first, and build.py keeps them out of lexicon.json.  A term the
    dictionary already records (**Wosapor**, *hot-taste* 'spicy') keeps its
    standing entry.  Only single-word translations count: a multi-word one
    (`Torakan ratenpeste`) needs its words given entries of their own, as
    `Dragon` is."""
    recorded = {form.lower() for form in t.form2gloss}
    for gloss in t.compound_by_gloss:
        words = pikotika.parse_gloss(gloss, t)
        if words:
            recorded.add(pikotika.render_latin(words, t).lower())
    out = {}
    for comments, english, pk in po_entries():
        form = pk.strip(EDGE_PUNCT)
        if len(pk.split()) != 1 or form.lower() in recorded:
            continue
        if is_plain_name(comments):
            continue                  # never chips; see plain_names
        words = pikotika.parse_latin(form, t)
        if words is None or len(words) != 1:
            continue                  # renders plain, like Savuran: no chip
        if len(words[0]) == 1 and pikotika.is_name(words[0][0]):
            continue                  # an ordinary name from names.tsv
        headword = form if english[:1].isupper() else form.lower()
        out[form.lower()] = (headword, english, form)
    return out


def jargon_forms(t) -> set:
    return set(load_jargon(t))


def page_words(html, t, jargon) -> dict:
    """Popover entries for the jargon a page uses, keyed as its chips are.
    Shipped in the page as `<script id="page-words">`, read by site.js."""
    import gen_lexicon

    used = set()
    for span in re.findall(r'<span class="pk"[^>]*>(.*?)</span>', html, re.S):
        for word in re.sub(r"<[^>]+>", " ", span).split():
            word = unescape(word).strip(EDGE_PUNCT).lower()
            if word in jargon:
                used.add(word)
    out = {}
    for form in sorted(used):
        headword, english, spelling = jargon[form]
        words = pikotika.parse_latin(spelling, t)
        entry = None
        # A name hiding in the parse -- **Torakan** reads as Tora + kan,
        # *Dora-can* -- is an accident of the parser, not a derivation, so
        # that entry gets its English and no parse.
        if not any(pikotika.is_name(part) for part in words[0]):
            entry = gen_lexicon.entry_for(pikotika.render_gloss(words, t), t, "comic")
        entry = entry or {}
        entry.update(form=headword, kind="comic", en=english)
        out[form] = entry
    return out


def pk_html(text, t, lettering_words, where, problems, attrs="",
            names=frozenset()) -> str:
    """One line of lettering as HTML: Pikotika in .pk spans, lettering bare.

    Words are judged one at a time rather than the line as a whole, so that a
    balloon reading `...mmm tis ri pos` still chips the three words it can.
    A run of Pikotika stays one span, which is what check_forms re-parses.
    A name is tried only after the roots, as in pikotika.name_wins: one the
    roots can spell (a compound coined as a name) chips as that compound."""
    items = []
    for piece in re.split(r"(\s+)", text):
        if not piece:
            continue
        core = piece.strip(EDGE_PUNCT)
        if piece.isspace() or not core:
            items.append(("gap", piece))
        elif core in lettering_words:
            items.append(("plain", piece))
        elif (pikotika.is_filler(core, piece[piece.index(core) + len(core):])
              or pikotika.parse_latin(core, t) is not None):
            items.append(("pk", piece))
        elif core in names:
            items.append(("plain", piece))
        else:
            problems.append(f"{where}: {core!r} in {text!r}")
            items.append(("plain", piece))

    out, run, pending = [], [], []

    def close():
        if run:
            out.append(f'<span class="pk"{attrs}>{escape("".join(run))}</span>')
            run.clear()

    for kind, piece in items:
        if kind == "gap":
            pending.append(piece)
            continue
        if kind == "pk":
            if run:
                run.extend(pending)
            else:
                out.append(escape("".join(pending)))
            run.append(piece)
        else:
            close()
            out.append(escape("".join(pending) + piece))
        pending.clear()
    close()
    out.append(escape("".join(pending)))
    return "".join(out)


# --- lines that overrun their box -------------------------------------------------

# The faces a line can be measured in: the ones the site ships, plus Arial,
# which a few credits lines use and which the site leaves to the reader's own
# system.  Arial is measured from the copy macOS installs, where there is one;
# elsewhere its boxes simply go unmeasured.
FACE_FILES = {"Lavi": ROOT / "web" / "fonts" / "lavi-regular.woff2",
              "Fondamento": ROOT / "web" / "fonts" / "fondamento-regular.woff2",
              "Arial": Path("/System/Library/Fonts/Supplemental/Arial.ttf")}
_advances = {}


def advances(family):
    """Advance width of each character in ems, or None for a face we cannot
    measure."""
    if family not in FACE_FILES or not FACE_FILES[family].exists():
        return None
    if family not in _advances:
        from fontTools.ttLib import TTFont
        font = TTFont(str(FACE_FILES[family]))
        upm, hmtx = font["head"].unitsPerEm, font["hmtx"]
        _advances[family] = {cp: hmtx[glyph][0] / upm
                             for cp, glyph in font.getBestCmap().items()}
    return _advances[family]


def line_height(style: dict, size: float) -> float:
    lh = style.get("line-height", "")
    if lh.endswith("%"):
        return float(lh[:-1]) / 100 * size
    if lh.endswith("px") and length(lh) is not None:
        return length(lh)
    if length(lh) is not None:
        return length(lh) * size
    return 1.25 * size


def wrap(paras, box_width: float):
    """Each paragraph word-wrapped to the box's width, as (text, line height,
    font size) per line, or None if it is set in a face the site does not ship.

    Inkscape wraps a flowed line that is too long, and then *drops* whatever
    wrapped past the bottom of the box -- so in Inkscape the last words simply
    vanish, while the browser shows them, spilling out of the balloon.  A line
    that wraps but still fits is no problem in either.  Estimated from advance
    widths without kerning, which is close enough to catch a box that is a few
    percent short, as the one that prompted this was.

    The last line counts one em rather than a full line height: Inkscape
    shows episode 2's one-letter sound effects in boxes 1.14 em tall, where
    a 1.25 line height would say they could not fit.  Trailing empty
    paragraphs are ignored, since a hidden empty line loses nothing."""
    paras = list(paras)
    while paras and not paras[-1][1].strip():
        paras.pop()
    out = []
    for style, text in paras:
        widths = advances(style.get("font-family", "").strip("'\""))
        size = length(style.get("font-size"))
        if widths is None or not size:
            return None
        spacing = length(style.get("letter-spacing")) or 0.0
        word_gap = length(style.get("word-spacing")) or 0.0

        def measure(s):
            return sum(widths.get(ord(ch), 0.5) * size + spacing for ch in s)

        space = measure(" ") + word_gap
        lines, run = [[]], 0.0
        for word in text.split():
            w = measure(word)
            if run and run + space + w > box_width:
                lines.append([word])
                run = w
            else:
                lines[-1].append(word)
                run += (space if run else 0.0) + w
        lh = line_height(style, size)
        out += [(" ".join(line), lh, size) for line in lines]
    return out


def hidden_lines(paras, box_width: float, box_height: float):
    """The wrapped lines that fall past the bottom of the box -- what Inkscape
    hides -- or None if the face cannot be measured."""
    lines = wrap(paras, box_width)
    if lines is None:
        return None
    used = 0.0
    for i, (_text, lh, size) in enumerate(lines):
        if used + size > box_height * 1.02:
            return [text for text, _lh, _size in lines[i:]]
        used += lh
    return []


# --- reading a page -------------------------------------------------------------

def read_page(svg: Path, t, lettering, problems) -> dict:
    """A page's size and its lettering, as HTML boxes and as plain lines."""
    words, boxes, names = lettering
    root = ET.parse(svg).getroot()
    _x, _y, width, height = page_box(root, svg)
    s = 100 / width
    where = svg.relative_to(ROOT)
    html_boxes, lines = [], []
    for ctm, flow_root in flow_roots(root):
        paras = paragraphs(flow_root)
        whole = " ".join(" ".join(text for _s, text in paras).split())
        if not whole:
            continue                  # Inkscape leaves empty flowRoots behind
        lines.append(whole)
        plain = whole in boxes or flow_root.get(INKSCAPE_LABEL) == "lettering"
        spans = []
        for style, text in paras:
            inner = (escape(text) if plain
                     else pk_html(text, t, words, where, problems, names=names))
            spans.append(f'<span class="ln" style="{escape(line_css(style, s))}">'
                         f'{inner or "&nbsp;"}</span>')
        region = flow_region(flow_root, where)
        hidden = hidden_lines(paras, region[3], region[4])
        if hidden:
            print(f"  warning: {where}: {whole[:40]!r}... runs past the bottom "
                  f"of its box, so Inkscape hides {' / '.join(hidden)!r} and the "
                  f"site spills it out of the balloon.  Resize the box in "
                  f"Inkscape; `gen_comics.py --check` lists every box.")
        # One line span per paragraph, newline-separated: check_forms joins a
        # span's text without a separator, and the newline is what keeps the
        # last word of one line off the first word of the next.
        html_boxes.append(f'<div class="comic-text" style="{box_css(ctm, region, s)}">'
                          + "\n".join(spans) + "</div>")
    return {"svg": svg, "name": svg.stem, "width": width, "height": height,
            "boxes": html_boxes, "lines": lines}


def check_sheet(ep_dir: Path) -> str:
    """Markdown: every text box of an episode, page by page in reading order,
    with its full text and whether all of it fits.  For going over the pages
    in Inkscape, where a line wrapped past the bottom of its box is simply
    not drawn, and so is easy to miss."""
    out, short = [], 0
    for svg in page_svgs(ep_dir):
        root = ET.parse(svg).getroot()
        _x, _y, width, height = page_box(root, svg)
        rows = []
        for ctm, flow_root in flow_roots(root):
            paras = paragraphs(flow_root)
            text = " / ".join(t.strip() for _s, t in paras if t.strip())
            if not text:
                continue
            m, x, y, w, h = flow_region(flow_root, svg)
            a, b, c, d, e, f = multiply(ctm, m)
            left, top = a * x + c * y + e, b * x + d * y + f
            if flow_root.get(INKSCAPE_LABEL) == "lettering":
                text = f"*(lettering)* {text[:60]}…"
            hidden = hidden_lines(paras, w, h)
            if hidden is None:
                fit = "? (font not measured)"
            elif hidden:
                fit = "**✗ hides:** " + " / ".join(hidden)
                short += 1
            else:
                fit = "✓"
            rows.append((top, left, text, fit))
        out += ["", f"## {svg.stem}", ""]
        if not rows:
            out.append("No text.")
            continue
        out += ["| # | where | text | all visible? |", "|---|---|---|---|"]
        # Reading order: rows first, then left to right.  Balloons side by side
        # rarely share an exact top, so tops are banded to 5% of the page.
        rows.sort(key=lambda r: (round(r[0] / height * 20), r[1]))
        for i, (top, left, text, fit) in enumerate(rows, 1):
            cell = text.replace("|", "\\|")
            out.append(f"| {i} | {top / height:.0%} down, {left / width:.0%} "
                       f"across | {cell} | {fit} |")
    head = [f"# {ep_dir.name}: text boxes", "",
            f"{short} box{'es' if short != 1 else ''} with hidden text. "
            "Positions are each box's top-left corner as a share of the page; "
            "the fit is estimated from the font's metrics, so trust Inkscape "
            "where they disagree."]
    return "\n".join(head + out)


def shown(page: dict) -> bool:
    return not is_title(page["svg"]) and page["height"] >= SPACER_HEIGHT


def image_names(stem: str) -> list:
    return [f"{stem}-{w}.webp" for w in WIDTHS]


# --- rendering the images (python3 gen_comics.py) --------------------------------

def artwork_href(svg: Path):
    """The href of the painted artwork an SVG links to (not a gradient)."""
    for img in ET.parse(svg).getroot().iter(SVG + "image"):
        href = img.get(XLINK_HREF) or img.get("href")
        if href and not href.startswith(("#", "data:")):
            return href
    return None


def fetch(path: Path, episode: str) -> None:
    url = ART_URL.format(episode=episode, name=path.name)
    print(f"  fetching {url}")
    part = path.with_name(path.name + ".part")
    subprocess.run(["curl", "-sSfL", "-o", str(part), url], check=True)
    part.rename(path)


def render(svg: Path, force: bool, tools: dict) -> bool:
    """Render one page without its flowed text.  False if already current."""
    href = artwork_href(svg)
    if href is None:
        raise SystemExit(f"{svg.relative_to(ROOT)}: links no artwork")
    art = (svg.parent / href).resolve()
    if not art.exists():
        fetch(art, svg.parent.parent.name)
    out_dir = IMAGES / slug_of(svg.parent.parent)
    outs = [out_dir / name for name in image_names(svg.stem)]
    newest = max(svg.stat().st_mtime, art.stat().st_mtime)
    if not force and all(o.exists() and o.stat().st_mtime >= newest for o in outs):
        return False
    text = svg.read_text(encoding="utf-8")
    # rsvg-convert does not draw flowRoot at all, but that is a gap in the
    # renderer rather than a promise, so the text is taken out explicitly.
    text = re.sub(r"<flowRoot\b.*?</flowRoot>", "", text, flags=re.S)
    # librsvg only loads files at or below the SVG's own directory, so the copy
    # it renders sits beside the artwork and links it by bare name.
    tmp = art.parent / f".render-{svg.stem}.svg"
    png = art.parent / f".render-{svg.stem}.png"
    text = text.replace(f'"{href}"', f'"{os.path.relpath(art, tmp.parent)}"')
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(text, encoding="utf-8")
        subprocess.run([tools["rsvg-convert"], "-w", str(max(WIDTHS)), "-f", "png",
                        "-o", str(png), str(tmp)], check=True)
        for width, out in zip(WIDTHS, outs):
            resize = [] if width == max(WIDTHS) else ["-resize", str(width), "0"]
            subprocess.run([tools["cwebp"], "-quiet", "-q", str(WEBP_QUALITY),
                            "-metadata", "none", *resize, str(png), "-o", str(out)],
                           check=True)
    finally:
        tmp.unlink(missing_ok=True)
        png.unlink(missing_ok=True)
    return True


def render_all(force: bool = False) -> None:
    tools = {name: shutil.which(name) for name in ("rsvg-convert", "cwebp")}
    missing = [name for name, path in tools.items() if not path]
    if missing:
        raise SystemExit(f"gen_comics needs {' and '.join(missing)} on the PATH")
    for ep_dir in episode_dirs():
        wanted = set()
        for svg in page_svgs(ep_dir):
            root = ET.parse(svg).getroot()
            if is_title(svg) or page_box(root, svg)[3] < SPACER_HEIGHT:
                continue
            wanted.update(image_names(svg.stem))
            did = render(svg, force, tools)
            print(f"  {svg.relative_to(ROOT)}" + ("" if did else "  (current)"))
        # A page renamed or dropped would otherwise keep shipping its image.
        for old in (IMAGES / slug_of(ep_dir)).glob("*.webp"):
            if old.name not in wanted:
                print(f"  removing {old.relative_to(ROOT)}")
                old.unlink()


# --- the pages (build.py) -----------------------------------------------------------

def person(entry: str) -> str:
    """`Name <url>`, as the upstream info.json writes a credit, as a link."""
    m = re.fullmatch(r"\s*(.*?)\s*<([^>]+)>\s*", entry)
    if not m:
        return escape(entry)
    return f'<a href="{escape(m.group(2))}">{escape(m.group(1))}</a>'


def credit_rows(info: dict, translation: dict) -> list:
    roles = dict(info.get("credits", {}))
    if roles.get("art") and roles.get("art") == roles.get("scenario"):
        roles = {"art and scenario": roles.pop("art"),
                 **{k: v for k, v in roles.items() if k != "scenario"}}
    rows = [(role.replace("-", " ").capitalize(), people)
            for role, people in roles.items() if people]
    rows += [("Pikotika " + role.replace("-", " "), people)
             for role, people in translation.get("credits", {}).items() if people]
    return [f"<li>{label}: {', '.join(person(p) for p in people)}</li>"
            for label, people in rows]


def read_episode(ep_dir: Path, t, lettering, problems) -> dict:
    slug = slug_of(ep_dir)
    pages = [read_page(svg, t, lettering, problems) for svg in page_svgs(ep_dir)]
    title_lines = [line for p in pages if is_title(p["svg"]) for line in p["lines"]]
    title = " ".join(title_lines)
    where = f"{ep_dir.relative_to(ROOT)}/pk/title"
    info = json.loads((ep_dir / "info.json").read_text(encoding="utf-8"))
    translation = json.loads((ep_dir / "pk" / "info.json").read_text(encoding="utf-8"))
    return {
        "dir": ep_dir, "slug": slug, "number": int(slug[2:]),
        "url": EPISODE_URL.format(slug=slug), "english": english_title(ep_dir),
        "title": title or f"Episode {int(slug[2:])}",
        "title_html": pk_html(title, t, lettering[0], where, problems,
                              names=lettering[2]),
        "title_link_html": pk_html(title, t, lettering[0], where, [],
                                   attrs=' data-chip="off"', names=lettering[2]),
        "pages": [p for p in pages if shown(p)],
        "info": info, "translation": translation,
    }


def page_figure(ep: dict, page: dict, index: int, problems: list) -> str:
    names = image_names(page["name"])
    for name in names:
        path = IMAGES / ep["slug"] / name
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT)} is missing -- run "
                            f"python3 gen_comics.py")
        elif path.stat().st_mtime < page["svg"].stat().st_mtime:
            print(f"  warning: {path.relative_to(ROOT)} is older than its SVG "
                  f"-- run python3 gen_comics.py")
    urls = [IMAGE_URL.format(slug=ep["slug"], name=n) for n in names]
    srcset = ", ".join(f"{u} {w}w" for u, w in zip(urls, WIDTHS))
    big = max(WIDTHS)
    tall = round(page["height"] * big / page["width"])
    lazy = "" if index == 1 else ' loading="lazy"'
    return "\n".join(
        [f'<figure class="comic-page">',
         f'<img src="{urls[-1]}" srcset="{srcset}" sizes="{SIZES}" width="{big}" '
         f'height="{tall}" alt="Page {index}"{lazy} decoding="async">']
        + page["boxes"] + ["</figure>"])


def episode_nav(prev, nxt) -> str:
    def link(ep, label, rel):
        if ep is None:
            return f'<span class="comic-nav-off">{label}</span>'
        return f'<a href="{ep["url"]}" rel="{rel}">{label}</a>'
    return ('<nav class="comic-nav" aria-label="Episodes">'
            f'{link(prev, "&lsaquo; Previous", "prev")}'
            f'<a href="{INDEX_URL}">All episodes</a>'
            f'{link(nxt, "Next &rsaquo;", "next")}</nav>')


def episode_fragment(ep, prev, nxt, problems) -> str:
    original = ORIGINAL_URL.format(episode=ep["dir"].name)
    published = ep["info"].get("published", "")
    nav = episode_nav(prev, nxt)
    figures = [page_figure(ep, page, i, problems)
               for i, page in enumerate(ep["pages"], 1)]
    return "\n".join([
        '<header class="comic-head">',
        f'<p class="comic-kicker"><a href="{INDEX_URL}">Pepper&amp;Carrot</a>'
        f' &middot; episode {ep["number"]}</p>',
        f'<h1 class="comic-title">{ep["title_html"]}</h1>',
        f'<p class="comic-sub">{escape(ep["english"])}</p>',
        '<p class="comic-hint">Tap any underlined word for its meaning.</p>',
        '</header>',
        nav,
        '<div class="comic-pages">',
        *figures,
        '</div>',
        nav,
        '<section class="comic-credits">',
        '<h2>Credits</h2>',
        f'<p>Episode {ep["number"]} of <a href="https://www.peppercarrot.com">'
        f'Pepper&amp;Carrot</a> by David Revoy'
        + (f', first published {escape(published)}' if published else "")
        + f'. <a href="{original}">Read the original</a>.</p>',
        '<ul>', *credit_rows(ep["info"], ep["translation"]), '</ul>',
        '<p>Pepper&amp;Carrot is licensed '
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC&nbsp;BY&nbsp;4.0</a>. '
        'This is an unofficial translation, not affiliated with or endorsed by '
        'the Pepper&amp;Carrot project: its text has been translated and '
        'relettered, and the artwork is otherwise unchanged.</p>',
        '<p>Pepper&amp;Carrot is funded by its readers. If you enjoy it, '
        'consider supporting David Revoy at '
        '<a href="https://www.peppercarrot.com">peppercarrot.com</a>.</p>',
        '</section>',
    ])


def index_list(episodes) -> str:
    rows = [f'<li><a href="{ep["url"]}"><span class="comic-list-num">'
            f'{ep["number"]}</span> {ep["title_link_html"]}</a>'
            f'<span class="comic-list-en">{escape(ep["english"])}</span></li>'
            for ep in episodes]
    return '<ol class="comic-list">\n' + "\n".join(rows) + "\n</ol>"


def pages(t) -> list:
    """(url, content, <title>, description) for /comics/ and every episode.

    Kept out of build.authored_pages on purpose: a page there has its
    sentences queued for audio, and a comic's lines are not course material."""
    problems = []
    words, boxes = load_lettering()
    # A name marked `# name` in pk.po counts as lettering outright -- checked
    # before the roots get their try, so an accidental parse never chips.
    lettering = (words | plain_names(), boxes, load_names())
    episodes = [read_episode(d, t, lettering, problems)
                for d in episode_dirs() if not is_draft(d)]
    out = []
    index = INDEX_FRAGMENT.read_text(encoding="utf-8")
    out.append((INDEX_URL, index.replace(INDEX_MARK, index_list(episodes)),
                "Comics — Pikotika",
                "Pepper&Carrot, David Revoy's open-source webcomic, translated "
                "into Pikotika."))
    jargon = load_jargon(t)
    for i, ep in enumerate(episodes):
        prev = episodes[i - 1] if i > 0 else None
        nxt = episodes[i + 1] if i + 1 < len(episodes) else None
        fragment = episode_fragment(ep, prev, nxt, problems)
        words = page_words(fragment, t, jargon)
        if words:
            data = json.dumps(words, ensure_ascii=False).replace("</", "<\\/")
            fragment += (f'\n<script type="application/json" id="page-words">'
                         f'{data}</script>')
        out.append((ep["url"], fragment,
                    f"{ep['title']} — Pepper&Carrot in Pikotika",
                    f"Pepper&Carrot episode {ep['number']}, {ep['english']}, "
                    f"translated into Pikotika. Tap any word for its meaning."))
    if problems:
        raise SystemExit(
            "comic lettering that is not Pikotika, a name in pk.po, or listed "
            "lettering:\n  "
            + "\n  ".join(problems)
            + f"\n(fix the SVG, or add the token to "
              f"{LETTERING.relative_to(ROOT)} if it is lettering)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="re-render every page, not just the stale ones")
    ap.add_argument("--check", metavar="EPISODE",
                    help="instead of rendering, print a table of every text box "
                         "in EPISODE (ep03, or its folder name) and whether its "
                         "text fits")
    args = ap.parse_args()
    if args.check:
        found = [d for d in episode_dirs() if args.check in (slug_of(d), d.name)]
        if not found:
            raise SystemExit(f"no translated episode {args.check!r}")
        print(check_sheet(found[0]))
    else:
        render_all(args.force)
