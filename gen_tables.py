#!/usr/bin/env python3
"""Generate the reader-facing lexicon tables from the TSV sources.

ROOTS.md      one table per category from roots.tsv, in source order,
              with columns Gloss, Latin, Han, Covers.
COMPOUNDS.md  one table from compounds.tsv, sorted by English, with
              columns English, Gloss, Latin, Han.

Latin and Han for the compounds are rendered through pikotise.py rather
than spelled out here, so the linking `e` and the numeral/digit rules stay
in one place.

compounds.tsv is also rewritten in place, to fill in `root_level` (the
highest Level of any root the compound uses).  `assigned_level` is edited by
hand and only carried through.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pikotise  # noqa: E402  (needs HERE on the path first)

ROOTS_TSV = os.path.join(HERE, 'roots.tsv')
COMPOUNDS_TSV = os.path.join(HERE, 'compounds.tsv')
ROOTS_MD = os.path.join(HERE, 'ROOTS.md')
COMPOUNDS_MD = os.path.join(HERE, 'COMPOUNDS.md')


def rows_of(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def read_table(path):
    """Rows plus the field order, so a file can be rewritten as it was read."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        return list(reader), list(reader.fieldnames)


def rewrite(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields, delimiter='\t', lineterminator='\n')
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


def render_roots(groups):
    total = sum(len(rows) for _, rows in groups)
    out = ['# Pikotise Roots', '',
           f'{total} entries in {len(groups)} groups.', '']
    for category, rows in groups:
        out += [f'## {category} ({len(rows)})', '']
        out += table(['Gloss', 'Latin', 'Han', 'Covers'],
                     [(r.get('gloss'), r.get('form'), r.get('han'),
                       r.get('covers')) for r in rows])
        out.append('')
    return '\n'.join(out)


# --- compounds --------------------------------------------------------

ROOT_LEVEL = 'root_level'
ASSIGNED_LEVEL = 'assigned_level'


def root_level(gloss, t):
    """The highest Level of any root in `gloss`; '' if any root has none.

    A blank Level counts as higher than any number: a compound is only as
    teachable as its least-placed root, and an unplaced root is unplaced.
    """
    words = pikotise.parse_gloss(gloss, t)
    if words is None:
        sys.exit(f'{COMPOUNDS_TSV}: cannot parse gloss {gloss!r}')
    highest = 0
    for word in words:
        if isinstance(word, str):     # punctuation rides along as text
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
        row[ROOT_LEVEL] = root_level(gloss, t) if gloss else ''
        row[ASSIGNED_LEVEL] = (row.get(ASSIGNED_LEVEL) or '').strip()
    return sum(1 for r in rows if r[ROOT_LEVEL])


def render_compounds(rows, t):
    entries = []
    for row in rows:
        english = (row.get('EN') or '').strip()
        gloss = (row.get('gloss') or '').strip()
        if not english or not gloss:
            continue
        words = pikotise.parse_gloss(gloss, t)
        if words is None:
            sys.exit(f'{COMPOUNDS_TSV}: cannot parse gloss {gloss!r}')
        entries.append((english, gloss,
                        pikotise.render_latin(words, t),
                        pikotise.render_han(words, t)))
    entries.sort(key=lambda e: (e[0].casefold(), e[0]))
    out = ['# Pikotise Compounds', '',
           f'{len(entries)} terms', '']
    out += table(['English', 'Gloss', 'Latin', 'Han'], entries)
    out.append('')
    return '\n'.join(out)


def main():
    groups = group_roots(rows_of(ROOTS_TSV))
    with open(ROOTS_MD, 'w', encoding='utf-8') as f:
        f.write(render_roots(groups))
    print(f'Wrote {ROOTS_MD}: {sum(len(r) for _, r in groups)} roots, '
          f'{len(groups)} groups.')

    t = pikotise.Tables(HERE)
    rows, fields = read_table(COMPOUNDS_TSV)
    with open(COMPOUNDS_MD, 'w', encoding='utf-8') as f:
        f.write(render_compounds(rows, t))
    print(f'Wrote {COMPOUNDS_MD}: {len(rows)} compounds.')

    leveled = level_compounds(rows, fields, t)
    rewrite(COMPOUNDS_TSV, rows, fields)
    print(f'Wrote {COMPOUNDS_TSV}: {leveled} of {len(rows)} compounds leveled, '
          f'{len(rows) - leveled} with an unleveled root.')


if __name__ == '__main__':
    main()
