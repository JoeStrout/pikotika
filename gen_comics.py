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
from html import escape
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
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


# --- episodes ---------------------------------------------------------------

def episode_dirs() -> list:
    """Every episode with a translation, in order."""
    return [d for d in sorted(SOURCE.glob("ep[0-9][0-9]_*")) if (d / "pk").is_dir()]


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
        style = dict(base)
        style.update(parse_style(para.get("style")))
        out.append((style, "".join(para.itertext())))
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


EDGE_PUNCT = "".join(pikotika.PUNCT) + "\"“”'()"


def pk_html(text, t, lettering_words, where, problems, attrs="") -> str:
    """One line of lettering as HTML: Pikotika in .pk spans, lettering bare.

    Words are judged one at a time rather than the line as a whole, so that a
    balloon reading `...mmm tis ri pos` still chips the three words it can.
    A run of Pikotika stays one span, which is what check_forms re-parses."""
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

# The faces the site ships, which are the only ones a line can be measured in.
FACE_FILES = {"Lavi": ROOT / "web" / "fonts" / "lavi-regular.woff2"}
_advances = {}


def advances(family):
    """Advance width of each character in ems, or None for a face not shipped."""
    if family not in FACE_FILES:
        return None
    if family not in _advances:
        from fontTools.ttLib import TTFont
        font = TTFont(str(FACE_FILES[family]))
        upm, hmtx = font["head"].unitsPerEm, font["hmtx"]
        _advances[family] = {cp: hmtx[glyph][0] / upm
                             for cp, glyph in font.getBestCmap().items()}
    return _advances[family]


def overrun(style: dict, text: str, box_width: float) -> float:
    """How far one line runs past its box, as a fraction of the box; 0 if it fits.

    Inkscape wraps a flowed line that is too long, and then *drops* whatever
    wrapped past the bottom of the box -- so in Inkscape the last word simply
    vanishes, while the browser shows it, wrapped onto the balloon below.
    Estimated from advance widths without kerning, which is close enough to
    catch a line that is a few percent over, as the one that prompted this was."""
    widths = advances(style.get("font-family", "").strip("'\""))
    size = length(style.get("font-size"))
    if widths is None or not size or not text.strip():
        return 0.0
    spacing = length(style.get("letter-spacing")) or 0.0
    word = length(style.get("word-spacing")) or 0.0
    total = sum(widths.get(ord(ch), 0.5) * size + spacing
                + (word if ch == " " else 0.0) for ch in text.strip())
    return max(0.0, total / box_width - 1)


# --- reading a page -------------------------------------------------------------

def read_page(svg: Path, t, lettering, problems) -> dict:
    """A page's size and its lettering, as HTML boxes and as plain lines."""
    words, boxes = lettering
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
        spans = []
        for style, text in paras:
            inner = (escape(text) if whole in boxes
                     else pk_html(text, t, words, where, problems))
            spans.append(f'<span class="ln" style="{escape(line_css(style, s))}">'
                         f'{inner or "&nbsp;"}</span>')
        region = flow_region(flow_root, where)
        for style, text in paras:
            over = overrun(style, text, region[3])
            if over:
                print(f"  warning: {where}: {text.strip()!r} is {over:.1%} wider "
                      f"than its box, so it wraps on the site -- and in Inkscape "
                      f"its last words are hidden.  Widen the box in Inkscape.")
        # One line span per paragraph, newline-separated: check_forms joins a
        # span's text without a separator, and the newline is what keeps the
        # last word of one line off the first word of the next.
        html_boxes.append(f'<div class="comic-text" style="{box_css(ctm, region, s)}">'
                          + "\n".join(spans) + "</div>")
    return {"svg": svg, "name": svg.stem, "width": width, "height": height,
            "boxes": html_boxes, "lines": lines}


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
        "title_html": pk_html(title, t, lettering[0], where, problems),
        "title_link_html": pk_html(title, t, lettering[0], where, [],
                                   attrs=' data-chip="off"'),
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
    lettering = load_lettering()
    episodes = [read_episode(d, t, lettering, problems) for d in episode_dirs()]
    out = []
    index = INDEX_FRAGMENT.read_text(encoding="utf-8")
    out.append((INDEX_URL, index.replace(INDEX_MARK, index_list(episodes)),
                "Comics — Pikotika",
                "Pepper&Carrot, David Revoy's open-source webcomic, translated "
                "into Pikotika."))
    for i, ep in enumerate(episodes):
        prev = episodes[i - 1] if i > 0 else None
        nxt = episodes[i + 1] if i + 1 < len(episodes) else None
        out.append((ep["url"], episode_fragment(ep, prev, nxt, problems),
                    f"{ep['title']} — Pepper&Carrot in Pikotika",
                    f"Pepper&Carrot episode {ep['number']}, {ep['english']}, "
                    f"translated into Pikotika. Tap any word for its meaning."))
    if problems:
        raise SystemExit(
            "comic lettering that is neither Pikotika nor listed lettering:\n  "
            + "\n  ".join(problems)
            + f"\n(fix the SVG, or add the token to "
              f"{LETTERING.relative_to(ROOT)} if it is lettering)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="re-render every page, not just the stale ones")
    render_all(ap.parse_args().force)
