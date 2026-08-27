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
        # The Vocab page searches the sense range, so it rides along; strokes is
        # for the Han character in the detail view.  `covers` holds only what
        # the glosses do not already name, so what ships is the joined range --
        # see pikotika.root_covers.
        if row:
            entry["covers"] = P.root_covers(row)
            for key, out in (("strokes", "strokes"), ("gloss2", "gloss2")):
                if row.get(key):
                    entry[out] = row[key]

    # A root sits in exactly one category and a compound may sit in several,
    # but the page filters them all the same way, so what ships is always a
    # list.  **parte** is both -- a root, and a compounds.tsv row for the
    # "decimal point; minute" sense -- so the two are unioned, its own category
    # first, rather than one silently replacing the other.
    cats = []
    row = t.gloss2root.get(gloss)
    if row and row.get("category"):
        cats.append(row["category"])
    for cat in t.compound_cats.get(gloss, ()):
        if cat not in cats:
            cats.append(cat)
    if cats:
        entry["cats"] = cats

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
    # Curated rows first: a poured name can spell the same word as a hand-made
    # one (Mitar the name against mitar the loan, Tom against Dom/Thom/Tome),
    # and since `words` is keyed by the case-folded form, whichever comes first
    # is the entry the site shows.  The curated row is the one that was
    # deliberate.
    ordered = sorted(t.name_forms, key=lambda f: (bool(t.name_origin.get(f)), f))
    for form in ordered:
        canonical = t.name_forms[form]
        # Show every English name the form answers to, not just the one that
        # parsing round-trips through.
        english = t.name_english.get(form, canonical)
        # names.tsv marks the sanctioned loan register with kind=loan; both ride
        # in the same table and both stay in Latin inside Han text
        entry = {
            "form": form,
            "kind": t.name_kind.get(form, "name"),
            "gloss": english,
            "en": english,
            "han": "",
            "level": "",
        }
        if t.name_cats.get(form):
            entry["cats"] = list(t.name_cats[form])
        # Poured rows are searchable but not browsable: there are thousands of
        # them, and a browse list they appeared in would stop being a
        # dictionary you can read down.
        if t.name_origin.get(form):
            entry["bulk"] = 1
        yield form, entry


def check_compounds(t):
    """Every compounds.tsv row is a compound: two roots or more.

    A single-root row would work -- the lookups are by gloss either way -- which
    is why one sat there unnoticed, giving **parte** the extra senses "decimal
    point" and "minute".  That is what a root's `covers` column is for, and a
    sense recorded in the wrong table is a sense the root's own entry does not
    show."""
    bad = []
    for gloss in t.compound_by_gloss:
        roots = t.gloss_roots(gloss)
        if roots is None:
            # Not roots all the way through.  A sanctioned loan may be one of
            # a compound's components -- **kirumitar** is thousand-meter --
            # and counts as one for this rule, though gloss_roots has nothing
            # to say about it.  A piece that is neither root nor loan is a
            # table error, and gen_tables' parse_or_die is what reports that.
            pieces = gloss.split("-")
            if not all(t.root_gloss(x) or t.loan_of(x) for x in pieces):
                continue
            roots = pieces
        if len(roots) < 2:
            bad.append(gloss)
    if bad:
        raise SystemExit(
            "gen_lexicon: compounds.tsv row is a single root, not a compound: "
            + ", ".join(sorted(bad))
            + " -- extra senses of a root belong in its roots.tsv `covers`")


def check_categories(t):
    """roots.tsv defines the categories; the other two tables may only cite them.

    A typo in a `categories` cell would otherwise be silent -- the word would
    simply never appear under any chip -- so it stops the build instead."""
    known = set(t.category_order)
    bad = {}
    for gloss, cats in t.compound_cats.items():
        for cat in cats:
            if cat not in known:
                bad.setdefault(cat, []).append(gloss)
    for form, cats in t.name_cats.items():
        for cat in cats:
            if cat not in known:
                bad.setdefault(cat, []).append(form)
    if bad:
        lines = ["category not in roots.tsv: %r (%s)" % (cat, ", ".join(w[:3]))
                 for cat, w in sorted(bad.items())]
        raise SystemExit("gen_lexicon: " + "; ".join(lines))


