#!/usr/bin/env python3
"""Screen a proposed root form, or audit the forms already in the lexicon.

    python3 check_form.py <gloss> <form> [<form> ...]   screen candidates
    python3 check_form.py --new <gloss> <form> ...      screen a root we lack
    python3 check_form.py --audit                       audit what we have

Renaming a root is cheap to propose and expensive to undo, so this collects the
checks that decide whether a candidate form can work.  They are not all equally
important, and the order below is roughly the order in which a candidate dies:

1. **Legality.**  The form has to be pronounceable in Pikotika at all: single
   consonant onsets, only `n m s r` as a simple coda, and `-ns -ts -ks` only at
   the end of a word.  This is first because a tool that scores an impossible
   word as "clean" is worse than no tool -- *rot* for 'red' looks fine to every
   other test here and is not a legal Pikotika word.  The test applies to the
   root alone: a legal root is legal in every compound, because the linking `e`
   resolves whatever it meets.  A cluster-final root is charged for that link
   in the impact section, not here.

2. **Collision**, exact and fuzzy.  Exact is obvious.  Fuzzy is not: the
   pronunciation table in DETAILS.md gives every letter a *range* of correct
   sounds, and two ranges can overlap, so two spellings can be one word in some
   speaker's mouth.  `v` covers [v] and [f]; `w` covers [w] and [v]; so **arvo**
   and **arwo** are the same word to anyone who takes the [v] option, and, worse,
   **arvo** and **arpo** are the same word to a Spanish speaker, for whom the [b]
   inside `p` and the [v] inside `v` are one sound.  This test is the one that
   most often kills an otherwise attractive candidate, and it is impossible to
   run reliably by eye.

3. **Consonant structure.**  DETAILS.md says a word should be recognizable from
   its consonants alone, with vowels as a secondary cue.  Taken seriously, that
   makes two roots with the same consonants in the same places near-homophones
   however different they look on the page -- **ranko** 'white' and **ronka**
   'long' are both `r*nk*`.  The test masks the vowels rather than deleting
   them, so the count and position of the vowels still tells the two words
   apart: **rus** is `r*s` and **riso** is `r*s*`, and those do not collide.

4. **Minimal pairs**, vowel-only ones reported harder than consonant ones, for
   the same reason.

5. **Segmentation.**  Whether the candidate makes any compound parse two ways.
   Reported last because it almost never fires: compounds are long and the form
   inventory is sparse, so nearly every candidate scores clean here.

6. **Impact.**  Every compound holding the root, rendered before and after, with
   syllable counts.  A rename is bought for the syllables it saves, so the bill
   belongs in the same output as the risks.

Prefix relations are reported too, but as information rather than a verdict: a
shared prefix only matters if it actually produces a second parse, and check 5
answers that directly.

Proper names are not part of any of this.  They are capitalized wherever they
appear, context supplies them, and the list of them is open-ended -- so a root
sharing a form with somebody's name is not a fact about the language.  The
sanctioned loans in `names.tsv` (**metoru**, **kuramu**) are ordinary lowercase
words and are checked like roots.
"""

import csv
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pikotika  # noqa: E402  (needs HERE on the path first)

COMPOUNDS_TSV = os.path.join(HERE, 'compounds.tsv')
CORPUS_TSV = os.path.join(HERE, 'corpus.tsv')

VOWELS = pikotika.VOWELS
CONSONANTS = 'ptkvsrmnwy'
CODAS = set('nmsr')
FINAL_CLUSTERS = set(pikotika.CLUSTERS)

# What each letter may be pronounced as, from the tables in DETAILS.md.  Two
# letters are confusable when these sets intersect -- not when the letters look
# alike.  Written out in full rather than reduced to the one overlapping pair,
# so that changing the pronunciation table changes the answer here too.
SOUNDS = {
    'p': {'p', 'b'},
    't': {'t', 'd', 'th'},
    'k': {'k', 'g'},
    'v': {'v', 'f'},
    's': {'s', 'z', 'sh'},
    'r': {'r', 'l'},
    'm': {'m'},
    'n': {'n', 'ng'},
    'w': {'w', 'v'},
    'y': {'y', 'j', 'zh'},
}


