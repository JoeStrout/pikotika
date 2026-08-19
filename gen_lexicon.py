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


def subruns(parts):
    """Every contiguous run of `parts`, longest first, as tuples.

    `contains_run` asks "do these roots appear in that word, side by side?", so
    an index keyed on every such run answers it by lookup.  613 entries against
    376 corpus rows is small either way; what this really buys is that the
    corpus is walked once instead of once per word."""
    n = len(parts)
    for i in range(n):
        for j in range(i + 1, n + 1):
            yield tuple(parts[i:j])


def usage_index(t):
    """(sentences, run -> sentence indices) over the whole corpus.

    Sentences are shipped once in a list and referred to by index.  Written into
    each entry instead, the common roots would carry the same string dozens of
    times and the file would be several times its size."""
    sentences, by_run = [], {}
    for row in t.corpus:
        index = len(sentences)
        sentences.append([row["latin"], row["EN"]])
        for word in row["gloss"].split():
            parts = t.gloss_roots(word)
            if not parts:
                continue
            for run in subruns(parts):
                by_run.setdefault(run, set()).add(index)
    return sentences, by_run


def compound_index(t):
    """run -> the Latin forms of the standing compounds built around it.

    A compound never lists itself, which is the `!= parts` in `compound_hits`;
    here that is the run that spans the whole word."""
    by_run = {}
    for gloss, parts in t.compound_roots.items():
        form = P.join_latin([t.form_of(g) for g in parts])
        whole = tuple(parts)
        for run in subruns(parts):
            if run == whole:
                continue
            by_run.setdefault(run, set()).add(form)
    return by_run


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


def entry_for(gloss, t, kind, usage=None):
    """A lexicon entry for one gloss word (a single root or a compound).

    `usage` is (sentences_by_run, compounds_by_run) from the indexes above; pass
    it and the entry also carries where the word is used."""
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
        # The Vocab page searches the sense range and groups by `category`, so
        # both ride along; strokes is for the Han character in the detail view.
        # `covers` holds only what the glosses do not already name, so what
        # ships is the joined range -- see pikotika.root_covers.
        if row:
            entry["covers"] = P.root_covers(row)
            for key, out in (("category", "cat"),
                             ("strokes", "strokes"), ("gloss2", "gloss2")):
                if row.get(key):
                    entry[out] = row[key]

    if usage:
        by_sentence, by_compound = usage
        run = tuple(t.gloss_roots(gloss) or ())
        used_in = sorted(by_compound.get(run, ()))
        if used_in:
            entry["in"] = used_in
        examples = sorted(by_sentence.get(run, ()))
        if examples:
            entry["ex"] = examples
    return entry


def name_entries(t):
    for form, english in sorted(t.name_forms.items()):
        # names.tsv marks the sanctioned loan register with kind=loan; both ride
        # in the same table and both stay in Latin inside Han text
        yield form, {
            "form": form,
            "kind": t.name_kind.get(form, "name"),
            "gloss": english,
            "en": english,
            "han": "",
            "level": "",
        }


def categories(t):
    """The `category` values of roots.tsv, in the order the table gives them.

    Vocab groups its browse list by these, and the table's order is editorial --
    body and life first, grammar words last -- so it is kept, not sorted."""
    out = []
    for row in t.gloss2root.values():
        cat = row.get("category")
        if cat and cat not in out:
            out.append(cat)
    return out


def build(t, extra_forms=()):
    """The standing lexicon, plus any word only page prose uses.

    A page is free to write a compound that is not in compounds.tsv -- an
    example built in running speech is not a dictionary entry.  Those get
    resolved here so that every chip on the site has something to open."""
    words = {}
    sentences, by_sentence = usage_index(t)
    usage = (by_sentence, compound_index(t))

    for gloss in t.gloss2root:
        kind = "particle" if t.is_particle(gloss) else "root"
        entry = entry_for(gloss, t, kind, usage)
        if entry:
            words[entry["form"].lower()] = entry

    for gloss in t.compound_by_gloss:
        entry = entry_for(gloss, t, "compound", usage)
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
        entry = entry_for(gloss, t, "phrase", usage)
        if entry is None:
            unresolved.append(form)
            continue
        entry["form"] = form
        words[form.lower()] = entry

    return {"words": words, "sentences": sentences,
            "categories": categories(t)}, unresolved


def write(lexicon):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(lexicon, count=len(lexicon["words"]))
    OUT.write_text(json.dumps(payload, ensure_ascii=False,
                              separators=(",", ":"), sort_keys=True) + "\n",
                   encoding="utf-8")
    return OUT


if __name__ == "__main__":
    tables = P.Tables()
    lexicon, missing = build(tables)
    path = write(lexicon)
    print(f"{len(lexicon['words'])} words, {len(lexicon['sentences'])} sentences "
          f"-> {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
    if missing:
        raise SystemExit(f"unresolved: {missing}")
