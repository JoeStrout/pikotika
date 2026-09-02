#!/usr/bin/env python3
"""Build web/data/convert.json -- the tables the browser converter parses with.

`web/js/convert.js` is a port of pikotika.py's parse/render core, and a port has
two halves that can drift: the algorithms and the tables they run on.  Only the
first is worth porting.  So `pikotika.Tables` is dumped here exactly as it ends
up in memory -- the same maps, built by the same code, keyed the same way -- and
convert.js does no table building of its own.  What build.py:check_convert then
compares is the algorithms alone, which is where drift actually lives.

Not folded into lexicon.json, which every page fetches on the first word tap:
the bulk of this is the 3,000-odd poured names, and only /tools/ needs them.
Kept apart, it is a fetch the converter page makes and no other page pays for.

    python3 gen_convert.py     write web/data/convert.json
"""

import json
from pathlib import Path

import pikotika as P

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web" / "data" / "convert.json"


def build(t):
    """Every table parse() and the three renderers read, as plain JSON.

    Names come out as rows rather than as the two maps they feed, because the
    maps disagree about which row wins: `names` (English -> form) takes the last
    row for an English name, while `name_forms` (form -> English) keeps the
    first, so that a curated Tom outranks the poured Dom/Thom/Tome that spells
    the same word.  Replaying the rows in file order is the one description both
    fall out of; deriving one map from the other would have to encode the
    difference twice.
    """
    roots = {}
    for gloss, row in t.gloss2root.items():
        entry = {"form": row["form"], "han": row["han"]}
        alias = "_".join((row.get("gloss2") or "").strip().split())
        if alias:
            entry["gloss2"] = alias
        level = t.level_of(gloss)
        if level:
            entry["level"] = level
        if t.is_particle(gloss):
            entry["particle"] = 1
        # english_match prints "gloss; gloss2  (root: <full range>)" for a query
        # that is one root -- particles included -- and both strings are joined
        # from columns this file does not otherwise carry.
        entry["en"] = P.root_glosses(row)
        entry["covers"] = P.root_covers(row)
        roots[gloss] = entry

    names = []
    with open(ROOT / "names.tsv", encoding="utf-8", newline="") as fh:
        import csv
        for r in csv.DictReader(fh, **P.TSV):
            if r["form"]:
                row = [r["form"], r["EN"].strip()]
                # The sanctioned loan register rides in the same table and is
                # told apart only by `kind`, which gloss parsing now needs (a
                # loan is lowercase, so nameWins can never take it).  Carried
                # as a third cell on the few rows that have it rather than on
                # all 3,379, which are otherwise pairs.
                if (r.get("kind") or "").strip() == "loan":
                    row.append("loan")
                names.append(row)

    return {
        "roots": roots,
        "covers": {k: list(v) for k, v in t.covers.items()},
        "compounds": dict(t.compounds),
        "compoundEn": {g: list(en) for g, en in t.compound_by_gloss.items()},
        # A compound written with a root's `gloss2` -- silver is `moon-metal`,
        # wine `fruit-fire-water` -- is filed under that spelling, while
        # renderGloss produces the primary one.  Only the rows where the two
        # differ need carrying; the rest would just be a map to itself.
        "canonGloss": {canon: gloss
                       for canon, gloss in t.canon2gloss.items()
                       if canon != gloss},
        "names": names,
    }


def write(payload):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False,
                              separators=(",", ":")) + "\n",
                   encoding="utf-8")
    return OUT


if __name__ == "__main__":
    tables = P.Tables()
    data = build(tables)
    path = write(data)
    print(f"{len(data['roots'])} roots, {len(data['compounds'])} English "
          f"phrases, {len(data['names'])} name rows -> "
          f"{path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
