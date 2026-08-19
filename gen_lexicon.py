#!/usr/bin/env python3
"""Build web/data/lexicon.json -- the data behind word chips and Vocab search.

One entry per Pikotika word the site can show: every root, every standing
compound, every name and loan, plus any word that only appears in page prose.
Everything comes out of the tables through `pikotika.py`, so a form here cannot
disagree with the language.

The point of shipping the *parse* alongside each compound is that the browser
never has to segment anything.  `segment()` is a real algorithm with linking-e
rules, name matching, and numeral handling, and porting it to JavaScript would
mean two implementations to keep honest.  Instead the build resolves every word
the site actually uses and the client just looks them up.

    python3 gen_lexicon.py     write web/data/lexicon.json
"""

import json
from pathlib import Path

import pikotika as P

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web" / "data" / "lexicon.json"


def part_entry(gloss, t):
    """One root of a compound, as the popover shows it in the literal parse."""
    row = t.gloss2root.get(gloss)
    if row is None:
        return None
    return {
        "form": row["form"],
        "gloss": gloss,
        "en": P.root_glosses(row),
        "han": row["han"],
    }


def entry_for(gloss, t, kind):
    """A lexicon entry for one gloss word (a single root or a compound)."""
    words = P.parse_gloss(gloss, t)
    if words is None:
        return None
    form = P.render_latin(words, t)
    entry = {
        "form": form,
        "kind": kind,
        "gloss": gloss,
        "han": P.render_han(words, t),
        # max_level reads "3 (home)" -- the level, and which root sets it.  The
        # parenthetical is for us, not for a popover; keep the number.
        "level": (P.max_level(words, t) or "").split(" (")[0],
    }

    roots = t.gloss_roots(gloss)
    if roots and len(roots) > 1:
        parts = [part_entry(r, t) for r in roots]
        if all(parts):
            entry["parts"] = parts

    english = t.compound_by_gloss.get(gloss)
    if english:
        entry["en"] = "; ".join(english)
    else:
        row = t.gloss2root.get(gloss)
        entry["en"] = P.root_glosses(row) if row else gloss
        # A root has no parse to show, so the popover shows its mnemonic
        # instead.  The etymology column stays out of the lexicon: it is for a
        # full entry, not for a chip you tapped in the middle of a sentence.
        if row and row.get("mnemonic"):
            entry["mnemonic"] = row["mnemonic"]
    return entry


def name_entries(t):
    for form, english in sorted(t.name_forms.items()):
        # names.tsv marks the sanctioned loan register with kind=loan; both ride
        # in the same table and both stay in Latin inside Han text
        yield form, {
            "form": form,
            "kind": "name",
            "gloss": english,
            "en": english,
            "han": "",
            "level": "",
        }


def build(t, extra_forms=()):
    """The standing lexicon, plus any word only page prose uses.

    A page is free to write a compound that is not in compounds.tsv -- an
    example built in running speech is not a dictionary entry.  Those get
    resolved here so that every chip on the site has something to open."""
    words = {}

    for gloss in t.gloss2root:
        kind = "particle" if t.is_particle(gloss) else "root"
        entry = entry_for(gloss, t, kind)
        if entry:
            words[entry["form"].lower()] = entry

    for gloss in t.compound_by_gloss:
        entry = entry_for(gloss, t, "compound")
        if entry:
            words.setdefault(entry["form"].lower(), entry)

    for form, entry in name_entries(t):
        words.setdefault(form.lower(), entry)

    unresolved = []
    for form in extra_forms:
        if form.lower() in words:
            continue
        parsed = P.parse_latin(form, t)
        if parsed is None:
            unresolved.append(form)
            continue
        gloss = P.render_gloss(parsed, t)
        entry = entry_for(gloss, t, "phrase")
        if entry is None:
            unresolved.append(form)
            continue
        entry["form"] = form
        words[form.lower()] = entry

    return words, unresolved


def write(words):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"count": len(words), "words": words}
    OUT.write_text(json.dumps(payload, ensure_ascii=False,
                              separators=(",", ":"), sort_keys=True) + "\n",
                   encoding="utf-8")
    return OUT


if __name__ == "__main__":
    tables = P.Tables()
    lexicon, missing = build(tables)
    path = write(lexicon)
    print(f"{len(lexicon)} words -> {path.relative_to(ROOT)} "
          f"({path.stat().st_size:,} bytes)")
    if missing:
        raise SystemExit(f"unresolved: {missing}")
