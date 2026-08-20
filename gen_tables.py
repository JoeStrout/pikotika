#!/usr/bin/env python3
"""Generate the reader-facing lexicon tables from the TSV sources.

ROOTS.md      one table per category from roots.tsv, in source order,
              with columns Gloss, Latin, Han, Covers.
COMPOUNDS.md  one table from compounds.tsv, sorted by English, with
              columns English, Gloss, Latin, Han.

Latin and Han for the compounds are rendered through pikotika.py rather
than spelled out here, so the linking `e` and the numeral/digit rules stay
in one place.

compounds.tsv is also rewritten in place, to fill in `root_level` (the
highest Level of any root the compound uses).  `assigned_level` is edited by
hand and only carried through.

corpus.tsv likewise: `EN` and `gloss` are canonical and hand-edited, and
`latin`, `han`, and `root_level` are rendered from the gloss on every run, so
a sentence recorded once stays correct through any later change to a root's
form or character.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pikotika  # noqa: E402  (needs HERE on the path first)

ROOTS_TSV = os.path.join(HERE, 'roots.tsv')
COMPOUNDS_TSV = os.path.join(HERE, 'compounds.tsv')
CORPUS_TSV = os.path.join(HERE, 'corpus.tsv')
ROOTS_MD = os.path.join(HERE, 'ROOTS.md')
COMPOUNDS_MD = os.path.join(HERE, 'COMPOUNDS.md')


def rows_of(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, **pikotika.TSV))


def read_table(path):
    """Rows plus the field order, so a file can be rewritten as it was read."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, **pikotika.TSV)
        return list(reader), list(reader.fieldnames)


def rewrite(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n',
                                **pikotika.TSV)
        writer.writeheader()
        writer.writerows(rows)


def cell(text):
    return (text or '').strip().replace('|', r'\|')


def table(header, body):
    return ['| ' + ' | '.join(header) + ' |',
            '|' + '---|' * len(header)] + \
           ['| ' + ' | '.join(cell(c) for c in row) + ' |' for row in body]


# --- roots ------------------------------------------------------------

def group_roots(rows):
    """Return [(category, [row, ...]), ...] in source order."""
    groups = []
    index = {}
    for row in rows:
        category = (row.get('category') or '').strip() or 'Uncategorized'
        if category not in index:
            index[category] = []
            groups.append((category, index[category]))
        index[category].append(row)
    return groups


def glosses(row):
    """Both glosses of a root, as `gloss; gloss2` (`gloss` alone if bare)."""
    return '; '.join(g for g in ((row.get('gloss') or '').strip(),
                                 (row.get('gloss2') or '').strip()) if g)


def render_roots(groups):
    total = sum(len(rows) for _, rows in groups)
    out = ['# Pikotika Roots', '',
           f'{total} entries in {len(groups)} groups.', '']
    for category, rows in groups:
        out += [f'## {category} ({len(rows)})', '']
        # both glosses in one cell: a learner memorizes the pair, and either
        # one may be written in gloss notation (pikotika.org/grammar/writing/)
        out += table(['Gloss', 'Latin', 'Han', 'Covers'],
                     [(glosses(r), r.get('form'), r.get('han'),
                       r.get('covers')) for r in rows])
        out.append('')
    return '\n'.join(out)


# --- compounds --------------------------------------------------------

ROOT_LEVEL = 'root_level'
ASSIGNED_LEVEL = 'assigned_level'


def parse_or_die(gloss, t, source):
    words = pikotika.parse_gloss(gloss, t)
    if words is None:
        sys.exit(f'{source}: cannot parse gloss {gloss!r}')
    return words


def root_level(words, t):
    """The highest Level of any root in `words`; '' if any root has none.

    A blank Level counts as higher than any number: a compound is only as
    teachable as its least-placed root, and an unplaced root is unplaced.

    A written numeral is read out first, the same way `pikotika.max_level`
    does it, so `30` costs the roots `three` and `ten` that saying it costs.
    """
    highest = 0
    for word in pikotika.expand_numerals(words):
        if pikotika.is_punct(word):    # punctuation rides along as text
            continue
        for piece in word:
            if isinstance(piece, tuple):   # names and numbers are not roots
                continue
            level = (t.gloss2root.get(piece, {}).get('Level') or '').strip()
            if not level.isdigit():
                return ''
            highest = max(highest, int(level))
    return str(highest) if highest else ''