# Two letters can also meet one step further out, in a listener's first
# language, and the tables above will not show it.  Spanish has one phoneme
# where English has *b* and *v*, so the [b] allowed inside `p` and the [v]
# allowed inside `v` are the same sound to a Spanish speaker -- which makes
# **arpo** and **arvo** homophones for a tenth of the planet, though no cell of
# the pronunciation table says so.  Each set below is a merger common enough to
# design around; sounds, not letters.
MERGERS = (
    {'b', 'v'},     # Spanish, Catalan, Greek: one phoneme, [β]
    {'v', 'w'},     # Hindi, Urdu, and much of South and Southeast Asia
    {'p', 'f'},     # Arabic, where [p] is normally realized as [f]
    {'sh', 'zh'},   # voicing is free elsewhere in the language; so here too
)


def merged(sound, _cache={}):
    """A sound as its merger class, so merged sounds compare equal."""
    if not _cache:
        classes = [set(m) for m in MERGERS]
        changed = True
        while changed:                      # merge overlapping sets
            changed = False
            for i, a in enumerate(classes):
                for b in classes[i + 1:]:
                    if a & b:
                        a |= b
                        classes.remove(b)
                        changed = True
                        break
                if changed:
                    break
        for group in classes:
            for member in group:
                _cache[member] = min(group)
    return _cache.get(sound, sound)


def confusable_letters():
    """Letter -> the letters it can share a pronunciation with."""
    heard = {letter: {merged(s) for s in sounds}
             for letter, sounds in SOUNDS.items()}
    out = defaultdict(set)
    for a in heard:
        for b in heard:
            if a != b and heard[a] & heard[b]:
                out[a].add(b)
    return out


CONFUSABLE = confusable_letters()

# One representative per set of mutually confusable letters, so that two forms
# that some speaker pronounces alike fold to the same string.
FUZZ = {}
for _letter in SOUNDS:
    _group = sorted({_letter} | CONFUSABLE.get(_letter, set()))
    FUZZ[_letter] = _group[0]


def fuzzy(form):
    """The form as heard through the pronunciation tolerances."""
    return ''.join(FUZZ.get(c, c) for c in form)


def masked(form):
    """The form with every vowel replaced by `*`.

    Two forms with the same mask are the same word to a listener who takes the
    consonants and no more: **ranko** and **ronka** are both `r*nk*`.  Dropping
    the vowels instead of masking them would be too coarse -- it makes **rus**
    and **riso** compare equal, which no listener would confuse, because the
    number and placement of the vowels is itself information even when their
    quality is not.
    """
    return ''.join('*' if c in VOWELS else c for c in form)


def syllables(form):
    """Syllable count: one per vowel, since Pikotika has no diphthongs."""
    return sum(1 for c in form if c in VOWELS)


