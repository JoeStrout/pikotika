#!/usr/bin/env python3
"""Generate a Mochi-importable Markdown deck from a level of CURRICULUM.md.

Cards are separated by "===" on a line of its own, the two sides of a card by
"---"; Mochi asks for both separators when the file is imported.

Usage:  python3 make_srs.py [level] [-o outfile]
"""

import argparse
import os
import re
import sys

import pikotika

HERE = os.path.dirname(os.path.abspath(__file__))

CARD_SEP = "==="
SIDE_SEP = "---"


# -- reading the curriculum --------------------------------------------------

def level_section(text, level):
    """The lines of "## Level <n>", up to the next "## " heading."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Level\s+%s\s*$" % level, line):
            start = i + 1
            break
    if start is None:
        sys.exit("no '## Level %s' section in CURRICULUM.md" % level)
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return lines[start:end]


def subsections(lines):
    """[(heading, [body line, ...]), ...] for the "### " headings within."""
    out = []
    for line in lines:
        if line.startswith("### "):
            out.append((line[4:].strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def comma_list(body):
    """The items of a one-line comma-separated list subsection."""
    text = " ".join(l.strip() for l in body if l.strip())
    return [item.strip() for item in text.split(",") if item.strip()]


def table_rows(body):
    """(english, gloss, latin) for each data row of a markdown table."""
    rows = []
    for line in body:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "english" or set(cells[0]) <= set("-: "):
            continue          # header row or its underline
        rows.append(tuple(cells[:3]))
    return rows


# -- rendering Pikotika ------------------------------------------------------

def strip_bold(s):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).strip()


def from_gloss(gloss, t):
    """(Latin, Han) for a single root or compound named by its gloss."""
    words = [gloss.split("-")]
    return pikotika.render_latin(words, t), pikotika.render_han(words, t)


def han_of_latin(latin, t):
    """The Han for a whole utterance written in Latin notation."""
    words, _ = pikotika.parse(latin, t)
    if not words:
        sys.exit("could not parse Latin: %r" % latin)
    return pikotika.render_han(words, t)


def find_compound(english, t):
    """The gloss for a curriculum compound name, or None.

    The curriculum names a compound by one of its English equivalents, but
    sometimes by several at once ("he/she/they"); any one of them will do.
    """
    for key in [english] + english.split("/"):
        gloss = t.compounds.get(key.strip().lower())
        if gloss:
            return gloss
    return None


def all_english(gloss, t):
    return "; ".join(t.compound_by_gloss.get(gloss, []))


# -- the cards ---------------------------------------------------------------

def card(front, back):
    return "\n".join(front) + "\n" + SIDE_SEP + "\n" + "\n".join(back)


def root_cards(gloss, t):
    root = t.gloss2root.get(gloss)
    if not root:
        sys.exit("no root %r in roots.tsv" % gloss)
    latin, han, covers = root["form"], root["han"], root["covers"]
    yield card(["# " + gloss, "### " + covers],
               ["# " + latin, "## " + han])
    yield card(["# " + latin],
               ["# " + gloss, "### " + covers, "## " + han])


def compound_cards(english, t):
    gloss = find_compound(english, t)
    if not gloss:
        sys.exit("no compound %r in compounds.tsv" % english)
    latin, han = from_gloss(gloss, t)
    meanings = all_english(gloss, t) or english
    yield card(["# " + meanings],
               ["# " + latin, "## " + han])
    yield card(["# " + latin, "## " + han],
               ["# " + meanings])


def phrase_cards(english, latin, t):
    # the curriculum's Latin is kept verbatim: it is a sentence, and rendering
    # it from the roots would lose its capitalization
    latin = strip_bold(latin)
    han = han_of_latin(latin, t)
    yield card(["# " + english],
               ["# " + latin, "## " + han])
    yield card(["# " + latin],
               ["# " + english])


def build(level, t):
    cards = []
    for heading, body in subsections(level_section(
            open(os.path.join(HERE, "CURRICULUM.md"), encoding="utf-8").read(),
            level)):
        if "root" in heading:
            for gloss in comma_list(body):
                cards += root_cards(gloss, t)
        elif "compound" in heading:
            for english in comma_list(body):
                cards += compound_cards(english, t)
        else:
            for english, _gloss, latin in table_rows(body):
                cards += phrase_cards(english, latin, t)
    return cards


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("level", nargs="?", default="1",
                    help="curriculum level to generate (default: 1)")
    ap.add_argument("-o", "--out", help="output file (default: srs_level<N>.md)")
    args = ap.parse_args(argv)

    cards = build(args.level, pikotika.Tables(HERE))
    out = args.out or "srs_level%s.md" % args.level
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(("\n" + CARD_SEP + "\n").join(cards) + "\n")
    print("%d cards -> %s" % (len(cards), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