def level_compounds(rows, fields, t):
    """Fill in root_level, leaving the hand-edited assigned_level alone."""
    for column in (ROOT_LEVEL, ASSIGNED_LEVEL):
        if column not in fields:
            fields.append(column)
    for row in rows:
        gloss = (row.get('gloss') or '').strip()
        row[ROOT_LEVEL] = (root_level(parse_or_die(gloss, t, COMPOUNDS_TSV), t)
                           if gloss else '')
        row[ASSIGNED_LEVEL] = (row.get(ASSIGNED_LEVEL) or '').strip()
    return sum(1 for r in rows if r[ROOT_LEVEL])


def render_compounds(rows, t):
    """One row per English term, though the TSV keeps one row per gloss.

    A reader uses this table to look a word up, so the alternatives recorded
    together as "theater; playhouse" are split back apart and alphabetized
    separately.
    """
    entries = []
    for row in rows:
        gloss = (row.get('gloss') or '').strip()
        if not gloss:
            continue
        words = parse_or_die(gloss, t, COMPOUNDS_TSV)
        latin, han = pikotika.render_latin(words, t), pikotika.render_han(words, t)
        for english in pikotika.split_alternatives(row.get('EN') or ''):
            entries.append((english, gloss, latin, han))
    entries.sort(key=lambda e: (e[0].casefold(), e[0]))
    out = ['# Pikotika Compounds', '',
           f'{len(entries)} terms', '']
    out += table(['English', 'Gloss', 'Latin', 'Han'], entries)
    out.append('')
    return '\n'.join(out), len(entries)


# --- corpus -----------------------------------------------------------

LATIN = 'latin'
HAN = 'han'


def sentence_case(text):
    """Latin notation capitalizes a sentence; gloss notation does not.

    The particles are the reason this is done here and not in pikotika.py:
    they are *RI* in gloss and **ri** in Latin, so a sentence-initial *RI*
    renders lowercase and only a whole-sentence view knows to raise it.
    """
    return text[:1].upper() + text[1:]


def render_corpus(rows, fields, t):
    """Fill in latin, han and root_level from the hand-edited gloss."""
    for column in (LATIN, HAN, ROOT_LEVEL):
        if column not in fields:
            fields.append(column)
    rendered = 0
    for row in rows:
        gloss = (row.get('gloss') or '').strip()
        if not gloss:
            row[LATIN] = row[HAN] = row[ROOT_LEVEL] = ''
            continue
        words = parse_or_die(gloss, t, CORPUS_TSV)
        row[LATIN] = sentence_case(pikotika.render_latin(words, t))
        row[HAN] = pikotika.render_han(words, t)
        row[ROOT_LEVEL] = root_level(words, t)
        rendered += 1
    return rendered


def main():
    groups = group_roots(rows_of(ROOTS_TSV))
    with open(ROOTS_MD, 'w', encoding='utf-8') as f:
        f.write(render_roots(groups))
    print(f'Wrote {ROOTS_MD}: {sum(len(r) for _, r in groups)} roots, '
          f'{len(groups)} groups.')

    t = pikotika.Tables(HERE)
    rows, fields = read_table(COMPOUNDS_TSV)
    md, terms = render_compounds(rows, t)
    with open(COMPOUNDS_MD, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'Wrote {COMPOUNDS_MD}: {terms} terms for {len(rows)} compounds.')

    leveled = level_compounds(rows, fields, t)
    rewrite(COMPOUNDS_TSV, rows, fields)
    print(f'Wrote {COMPOUNDS_TSV}: {leveled} of {len(rows)} compounds leveled, '
          f'{len(rows) - leveled} with an unleveled root.')

    rows, fields = read_table(CORPUS_TSV)
    rendered = render_corpus(rows, fields, t)
    rewrite(CORPUS_TSV, rows, fields)
    print(f'Wrote {CORPUS_TSV}: {rendered} of {len(rows)} sentences rendered.')


if __name__ == '__main__':
    main()