def illegal(form):
    """Complaints about the form's phonology; empty if it is a legal word.

    Walks the form syllable by syllable.  Each syllable is an optional single
    consonant onset plus a vowel; the consonants that follow are split so that
    the last one opens the next syllable and whatever precedes it closes this
    one.  A closing consonant must be one of `n m s r`, except at the end of a
    word, where `-ns -ts -ks` are allowed as well.

    **This test is about roots, not about compounds.**  No combination of legal
    roots is unpronounceable: where a root ends in a cluster and the next root
    begins with a consonant, a linking `e` goes between them -- **tets** +
    **kurva** is **tetsekurva**.  So do not run this over a compound you have
    spelled out by hand and conclude that a candidate root is illegal in use;
    that is a mistake this tool has already caused once.  The impact section
    renders through `pikotika`, which inserts the linker, and the syllable
    counts there already charge the candidate for it -- which is the real cost
    of a cluster-final root, and the one worth reading.
    """
    problems = []
    bad = sorted({c for c in form if c not in VOWELS + CONSONANTS})
    if bad:
        problems.append('not in the alphabet: ' + ' '.join(repr(c) for c in bad))
        return problems
    if not form:
        return ['empty']

    i = 0
    while i < len(form):
        onset = ''
        while i < len(form) and form[i] not in VOWELS:
            onset += form[i]
            i += 1
        if len(onset) > 1:
            problems.append(f'{onset!r} is a consonant cluster at the start of '
                            f'a syllable; onsets are one consonant')
        if i >= len(form):
            # consonants with no vowel after them: the coda of the last syllable
            if onset not in CODAS and onset not in FINAL_CLUSTERS:
                problems.append(f'{onset!r} cannot close a word; '
                                f'codas are n m s r, plus -ns -ts -ks finally')
            return problems
        i += 1  # the vowel
        # a run of consonants: the last opens the next syllable, the rest close
        run = ''
        while i < len(form) and form[i] not in VOWELS:
            run += form[i]
            i += 1
        if i >= len(form):
            if run and run not in CODAS and run not in FINAL_CLUSTERS:
                problems.append(f'{run!r} cannot close a word; '
                                f'codas are n m s r, plus -ns -ts -ks finally')
        else:
            # `-ns -ts -ks` are word-final in a *root*, but a compound carries
            # one into the middle of a word and the linking `e` opens the next
            # syllable behind it -- **eksire**, **tetsekurva**.  So a licensed
            # cluster closes a syllable anywhere; otherwise the last consonant
            # of the run opens the next syllable and the rest has to close this.
            if run in FINAL_CLUSTERS:
                continue
            coda = run[:-1]
            if len(coda) > 1:
                problems.append(f'{coda!r} cannot close a syllable; '
                                f'a coda inside a word is one of n m s r')
            elif coda and coda not in CODAS:
                problems.append(f'{coda!r} cannot close a syllable; '
                                f'codas inside a word are n m s r')
    return problems


# ---------------------------------------------------------------------------
# the lexicon, as forms


def loans(d=HERE):
    """[(form, EN)] for the sanctioned loan register in names.tsv.

    Proper names are deliberately left out.  They are capitalized wherever they
    appear, context always supplies them, and there are as many of them as there
    are people and places -- so a root that happens to share a form with one is
    not a fact about the language.  Loans are ordinary lowercase words and do
    compete with roots, so they stay in.
    """
    path = os.path.join(d, 'names.tsv')
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as fh:
        return [(r['form'], r['EN']) for r in csv.DictReader(fh, **pikotika.TSV)
                if r.get('kind') == 'loan']


def lexicon(t, without=None):
    """[(form, label)] for every root, particle and loan.

    A list rather than a dict keyed by form, because two entries sharing a form
    is precisely the thing worth reporting, and a dict would quietly drop one.

    `without` is the gloss being renamed: its outgoing form is left out, so a
    candidate is not reported as colliding with the word it replaces.
    """
    out = []
    for gloss, row in t.gloss2root.items():
        form = row.get('form')
        if not form or gloss == without:
            continue
        kind = 'particle' if t.is_particle(gloss) else 'root'
        out.append((form, f'{gloss} ({kind})'))
    for form, english in loans():
        out.append((form, f'{english} (loan)'))
    return sorted(out)


def root_forms(t):
    """Just the forms a compound can be built from: roots, not particles."""
    return {f for f, label in lexicon(t) if label.endswith('(root)')}


SEVERITY = ('COLLISION', 'SOUNDS ALIKE', 'VOWEL-ONLY PAIR', 'SAME CONSONANTS',
            'minimal pair', 'prefix')


def compare(form, other):
    """How close two forms are: (kind, why), or None if they are far enough.

    A shared mask is reported as a VOWEL-ONLY PAIR when exactly one vowel
    differs and as SAME CONSONANTS when more than one does; the first is the
    sharper case, but both are the same finding underneath.
    """
    if other == form:
        return 'COLLISION', 'the same form'
    if fuzzy(other) == fuzzy(form):
        swaps = [f'{a}/{b}' for a, b in zip(form, other) if a != b]
        return 'SOUNDS ALIKE', 'one word to some speakers: ' + ', '.join(swaps)
    if masked(other) == masked(form):
        diff = [f'{a}/{b}' for a, b in zip(form, other) if a != b]
        kind = 'VOWEL-ONLY PAIR' if len(diff) == 1 else 'SAME CONSONANTS'
        return kind, f'both are {masked(form)}; {", ".join(diff)}'
    if len(other) == len(form):
        diff = [(a, b) for a, b in zip(form, other) if a != b]
        if len(diff) == 1:
            return 'minimal pair', f'{diff[0][0]} against {diff[0][1]}'
    if other.startswith(form) or form.startswith(other):
        return 'prefix', 'one opens the other'
    return None


