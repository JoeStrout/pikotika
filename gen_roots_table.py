#!/usr/bin/env python3
"""Generate ROOTS.md: one table per category from roots.tsv.

Columns: Gloss, Latin, Han, Covers.  Categories and rows keep the order
they appear in roots.tsv.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'roots.tsv')
OUTPUT = os.path.join(HERE, 'ROOTS.md')


def read_roots(path):
    """Return [(category, [row, ...]), ...] in source order."""
    groups = []
    index = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            category = (row.get('category') or '').strip() or 'Uncategorized'
            if category not in index:
                index[category] = []
                groups.append((category, index[category]))
            index[category].append(row)
    return groups


def cell(text):
    return (text or '').strip().replace('|', r'\|')


def render(groups):
    total = sum(len(rows) for _, rows in groups)
    out = ['# Pikotise Roots', '',
           f'{total} entries in {len(groups)} groups, generated from `roots.tsv`.', '']
    for category, rows in groups:
        out.append(f'## {category} ({len(rows)})')
        out.append('')
        out.append('| Gloss | Latin | Han | Covers |')
        out.append('|---|---|---|---|')
        for row in rows:
            out.append('| {} | {} | {} | {} |'.format(
                cell(row.get('gloss')), cell(row.get('form')),
                cell(row.get('han')), cell(row.get('covers'))))
        out.append('')
    return '\n'.join(out)


def main():
    groups = read_roots(SOURCE)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(render(groups))
    print(f'Wrote {OUTPUT}: {sum(len(r) for _, r in groups)} roots, '
          f'{len(groups)} groups.')


if __name__ == '__main__':
    main()
