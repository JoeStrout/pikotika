#!/usr/bin/env python3
"""Count how often each root is used, into roots.tsv `usage_count`.

Two sources are counted, and the column holds their total: the example
sentences in corpus.tsv, and the standing compound lexicon in compounds.tsv
(one count per appearance of a root in a compound's gloss).

The corpus is read from its `han` column rather than `gloss` or `latin`:
one character is one root, so names and numerals sort themselves out in
parse_han and nothing here has to know a cast list.

Usage: python3 count_usage.py [--dry-run]
"""

import csv
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pikotika  # noqa: E402  (needs HERE on the path first)

ROOTS_TSV = os.path.join(HERE, 'roots.tsv')
CORPUS_TSV = os.path.join(HERE, 'corpus.tsv')
COLUMN = 'usage_count'


def read_corpus(path):
    """The non-empty Han renderings of corpus.tsv, one per sentence."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, **pikotika.TSV)
        return [han for han in ((row.get('han') or '').strip()
                                for row in reader) if han]


def count_corpus(lines, t):
    """Counter of gloss -> uses, plus the sentences that would not parse."""
    counts = Counter()
    skipped = Counter()
    for line in lines:
        words = pikotika.parse_han(line, t)
        if words is None:
            skipped[line] += 1
            continue
        for word in words:
            # punctuation comes back as the bare string it was, and a written
            # numeral as one ("NUMERAL", text, reading) tuple rather than a
            # list of glosses -- its reading spells out the digits, and those
            # are not roots anyone chose
            if pikotika.is_punct(word) or pikotika.is_numeral(word):
                continue
            for gloss in word:
                # names, numbers and punctuation ride along as tuples
                if not isinstance(gloss, tuple):
                    counts[gloss] += 1
    return counts, skipped


def count_compounds(t):
    """Counter of gloss -> uses across every compound gloss in compounds.tsv."""
    counts = Counter()
    skipped = Counter()
    for gloss in t.compound_by_gloss:
        for part in re.split(r'[-\s]+', gloss.strip()):
            if not part:
                continue
            if part in t.gloss2root:
                counts[part] += 1
            else:
                skipped[part] += 1
    return counts, skipped


def counted_rows(path, counts):
    """The roots.tsv rows with `usage_count` filled in, plus the field order."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, **pikotika.TSV)
        fields = list(reader.fieldnames)
        rows = list(reader)
    if COLUMN not in fields:
        fields.append(COLUMN)
    for row in rows:
        row[COLUMN] = counts.get(row['gloss'], 0)
    return rows, fields


def rewrite(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields, lineterminator='\n',
                                **pikotika.TSV)
        writer.writeheader()
        writer.writerows(rows)


def main(argv):
    t = pikotika.Tables(HERE)
    lines = read_corpus(CORPUS_TSV)
    counts, skipped = count_corpus(lines, t)
    compound_counts, compound_skipped = count_compounds(t)
    counts += compound_counts
    skipped += compound_skipped

    if skipped:
        print('not counted (did not parse): '
              + ', '.join(f'{tok} x{n}' if n > 1 else tok
                          for tok, n in skipped.most_common()),
              file=sys.stderr)

    rows, fields = counted_rows(ROOTS_TSV, counts)
    if '--dry-run' not in argv:
        rewrite(ROOTS_TSV, rows, fields)

    used = sum(1 for r in rows if r[COLUMN])
    print(f'{len(lines)} corpus sentences + {len(t.compound_by_gloss)} '
          f'compounds, {sum(counts.values())} root uses; '
          f'{used} of {len(rows)} roots used, {len(rows) - used} unused')
    unused = [r['gloss'] for r in rows if not r[COLUMN]]
    if unused:
        print('unused: ' + ', '.join(unused))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