def neighbors(form, lex, skip=None):
    """Every entry in `lex` that is too close to `form`, worst first.

    `skip` is an index into `lex` to leave out -- the entry the form came from,
    when auditing a form already in the table.
    """
    found = []
    for i, (other, label) in enumerate(lex):
        if i == skip:
            continue
        verdict = compare(form, other)
        if verdict is None:
            continue
        kind, why = verdict
        found.append((kind, other, label, why))
    return sorted(found, key=lambda f: (SEVERITY.index(f[0]), f[1]))


# ---------------------------------------------------------------------------
# segmentation


def segmentations(word, forms):
    """Every way `word` splits into root forms, linking `e` allowed."""
    ways = [[] for _ in range(len(word) + 1)]
    ways[0] = [[]]
    for i in range(1, len(word) + 1):
        for j in range(i):
            piece = word[j:i]
            if piece not in forms:
                continue
            ways[i] += [w + [piece] for w in ways[j]]
            # form[j-1] is an `e` belonging to neither root: tets + e + kurva
            if j and word[j - 1] == pikotika.LINK:
                ways[i] += [w + [piece] for w in ways[j - 1]
                            if w and pikotika.links(w[-1], piece)]
    return ways[len(word)]


def rows_of(path):
    with open(path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh, **pikotika.TSV))


def written_words(t):
    """(where, latin) for every solid word in the compound and corpus tables."""
    out = []
    for row in rows_of(COMPOUNDS_TSV):
        gloss = (row.get('gloss') or '').strip()
        words = pikotika.parse_gloss(gloss, t)
        if words:
            out.append((row.get('EN', ''), pikotika.render_latin(words, t)))
    for row in rows_of(CORPUS_TSV):
        for word in re.split(r'[^a-z]+', (row.get('latin') or '').lower()):
            if len(word) > 3:
                out.append((row.get('EN', ''), word))
    return out


def ambiguous(t, forms):
    """(where, latin, parses) for every word that splits more than one way."""
    found, seen = [], set()
    for where, word in written_words(t):
        if word in seen:
            continue
        seen.add(word)
        parses = segmentations(word, forms)
        if len(parses) > 1:
            found.append((where, word, parses))
    return found


# ---------------------------------------------------------------------------
# screening one candidate


def swapped_tables(gloss, form):
    """A fresh Tables with `gloss` renamed to `form`, or added if it is new."""
    t = pikotika.Tables(HERE)
    row = t.gloss2root.get(gloss)
    if row is None:
        t.gloss2root[gloss] = {'gloss': gloss, 'form': form, 'han': '',
                               'covers': '', 'Level': ''}
    else:
        del t.form2gloss[row['form']]
        row['form'] = form
    t.form2gloss[form] = gloss
    return t


def compounds_using(gloss):
    """The gloss of every compound built on the root."""
    out = []
    for row in rows_of(COMPOUNDS_TSV):
        compound = (row.get('gloss') or '').strip()
        if gloss in re.split(r'[-\s]+', compound):
            out.append((row.get('EN', ''), compound))
    return out


