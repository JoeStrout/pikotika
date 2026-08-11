#!/usr/bin/env python3
"""Count how often each root is used in DIALOGS.md, into roots.tsv `usage_count`.

The dialogs are the only running corpus in the repo, so they are the best
evidence for which roots are earning their place.  Only the dialogs themselves
are counted -- the notes after them requote lines that were already counted.

Usage: python3 count_usage.py [--dry-run]
"""

import csv
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pikotise  # noqa: E402  (needs HERE on the path first)

ROOTS_TSV = os.path.join(HERE, 'roots.tsv')
DIALOGS_MD = os.path.join(HERE, 'DIALOGS.md')
COLUMN = 'usage_count'

# every Pikotise line in the dialogs is a blockquote holding one bold run
LINE = re.compile(r'^>\s*\*\*(.+?)\*\*')
# the dialogs end where the commentary starts; after this the same lines recur
END = re.compile(r'^##\s+Notes\b')
# the dialogs open by declaring their cast: "Names used here: **Aris** (Alice), ..."
CAST = re.compile(r'^Names used here:')
BOLD = re.compile(r'\*\*(.+?)\*\*')


def read_dialogs(path):
    """Return (Pikotise lines, names the dialogs declare)."""
    lines, names, in_cast = [], set(), False
    with open(path, encoding='utf-8') as f:
        for line in f:
            if END.match(line):
                break
            if CAST.match(line):
                in_cast = True
            if in_cast:
                names.update(n.lower() for n in BOLD.findall(line))
                if line.rstrip().endswith('.'):
                    in_cast = False
                continue
            found = LINE.match(line)
            if found:
                lines.append(found.group(1))
    return lines, names


def count_roots(lines, names, t):
    """Counter of gloss -> uses, plus the tokens that were not roots at all.

    Counting is per word rather than per line: a name or an interjection the
    parser does not know should cost that one token, not the whole sentence.
    """
    counts = Counter()
    skipped = Counter()
    for line in lines:
        for token in pikotise.tokenize(line):
            if pikotise.is_punct_text(token):
                continue
            # Names are capitalized wherever they stand, so capitalization is
            # what separates the name **Ar** (Hal) from the root `ar` 'other'.
            # It cannot separate a sentence-initial one, but no such case
            # occurs; if one ever does, the name reading is the one taken.
            if token[:1].isupper() and token.lower() in names:
                continue
            words = pikotise.parse_latin(token, t)
            if words is None:
                skipped[token] += 1
                continue
            for word in words:
                for gloss in word:
                    # names and numbers ride along as tuples; not roots
                    if not isinstance(gloss, tuple):
                        counts[gloss] += 1
    return counts, skipped


def counted_rows(path, counts):
    """The roots.tsv rows with `usage_count` filled in, plus the field order."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        fields = list(reader.fieldnames)
        rows = list(reader)
    if COLUMN not in fields:
        fields.append(COLUMN)
    for row in rows:
        row[COLUMN] = counts.get(row['gloss'], 0)
    return rows, fields


def rewrite(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields, delimiter='\t',
                                lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main(argv):
    t = pikotise.Tables(HERE)
    lines, names = read_dialogs(DIALOGS_MD)
    names |= {form.lower() for form in t.form2name}
    counts, skipped = count_roots(lines, names, t)

    if skipped:
        print('not counted (no such root): '
              + ', '.join(f'{tok} x{n}' if n > 1 else tok
                          for tok, n in skipped.most_common()),
              file=sys.stderr)

    rows, fields = counted_rows(ROOTS_TSV, counts)
    if '--dry-run' not in argv:
        rewrite(ROOTS_TSV, rows, fields)

    used = sum(1 for r in rows if r[COLUMN])
    print(f'{len(lines)} dialog lines, {sum(counts.values())} root uses; '
          f'{used} of {len(rows)} roots used, {len(rows) - used} unused')
    unused = [r['gloss'] for r in rows if not r[COLUMN]]
    if unused:
            print('unused: ' + ', '.join(unused))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
