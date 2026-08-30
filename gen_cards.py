#!/usr/bin/env python3
"""Write the course out as importable flashcard decks, into web/files/.

Twelve files: one per level plus a "complete" set that is all five levels in
course order, each in Mochi's Markdown and in Anki's tab-separated form.

The decks are the Learn tab's decks, with the build-time repeats taken out.
`gen_lessons.py` places review deliberately -- an item comes back two to eight
lessons later because the site has no cross-session scheduler -- but Mochi and
Anki both have one, and an item imported twice becomes two cards competing to
be the same card.  So an item appears once, at the lesson that introduced it,
and a level holds only what that level taught.

One card per item, not two.  The site flips a card every time it is dealt, so
one card drills both directions; here that is the importer's job -- Mochi's
two-sided card template, or Anki's "Basic (and reversed card)" note type.  The
sides are therefore built to stand alone in either order, which is why the
hint sits on the Pikotika side: a root's mnemonic spells its form and a
compound's parse spells its roots, so either one shown as a *prompt* for the
Pikotika would hand over the answer.

Usage:  python3 gen_cards.py [-o web/files]
"""

import argparse
import os
import re

import gen_lessons

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "web", "files")

# Mochi asks for both separators when the file is imported: "===" between
# cards, "---" between the two sides of one.
CARD_SEP = "==="
SIDE_SEP = "---"

# Anki reads these two lines and stops guessing -- without them a file whose
# first field contains a comma can be split on commas, and the <br> markup is
# shown as literal text.
ANKI_HEADER = ["#separator:tab", "#html:true", "#columns:Front\tBack\tTags"]

LEVELS = [1, 2, 3, 4, 5]

# stem, label, the levels it draws from.  build.py reads this to write the
# download table on the Learn page, so the table cannot list a file that was
# never written, or miscount one that was.
SETS = ([("pikotika-level%d" % n, "Level %d" % n, {n}) for n in LEVELS]
        + [("pikotika-complete", "Complete course", set(LEVELS))])


# -- gathering ---------------------------------------------------------------

def deck(lessons, levels):
    """The cards of `levels`, in course order, each item only once.

    A lesson's `words` are the items it introduces (for a level review, the
    whole level's, which by then are all duplicates and drop out), and its
    sentence cards are pulled back out of the dealt deck -- gen_lessons
    interleaves them, and the order they were dealt in is as good as any."""
    seen = set()
    out = []
    for lesson in lessons:
        if lesson["level"] not in levels:
            continue
        for entry in lesson["words"]:
            key = ("word", entry["form"])
            if key not in seen:
                seen.add(key)
                out.append(word_card(entry, lesson["level"]))
        for card in lesson["cards"]:
            if card["k"] != "sent":
                continue
            key = ("sent", card["form"])
            if key not in seen:
                seen.add(key)
                out.append(sent_card(card, lesson["level"]))
    return out


def word_card(entry, level):
    """One root or compound, as (english, [pikotika lines], [tags])."""
    return {
        "front": gen_lessons.prompt_english(entry),
        "back": [entry["form"], entry["han"], entry["hint"]],
        "tags": ["level%d" % level, entry["kind"]],
    }


def sent_card(card, level):
    return {
        "front": card["en"],
        "back": [card["form"], card["han"], card["hint"]],
        "tags": ["level%d" % level, "sentence"],
    }


# -- Mochi -------------------------------------------------------------------

def mochi(cards):
    """Markdown, "===" between cards and "---" between their sides.

    The heading levels do the sizing: the form large, the Han a step down, and
    the hint smaller again, matching what srs_level1.md established."""
    blocks = []
    for card in cards:
        form, han, hint = card["back"]
        back = ["# " + form]
        if han:
            back.append("## " + han)
        if hint:
            back.append("### " + hint)
        blocks.append("# %s\n%s\n%s" % (card["front"], SIDE_SEP, "\n".join(back)))
    return ("\n" + CARD_SEP + "\n").join(blocks) + "\n"


# -- Anki --------------------------------------------------------------------

def anki_field(lines):
    """The Pikotika side as one HTML field.

    <br> rather than a newline: a newline would end the record, since Anki's
    text importer is line-based.  A mnemonic marks the letters that echo the
    form with `*asterisks*`, which Markdown reads for us in the Mochi file but
    which Anki would print as themselves."""
    text = "<br>".join(part for part in lines if part)
    return re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)


def anki(cards):
    out = list(ANKI_HEADER)
    for card in cards:
        out.append("\t".join([
            card["front"],
            anki_field(card["back"]),
            " ".join(["pikotika"] + card["tags"]),
        ]))
    return "\n".join(out) + "\n"


# -- writing -----------------------------------------------------------------

def decks(course=None):
    """[(stem, label, [card, ...]), ...] -- every set, in order."""
    lessons = (course or gen_lessons.build())["lessons"]
    return [(stem, label, deck(lessons, levels)) for stem, label, levels in SETS]


def write(out_dir=OUT, course=None):
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for stem, _label, cards in decks(course):
        for ext, render in (("md", mochi), ("tsv", anki)):
            path = os.path.join(out_dir, "%s.%s" % (stem, ext))
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render(cards))
            written.append((path, len(cards)))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default=OUT, help="output directory")
    args = ap.parse_args(argv)

    for path, count in write(args.out):
        print("%4d cards -> %s" % (count, os.path.relpath(path, HERE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