def screen(gloss, form, base):
    """Report on one candidate.  Returns True if nothing fatal was found."""
    row = base.gloss2root.get(gloss)
    standing = f'now {row["form"]}' if row else 'a root we do not have'
    print(f'\n=== {form} for `{gloss}` ({standing}) ' + '=' * 20)

    problems = illegal(form)
    print('\nlegality:')
    if problems:
        for p in problems:
            print(f'  ILLEGAL: {p}')
        return False
    print(f'  legal, {syllables(form)} syllable(s)')

    lex = lexicon(base, without=gloss)
    close = neighbors(form, lex)
    print('\nneighbors:')
    if not close:
        print('  (none)')
    for kind, other, label, why in close:
        print(f'  {kind:16} {other:10} {label:22} {why}')

    t = swapped_tables(gloss, form)
    print('\nsegmentation:')
    # only what the candidate introduces: the lexicon has standing ambiguities
    # of its own, and repeating them under every candidate buries the new ones
    standing = {word for _, word, _ in ambiguous(base, root_forms(base))}
    new = [a for a in ambiguous(t, root_forms(t)) if a[1] not in standing]
    if not new:
        print(f'  no new ambiguity ({len(standing)} standing, unrelated)')
    for where, word, parses in new:
        print(f'  {word:24} {where}')
        for parse in parses:
            print(f'      {" + ".join(parse)}')

    uses = compounds_using(gloss)
    print(f'\nimpact ({len(uses)} compounds):')
    before = after = 0
    for english, compound in uses:
        old = pikotika.render_latin(pikotika.parse_gloss(compound, base), base)
        new = pikotika.render_latin(pikotika.parse_gloss(compound, t), t)
        before += syllables(old)
        after += syllables(new)
        print(f'  {old:24} ({syllables(old)}) -> {new:24} ({syllables(new)})'
              f'  {english}')
    if uses:
        saved = before - after
        verdict = (f'saves {saved} syllables' if saved > 0 else
                   f'costs {-saved} syllables' if saved < 0 else
                   'no change in length')
        print(f'  {"":24}  {before} syllables    -> {"":24}  {after}'
              f'          {verdict}')
    return not any(k in ('COLLISION', 'SOUNDS ALIKE') for k, _, _, _ in close)


# ---------------------------------------------------------------------------
# auditing what we already have


def audit():
    """Run the same tests over the lexicon as it stands."""
    t = pikotika.Tables(HERE)
    lex = lexicon(t)

    print('=' * 72)
    print(f'audit of {len(lex)} forms in roots.tsv, plus the loan register')
    print('=' * 72)

    print('\n-- illegal forms ' + '-' * 55)
    hits = 0
    for form, label in lex:
        if label.endswith('(loan)'):
            continue  # loans are adapted, not coined; DETAILS allows more there
        for problem in illegal(form):
            print(f'  {form:10} {label:24} {problem}')
            hits += 1
    if not hits:
        print('  (none)')
    else:
        # how far the problem has spread: a bad root makes every compound and
        # every sentence built on it unpronounceable too
        spread = sorted({word for _, word in written_words(t) if illegal(word)})
        print(f'  ... and {len(spread)} written words inherit it: '
              f'{", ".join(spread[:6])}'
              + (', ...' if len(spread) > 6 else ''))

    for kind, title in (('COLLISION', 'identical forms'),
                        ('SOUNDS ALIKE', 'forms some speakers cannot tell apart'),
                        ('VOWEL-ONLY PAIR', 'forms differing in one vowel'),
                        ('SAME CONSONANTS',
                         'forms with the same mask, differing in two vowels or more')):
        print(f'\n-- {title} ' + '-' * (70 - len(title)))
        seen, hits = set(), 0
        for i, (form, label) in enumerate(lex):
            for found, other, other_label, why in neighbors(form, lex, skip=i):
                if found != kind or (other, form) in seen:
                    continue
                seen.add((form, other))
                print(f'  {form:10} {label:24} vs '
                      f'{other:10} {other_label:24} {why}')
                hits += 1
        if not hits:
            print('  (none)')

    print('\n-- words that split more than one way ' + '-' * 34)
    amb = ambiguous(t, root_forms(t))
    if not amb:
        print('  (none)')
    for where, word, parses in amb:
        print(f'  {word:24} {where}')
        for parse in parses:
            print(f'      {" + ".join(parse)}')


def main(argv):
    if argv[:1] == ['--audit'] and len(argv) == 1:
        audit()
        return 0
    if len(argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    new = argv[0] == '--new'
    if new:
        argv = argv[1:]
        if len(argv) < 2:
            print(__doc__.strip(), file=sys.stderr)
            return 2
    gloss, candidates = argv[0], argv[1:]
    base = pikotika.Tables(HERE)
    if gloss not in base.gloss2root and not new:
        found = base.form2gloss.get(gloss)
        if found is None:
            print(f'no such root: {gloss} '
                  f'(use --new to screen a root we do not have yet)',
                  file=sys.stderr)
            return 1
        gloss = found
    for form in candidates:
        screen(gloss, form.lower(), base)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
