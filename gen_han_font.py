#!/usr/bin/env python3
"""Build the Pikotika Han web font from Noto Sans CJK JP.

The whole language uses fewer than 200 characters, so a subset is tens of
kilobytes rather than the source face's several megabytes.

One font, not two.  The earlier plan was a second @font-face with a
`unicode-range` for the particles, on the assumption that a CJK face would not
have them.  It very nearly does: Noto Sans CJK JP already covers *every*
character in the `han` column plus `>` and U+21D2, and misses only U+22A2 (the
turnstile, *RI*).  So we subset the face, convert its CFF outlines to `glyf`,
and draw the one missing glyph ourselves out of the font's own stroke weights
-- which is a better visual match than any second face could be, and leaves the
site with a single file and no per-codepoint fallback to get wrong.

Why Noto Sans CJK JP and not Noto Sans JP from Google Fonts: the `han` column
mixes Japanese shinjitai (体, 楽, 図) with characters outside the JIS
repertoire (车, 边, 选, 贝, 风), and only the full CJK face has both.

The build is hermetic: it reads `vendor/`, not a font you happen to have
installed.  What is vendored is not the 110 MB `NotoSansCJK.ttc` -- that would
grow the repository thirtyfold for a build-time asset -- but a CFF subset of it
per weight, holding exactly the characters Pikotika uses plus the two glyphs
the turnstile is measured against.  Some 40 KB each, and every outline is the
original, so the built font is identical either way.

Adding a root with a new Han character is the one thing the vendored source
cannot cover.  Then you need the full face again:

    python3 gen_han_font.py --vendor  re-cut vendor/ from NotoSansCJK.ttc

Get it from https://github.com/notofonts/noto-cjk/releases ("Noto Sans CJK"
all-in-one OTC) into ~/Library/Fonts/ or private/fonts/.  Licensed OFL 1.1;
both the vendored subsets and the shipped font are derived works, and carry the
license beside them.

    python3 gen_han_font.py           build into web/fonts/
    python3 gen_han_font.py --check   verify coverage only, write nothing
"""

import argparse
import csv
import io
import sys
from pathlib import Path

from fontTools import subset
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont, newTable

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "web" / "fonts"
# Build input, deliberately not under web/ -- everything there gets copied to
# the published site, and the source subsets are not for shipping.
VENDOR_DIR = ROOT / "vendor"

SOURCE_CANDIDATES = [
    Path.home() / "Library/Fonts/NotoSansCJK.ttc",
    Path("/Library/Fonts/NotoSansCJK.ttc"),
    Path("/System/Library/Fonts/NotoSansCJK.ttc"),
    ROOT / "private/fonts/NotoSansCJK.ttc",
]

# Everything a line of Han needs beyond the roots themselves.  `>` (TE) is
# ASCII but belongs to the notation, so it comes from this face rather than the
# body one.  0 and 1 are here because the `han` column only carries 2-9 as root
# characters -- 一 is the *root* one, while a numeral like 30 is written in
# digits, and 0 and 1 appear in no root at all.  Names stay in Latin inside Han
# text on purpose and are left to the body face; that contrast is the point.
EXTRA = "⊢⇒>01 .,;:?!"

# postscript name of the face inside the .ttc -> our output basename
FACES = [
    ("Noto Sans CJK JP Regular", "regular", 400, "Regular"),
    ("Noto Sans CJK JP Bold", "bold", 700, "Bold"),
]


def vendor_path(slug: str) -> Path:
    return VENDOR_DIR / f"NotoSansCJKjp-{slug}.subset.otf"


def stable(font: TTFont) -> TTFont:
    """Stop fontTools stamping head.modified with the current time on save.

    Without this the same inputs give a different file every run, the committed
    .woff2 churns in git on every rebuild, and there is no way to tell a real
    change from a rebuild.  The timestamp the source face carries is kept."""
    font.recalcTimestamp = False
    return font

FAMILY = "Pikotika Han"

