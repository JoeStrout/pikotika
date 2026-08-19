#!/usr/bin/env python3
"""Show where one root is used: its compounds, and its corpus sentences.

The two sources are the ones count_usage.py totals into `usage_count`, so this
is the readable form of any one of those counts.

Usage: python3 show_usage.py <root>

The root is given in Latin form (`kosa`); its gloss (`thing`) is accepted too,
since the tables are indexed both ways and it costs nothing to take either.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pikotika  # noqa: E402  (needs HERE on the path first)

COMPOUNDS_TSV = os.path.join(HERE, 'compounds.tsv')
CORPUS_TSV = os.path.join(HERE, 'corpus.tsv')


def resolve(token, t):
    """The gloss the argument names, in either notation; None if neither."""
    if token in t.form2gloss:
        return t.form2gloss[token]
    if token in t.gloss2root:
        return token
    lowered = token.lower()
    if lowered in t.form2gloss:
        return t.form2gloss[lowered]
    return t.gloss2root.get(lowered, {}).get('gloss')


def rows_of(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, **pikotika.TSV))


def parts_of(gloss):
    """The roots a compound gloss is built from."""
    return [p for p in re.split(r'[-\s]+', gloss.strip()) if p]


def compound_uses(gloss, t):
    """(English, Latin) for every compound whose gloss uses the root."""
    found = []
    for row in rows_of(COMPOUNDS_TSV):
        compound = (row.get('gloss') or '').strip()
        if gloss not in parts_of(compound):
            continue
        words = pikotika.parse_gloss(compound, t)
        latin = pikotika.render_latin(words, t) if words else compound
        found.append((row.get('EN', ''), latin))
    return found


def corpus_uses(gloss, t):
    """(English, Latin) for every corpus sentence whose Han uses the root.

    Matched on the `han` column for the same reason count_usage.py counts it:
    one character is one root, so names and numerals need no special case.
    """
    found = []
    for row in rows_of(CORPUS_TSV):
        han = (row.get('han') or '').strip()
        if not han:
            continue
        words = pikotika.parse_han(han, t)
        if words is None:
            continue
        used = any(g == gloss for word in words
                   if not pikotika.is_punct(word)
                   and not pikotika.is_numeral(word)
                   for g in word)
        if used:
            found.append((row.get('EN', ''), (row.get('latin') or '').strip()))
    return found


def show(title, uses):
    print(f'{title} ({len(uses)}):')
    if not uses:
        print('  (none)')
    for english, latin in uses:
        print(f'  {latin}\n      {english}')
    print()


def main(argv):
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    t = pikotika.Tables(HERE)
    gloss = resolve(argv[0], t)
    if gloss is None:
        print(f'no such root: {argv[0]}', file=sys.stderr)
        return 1

    print(f'{t.form_of(gloss)} = {gloss} '
          f'({pikotika.root_covers(t.gloss2root[gloss])})\n')
    show('compounds', compound_uses(gloss, t))
    show('corpus', corpus_uses(gloss, t))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