# The words whose job *is* grammar, and the pages that teach each one.  A chip
# for **rite** or **vons** is worth little on its own -- what the reader wants
# next is the page where the construction is explained -- so the Vocab entry
# carries a link to it.  Keyed by Latin form, which is what `words` is keyed by;
# `grammar_topics` fails the build on a form or a slug that does not exist, so a
# renamed page or a retired compound cannot leave a dead link behind.
#
# **A word may name more than one page, most central first** (decided
# 2026-08-25; it was one page each at first).  **vons** is the preposition
# *from* and the *than* of every comparison, and a reader who taps it wants
# whichever of those they just met -- picking one for them was the wrong
# economy.  The list stays a list of *teaching* pages, though: a page that
# merely uses the word in an example does not earn a link, or **vin** would
# name half the section.
#
# Ordinary vocabulary is left out entirely -- the test is whether the word does
# grammatical work, not whether a grammar page mentions it.
GRAMMAR_TOPIC = {
    # Particles and pronouns
    "ri":        ["structure", "nosubject", "subordinate"],
    "a":         ["structure", "subordinate"],
    "te":        ["te", "relative"],
    "rite":      ["relative", "te"],
    "eko":       ["nouns"],
    "tu":        ["nouns"],
    "tis":       ["nouns", "relative"],
    "nontis":    ["nouns"],
    "tisomo":    ["nouns"],
    "ekomen":    ["nouns"],

    # Prepositions
    "in":        ["prepositions"],
    "ver":       ["prepositions"],
    "vons":      ["prepositions", "comparison"],
    "por":       ["prepositions"],
    "topi":      ["prepositions"],
    "sur":       ["prepositions"],
    "tun":       ["prepositions"],
    "nir":       ["prepositions"],
    "eks":       ["prepositions"],
    "mets":      ["prepositions"],

    # Negation, questions, commands
    "non":       ["negation", "questions"],
    "nem":       ["negation"],
    "ker":       ["questions", "relative"],
    "keromo":    ["questions"],
    "kerroko":   ["questions"],
    "kertempo":  ["questions"],
    "kermoto":   ["questions"],
    "kerrason":  ["questions"],
    "si":        ["questions"],
    "pam":       ["nosubject"],

    # Modifiers and comparison
    "mas":       ["comparison", "modifier-order"],
    "nonmas":    ["comparison", "modifier-order"],
    "sam":       ["comparison"],
    "surmesur":  ["modifier-order"],

    # Time, mood, conditions
    "apa":       ["aspect"],
    "vin":       ["aspect", "mood", "conditions"],
    "sista":     ["aspect"],
    "yer":       ["aspect"],
    "tar":       ["aspect"],
    "kan":       ["mood", "conditions"],
    "neses":     ["mood"],
    "pospona":   ["mood", "conditions"],
    "pos":       ["conditions", "mood"],
    "nonves":    ["conditions", "negation"],

    # Joining
    "kum":       ["joining", "prepositions"],
    "sive":      ["joining"],
    "sets":      ["joining"],
    "rason":     ["joining"],
    "tisrason":  ["joining", "conditions"],
}


def grammar_topics(words):
    """Tag each grammar word with its pages, and return slug -> page title.

    The titles come from `build.GRAMMAR_GROUPS`, so the label in an entry is the
    one the page and the Grammar index carry; imported here rather than at the
    top because build.py imports this module."""
    import build

    titles = {slug: title
              for _group, pages in build.GRAMMAR_GROUPS for slug, title, _b in pages}
    topics, missing = {}, []
    for form, slugs in GRAMMAR_TOPIC.items():
        entry = words.get(form)
        if entry is None:
            missing.append("no such word: " + form)
            continue
        for slug in slugs:
            if slug not in titles or not build.grammar_fragment_path(slug).is_file():
                missing.append("no such grammar page: " + slug)
                continue
            topics[slug] = titles[slug]
            entry.setdefault("topic", []).append(slug)
    if missing:
        raise SystemExit("gen_lexicon: " + "; ".join(sorted(set(missing))))
    return topics


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
        # A numeral is written in digits and *said* in words, and the entry so
        # far carries only the digits -- `entry_for` renders Latin from the
        # gloss, and the gloss of a numeral is the numeral.  Tapping **7** then
        # opened a tile reading "7 7 / seven; 7", which manages to say seven
        # four times and never says **sens**.  So a numeral records what it is
        # read as, and the tile shows that as the headword.
        #
        # Derived here rather than in JavaScript on purpose: reading a numeral
        # is `pikotika.expand_numerals`, which knows the dropped multiplier,
        # the linking `e`, and clock and fraction marks.  numbers.js is already
        # one port of that and is kept honest by check_numbers; a third
        # implementation inside a popover would not be.
        said = P.render_latin(P.expand_numerals(parsed), t)
        if said != form:
            entry["say"] = said
            # With the headword now the reading, a multi-word numeral would
            # otherwise show the digits nowhere at all: `en` for one of these
            # falls back to the gloss, so **15** read as a Vocab row without a
            # chip beside it for context.  A single digit is unaffected -- `7`
            # takes its English from the **sens** row, which already says both.
            if entry.get("en") == gloss:
                entry["en"] = form
        words[form.lower()] = entry

    check_compounds(t)
    check_categories(t)
    topics = grammar_topics(words)
    return {"words": words, "sentences": sentences, "topics": topics,
            "categories": list(t.category_order)}, unresolved


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