# ---------------------------------------------------------------------------
# The turnstile, U+22A2.
#
# Not drawn to taste: every dimension is measured out of the face being built,
# so the glyph carries that weight's own color and sits on its own math axis.
# A hand-tuned outline would be right in Regular and wrong in Bold.
#
#   U+2212 MINUS SIGN  gives the arm -- its thickness, its horizontal extent,
#                      and (as its vertical center) the math axis
#   U+22A5 UP TACK     gives the overall height, so ⊢ is the same size as the
#                      relation it is a rotation of
#
# The stem comes out a hair thinner than the arm, which is the relationship
# U+22A5's own two strokes have (68 against 69 at Regular).
STEM_TO_ARM = 68 / 69

MINUS, UP_TACK = 0x2212, 0x22A5

# Full width, like the Han it stands beside.
ADVANCE = 1000


def turnstile_outline(font: TTFont):
    """Measure the source face and return the ⊢ contour, clockwise (which is
    the TrueType direction for an outer contour)."""
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()

    def bounds(codepoint):
        name = cmap.get(codepoint)
        if name is None:
            raise SystemExit(f"source face has no U+{codepoint:04X}; "
                             "cannot measure the turnstile")
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        return pen.bounds

    x0, y0, x1, y1 = bounds(MINUS)
    arm = y1 - y0
    axis = (y0 + y1) / 2
    height = bounds(UP_TACK)[3] - bounds(UP_TACK)[1]

    stem = round(arm * STEM_TO_ARM)
    top = round(axis + height / 2)
    bottom = round(axis - height / 2)
    x_stem = x0 + stem

    return [
        (x0, top), (x_stem, top), (x_stem, y1), (x1, y1),
        (x1, y0), (x_stem, y0), (x_stem, bottom), (x0, bottom),
    ]


def wanted_chars() -> set:
    path = ROOT / "roots.tsv"
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t",
                                quoting=csv.QUOTE_NONE, quotechar=None)
        chars = {row["han"] for row in reader if row["han"]}
    missing_han = [c for c in chars if len(c) != 1]
    if missing_han:
        raise SystemExit(f"han column has multi-character cells: {missing_han}")
    return chars | set(EXTRA)


def find_full_face() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path
    raise SystemExit(
        "cannot find NotoSansCJK.ttc.  Install the all-in-one OTC from\n"
        "  https://github.com/notofonts/noto-cjk/releases\n"
        "into ~/Library/Fonts/, or drop it in private/fonts/.\n"
        "Looked in:\n  " + "\n  ".join(str(p) for p in SOURCE_CANDIDATES))


def source_codepoints(chars) -> set:
    """What a source face must carry: everything we ship except the turnstile,
    which is drawn, plus the two glyphs it is drawn from."""
    return {ord(c) for c in chars if c != "⊢"} | {MINUS, UP_TACK}


def load_face(ps_name: str, slug: str, chars) -> TTFont:
    """The vendored subset if it covers what we need, the full face otherwise.

    The fallback exists for exactly one situation -- a new root brought a Han
    character the vendored cut predates -- and it says so, because the fix is to
    re-cut vendor/ and commit it, not to keep building off a local font."""
    needed = source_codepoints(chars)
    path = vendor_path(slug)
    if path.exists():
        font = stable(TTFont(str(path)))
        absent = needed - set(font.getBestCmap())
        if not absent:
            return font
        print(f"    {path.name} predates "
              + "".join(chr(c) for c in sorted(absent))
              + " -- falling back to the full face; re-run with --vendor")
    elif VENDOR_DIR.exists():
        print(f"    {path.name} is missing -- falling back to the full face")
    return open_face(find_full_face(), ps_name)


def open_face(ttc_path: Path, ps_name: str) -> TTFont:
    """One face out of the all-in-one OTC."""
    collection = TTCollection(str(ttc_path), lazy=False)
    for font in collection.fonts:
        if font["name"].getDebugName(4) == ps_name:
            # Re-serialize: a face out of a .ttc shares tables with its
            # siblings, and the subsetter wants one it can own outright.
            buf = io.BytesIO()
            stable(font).save(buf)
            buf.seek(0)
            return stable(TTFont(buf))
    have = sorted(f["name"].getDebugName(4) for f in collection.fonts)
    raise SystemExit(f"{ps_name!r} not in {ttc_path}.  Faces present:\n  "
                     + "\n  ".join(have))


def subset_face(font: TTFont, codepoints) -> None:
    options = subset.Options()
    # Vertical writing, baseline tables, and every layout feature go: this text
    # is horizontal, and nothing in Pikotika needs a substitution.
    options.drop_tables += ["BASE", "VORG", "vhea", "vmtx", "GSUB", "GPOS"]
    options.layout_features = []
    options.name_IDs = ["*"]
    options.desubroutinize = True
    options.notdef_outline = True
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)


def to_truetype(font: TTFont) -> None:
    """Convert CFF outlines to `glyf`.  Smaller here (the cubics are simple and
    there are only a couple hundred of them), and it is what lets us add a
    glyph at all -- the source is a CID-keyed CFF, which is no fun to extend."""
    order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()

    glyf = newTable("glyf")
    glyf.glyphOrder = list(order)
    glyf.glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        # reverse_direction: PostScript outer contours run counterclockwise,
        # TrueType clockwise.
        glyph_set[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyf[name] = pen.glyph()

    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    del font["CFF "]
    # The file still says OTTO until told otherwise, and a font that advertises
    # CFF outlines while carrying `glyf` is rejected outright -- by FreeType,
    # and by browsers through the WOFF2 header, which carries this through.
    font.sfntVersion = "\x00\x01\x00\x00"

    font["head"].indexToLocFormat = 0
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    maxp.numGlyphs = len(order)
    for attr in ("maxPoints", "maxContours", "maxCompositePoints",
                 "maxCompositeContours", "maxTwilightPoints", "maxStorage",
                 "maxFunctionDefs", "maxInstructionDefs", "maxStackElements",
                 "maxSizeOfInstructions", "maxComponentElements",
                 "maxComponentDepth"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1


def prune(font: TTFont) -> None:
    """Drop glyphs nothing can reach.

    A CJK face maps Ideographic Variation Sequences (a character plus a
    variation selector) to alternate shapes through a format-14 cmap subtable.
    The subsetter keeps those alternates but empties the subtable that reached
    them, so we come out with three dozen orphans and no way to type any of
    them.  Every glyph here is a simple contour -- the CFF source had no
    composites -- so removing one cannot strand a component."""
    keep = {".notdef"}
    for table in font["cmap"].tables:
        keep |= set(table.cmap.values())
    font["cmap"].tables = [t for t in font["cmap"].tables if t.cmap or t.format != 14]

    order = [name for name in font.getGlyphOrder() if name in keep]
    dropped = font["maxp"].numGlyphs - len(order)
    font.setGlyphOrder(order)
    glyf = font["glyf"]
    glyf.glyphs = {name: glyf[name] for name in order}
    glyf.glyphOrder = order
    font["hmtx"].metrics = {name: font["hmtx"][name] for name in order}
    font["maxp"].numGlyphs = len(order)
    if dropped:
        print(f"    pruned {dropped} unreachable variant glyphs")


def add_turnstile(font: TTFont, outline) -> None:
    name = "uni22A2"
    pen = TTGlyphPen(None)
    pen.moveTo(outline[0])
    for point in outline[1:]:
        pen.lineTo(point)
    pen.closePath()

    order = font.getGlyphOrder()
    if name in order:
        raise SystemExit("source face already has U+22A2 -- drop the hand-drawn one")
    font.setGlyphOrder(list(order) + [name])
    font["glyf"].glyphOrder = font.getGlyphOrder()
    font["glyf"][name] = pen.glyph()
    font["hmtx"][name] = (ADVANCE, outline[0][0])
    font["maxp"].numGlyphs = len(font.getGlyphOrder())
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[0x22A2] = name


def rename(font: TTFont, style: str, weight: int) -> None:
    """A derived subset should not claim to be Noto.  Noto's OFL carries no
    Reserved Font Name, so this is manners rather than obligation, but a font
    that says Noto and is missing 20,000 characters would be a trap."""
    full = f"{FAMILY} {style}"
    ps = f"PikotikaHan-{style}"
    name = font["name"]
    for record in list(name.names):
        if record.nameID in (1, 3, 4, 6, 16, 17):
            name.removeNames(record.nameID, record.platformID,
                             record.platEncID, record.langID)
    for name_id, value in ((1, FAMILY), (2, style), (4, full), (6, ps),
                           (16, FAMILY), (17, style)):
        name.setName(value, name_id, 3, 1, 0x409)
        name.setName(value, name_id, 1, 0, 0)
    font["OS/2"].usWeightClass = weight


def cut_vendor(chars) -> None:
    """Re-cut vendor/ from the full face.

    Outlines stay CFF and untouched -- this is a smaller copy of the source, not
    a step in the transformation -- so building from it and building from the
    110 MB original give the same file."""
    ttc_path = find_full_face()
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"cutting vendor/ from {ttc_path}")
    for ps_name, slug, _, _ in FACES:
        font = open_face(ttc_path, ps_name)
        subset_face(font, source_codepoints(chars))
        out = vendor_path(slug)
        stable(font).save(str(out))
        print(f"  {out.relative_to(ROOT)}  {out.stat().st_size:,} bytes")


def build_one(ps_name: str, slug: str, weight: int,
              style: str, chars: set, write: bool) -> None:
    font = load_face(ps_name, slug, chars)
    outline = turnstile_outline(font)

    cmap = set(font.getBestCmap())
    absent = {c for c in chars if ord(c) not in cmap} - {"⊢"}
    if absent:
        raise SystemExit(f"{ps_name}: no glyph for {sorted(absent)}")

    subset_face(font, {ord(c) for c in chars if c != "⊢"})
    to_truetype(font)
    prune(font)
    add_turnstile(font, outline)
    rename(font, style, weight)

    # Round-trip through bytes so every table is recompiled from scratch, then
    # assert coverage on the finished article rather than on our intentions.
    raw = io.BytesIO()
    stable(font).save(raw)
    raw.seek(0)
    built = stable(TTFont(raw))
    verify(built, chars, ps_name)

    built.flavor = "woff2"
    out = OUT_DIR / f"pikotika-han-{slug}.woff2"
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        built.save(out)
        print(f"  {out.relative_to(ROOT)}  {out.stat().st_size:,} bytes  "
              f"({built['maxp'].numGlyphs} glyphs)")
    else:
        sized = io.BytesIO()
        built.save(sized)
        print(f"  {out.relative_to(ROOT)}  would be {len(sized.getvalue()):,} bytes  "
              f"({built['maxp'].numGlyphs} glyphs)  [not written]")


def verify(font: TTFont, chars: set, label: str) -> None:
    """Fail the build on a missing glyph.  A tofu box ships on exactly one page
    and nobody notices for months."""
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    broken = []
    for char in sorted(chars):
        name = cmap.get(ord(char))
        if name is None:
            broken.append(f"{char} U+{ord(char):04X}: not in cmap")
        elif glyf[name].numberOfContours == 0 and not char.isspace():
            broken.append(f"{char} U+{ord(char):04X}: empty glyph {name}")
    if broken:
        raise SystemExit(f"{label}: coverage check failed\n  "
                         + "\n  ".join(broken))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="verify coverage without writing the fonts")
    ap.add_argument("--vendor", action="store_true",
                    help="re-cut vendor/ from the full NotoSansCJK.ttc")
    args = ap.parse_args()

    chars = wanted_chars()
    print(f"{len(chars)} characters from roots.tsv + particles")
    if args.vendor:
        cut_vendor(chars)
    for ps_name, slug, weight, style in FACES:
        build_one(ps_name, slug, weight, style, chars, not args.check)


if __name__ == "__main__":
    main()
