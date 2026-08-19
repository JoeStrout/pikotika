#!/usr/bin/env python3
"""Track which *sense* of each root is the best fit at each place it is used.

`covers` lists the senses a root is meant to span, but nothing so far says which
of them the language actually leans on.  Answering that is a judgment call per
occurrence -- a human or an LLM has to make it -- so this script does everything
around the judging: it enumerates the occurrences, hands them over one root at a
time to be filled in, validates what comes back, and totals the result.

The verdicts live in senses.tsv, never in anyone's head.  One row per
occurrence, keyed by (gloss, source, item, occ); the file is only ever appended
to, so an interrupted sweep resumes at a root boundary with nothing lost.

The two sources are the ones count_usage.py totals, enumerated the same way:
every root of every compound gloss in compounds.tsv, and every root of the `han`
column in corpus.tsv (one character is one root, so names and numerals sort
themselves out in parse_han).

Commands:

  todo [-n N]          roots still unjudged, most-used first, with progress
  emit <root>          the fill-in block for one root, senses left blank
  commit <file>        validate a filled-in block and append it to senses.tsv
  check                validate all of senses.tsv against the enumeration
  report [-o FILE]     the sense tallies (markdown; stdout unless -o)
  summary [-o FILE]    the same tallies, one line per root (text)

Fill in a block by writing one of the root's listed senses in the `sense`
column.  Any unambiguous prefix will do -- it is stored expanded.  Two values
are always legal and are the point of the exercise:

  *   no listed sense fits this use    (note required)
  ?   genuinely ambiguous here         (note required)

A root's own gloss counts as a sense whether or not `covers` repeats it.
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pikotika  # noqa: E402  (needs HERE on the path first)

ROOTS_TSV = os.path.join(HERE, 'roots.tsv')
CORPUS_TSV = os.path.join(HERE, 'corpus.tsv')
COMPOUNDS_TSV = os.path.join(HERE, 'compounds.tsv')
SENSES_TSV = os.path.join(HERE, 'senses.tsv')

FIELDS = ['gloss', 'source', 'item', 'occ', 'sense', 'note']
UNLISTED = '*'
AMBIGUOUS = '?'
SPECIAL = {UNLISTED: 'no listed sense fits',
           AMBIGUOUS: 'ambiguous in context'}


# --- reading -----------------------------------------------------------------

def rows_of(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, **pikotika.TSV))


def unquote(cell):
    """A cell's text without the literal quote characters some of them carry.

    roots.tsv is unquoted TSV, so a `"` in `covers` is data rather than a
    wrapper -- but the wrapping pair is punctuation nobody means, so drop it.
    """
    cell = (cell or '').strip()
    if len(cell) > 1 and cell[0] == '"' and cell[-1] == '"':
        cell = cell[1:-1]
    return cell.strip()


def senses_of(row):
    """The senses a root may be judged to carry, its own gloss first.

    22 roots have a `covers` list that does not repeat the gloss (`life` covers
    'alive, live, birth, grow'), and for those the plainest reading of the root
    would otherwise be unrecordable.
    """
    gloss = row['gloss']
    listed = [s.strip() for s in unquote(row.get('covers')).split(',')
              if s.strip()]
    return listed if gloss in listed else [gloss] + listed


def load_roots():
    """gloss -> its sense list, in the order they should be offered."""
    return {r['gloss']: senses_of(r) for r in rows_of(ROOTS_TSV)}


# --- enumerating the occurrences ---------------------------------------------

def compound_occurrences():
    """(gloss, 'compound', item, occ, context) for every root of every compound.

    The item key is the compound's own gloss, which compounds.tsv holds one row
    of; the context shown alongside is its English.
    """
    out = []
    for row in rows_of(COMPOUNDS_TSV):
        item = (row.get('gloss') or '').strip()
        if not item:
            continue
        context = (row.get('EN') or '').strip()
        seen = Counter()
        for part in re.split(r'[-\s]+', item):
            if not part:
                continue
            seen[part] += 1
            out.append((part, 'compound', item, seen[part], context))
    return out


def corpus_occurrences(t):
    """(gloss, 'corpus', item, occ, context) for every root of every sentence.

    Keyed on the Latin rendering, which is unique across corpus.tsv and stays
    readable; parsed from `han` for the reason count_usage.py parses it there.
    """
    out = []
    for row in rows_of(CORPUS_TSV):
        han = (row.get('han') or '').strip()
        item = (row.get('latin') or '').strip()
        if not han or not item:
            continue
        words = pikotika.parse_han(han, t)
        if words is None:
            continue
        context = (row.get('EN') or '').strip()
        seen = Counter()
        for word in words:
            if pikotika.is_punct(word) or pikotika.is_numeral(word):
                continue
            for gloss in word:
                if isinstance(gloss, tuple):
                    continue  # a name or numeral riding along
                seen[gloss] += 1
                out.append((gloss, 'corpus', item, seen[gloss], context))
    return out


def all_occurrences(t):
    """Every judgeable occurrence, compounds first then corpus."""
    return compound_occurrences() + corpus_occurrences(t)


def key_of(occurrence):
    return occurrence[0], occurrence[1], occurrence[2], str(occurrence[3])


# --- the ledger ---------------------------------------------------------------

def load_senses():
    if not os.path.exists(SENSES_TSV):
        return []
    return rows_of(SENSES_TSV)


def judged_keys(ledger):
    return {(r['gloss'], r['source'], r['item'], str(r['occ']).strip())
            for r in ledger}


def append_senses(rows):
    exists = os.path.exists(SENSES_TSV)
    with open(SENSES_TSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, FIELDS, lineterminator='\n', **pikotika.TSV)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def resolve_sense(value, senses):
    """The canonical sense `value` names, or None if it names none or several.

    Exact match wins; otherwise an unambiguous case-insensitive prefix, so a
    long entry like 'hurting (pain = `sick-feel`)' can be filled in as 'hurt'.
    """
    value = value.strip()
    if value in SPECIAL:
        return value
    if value in senses:
        return value
    if value.isdigit() and 1 <= int(value) <= len(senses):
        return senses[int(value) - 1]
    lowered = value.lower()
    hits = [s for s in senses if s.lower().startswith(lowered)]
    if len(hits) == 1:
        return hits[0]
    if lowered in [s.lower() for s in senses]:
        return next(s for s in senses if s.lower() == lowered)
    return None


# --- commands -----------------------------------------------------------------

def cmd_todo(args, t, roots, occurrences, ledger):
    done = judged_keys(ledger)
    pending = Counter()
    total = Counter()
    for occ in occurrences:
        total[occ[0]] += 1
        if key_of(occ) not in done:
            pending[occ[0]] += 1

    n_done = len(occurrences) - sum(pending.values())
    roots_left = len(pending)
    print(f'{n_done} of {len(occurrences)} occurrences judged; '
          f'{roots_left} of {len(total)} roots still open')
    if not pending:
        print('sweep complete -- run `report`')
        return 0

    print()
    limit = args.limit or len(pending)
    for gloss, n in pending.most_common(limit):
        senses = roots.get(gloss, [])
        print(f'  {gloss:<12} {n:>4} left of {total[gloss]:<4} '
              f'({len(senses)} senses)')
    if limit < roots_left:
        print(f'  ... and {roots_left - limit} more')
    return 0


def pending_by_root(roots, occurrences, ledger):
    """gloss -> its unjudged occurrences, for roots that still have some."""
    done = judged_keys(ledger)
    pending = defaultdict(list)
    for o in occurrences:
        if key_of(o) not in done:
            pending[o[0]].append(o)
    return pending


def cmd_emit(args, t, roots, occurrences, ledger):
    pending = pending_by_root(roots, occurrences, ledger)

    if args.top:
        wanted = [g for g, _ in sorted(pending.items(),
                                       key=lambda kv: (-len(kv[1]), kv[0]))]
        chosen, budget = [], args.top
        for gloss in wanted:
            if chosen and len(pending[gloss]) > budget:
                break
            chosen.append(gloss)
            budget -= len(pending[gloss])
    else:
        chosen = []
        for name in args.roots:
            gloss = name if name in roots else t.form2gloss.get(name, name)
            if gloss not in roots:
                print(f'no such root: {name}', file=sys.stderr)
                return 1
            chosen.append(gloss)

    lines, n = [], 0
    for gloss in chosen:
        mine = pending.get(gloss, [])
        lines.append(f'# ===== {t.form_of(gloss)} = {gloss}   '
                     f'({len(mine)} to judge)')
        for i, s in enumerate(roots[gloss], 1):
            lines.append(f'#   {i}. {s}')
        if not mine:
            lines.append('# nothing left for this root')
            continue
        for g, source, item, occ, context in mine:
            n += 1
            # `occ` is which use within the item, and it matters: one sentence
            # can use a root three times in three different senses, and the
            # English alone will not say which is which
            where = f'{source} {occ}' if occ > 1 else source
            lines.append(f'# [{n}] {where} | {item} | {context}')
            lines.append('\t'.join([g, source, item, str(occ), '', '']))

    header = ['# answer each numbered row in an answers file, one line of',
              '#   <n><TAB><sense><TAB><note>',
              f'# sense: a listed sense (any unambiguous prefix), its number, '
              f'or {UNLISTED}/{AMBIGUOUS} (note then required)',
              '\t'.join(FIELDS)]
    text = '\n'.join(header[:3] + [header[3]] + lines) + '\n'

    if not args.output:
        sys.stdout.write(text)
        return 0

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(text)
    # The work file keeps the keys; what gets shown is only what a judgment
    # needs -- the sense menu, the row number, and the use in context.
    for line in lines:
        if line.startswith('#'):
            print(line[2:] if line.startswith('# [') else line[1:].rstrip())
    print(f'\n-- {args.output}: {n} occurrences across {len(chosen)} root(s)')
    return 0


def cmd_commit(args, t, roots, occurrences, ledger):
    by_key = {key_of(o): o for o in occurrences}
    done = judged_keys(ledger)

    with open(args.file, newline='', encoding='utf-8') as f:
        lines = [ln for ln in f.read().splitlines()
                 if ln.strip() and not ln.lstrip().startswith('#')]
    if not lines:
        print('nothing to commit', file=sys.stderr)
        return 1
    if lines[0].split('\t')[0] == 'gloss':
        lines = lines[1:]

    # The answers file addresses rows by their position in the work file, so
    # the long Latin keys never have to be copied back out by hand.
    answers = {}
    if args.answers:
        with open(args.answers, encoding='utf-8') as f:
            for ln in f.read().splitlines():
                if not ln.strip() or ln.lstrip().startswith('#'):
                    continue
                parts = ln.split('\t')
                if not parts[0].strip().isdigit():
                    print(f'answers: not a row number: {ln!r}', file=sys.stderr)
                    return 1
                idx = int(parts[0].strip())
                answers[idx] = (parts[1].strip() if len(parts) > 1 else '',
                                parts[2].strip() if len(parts) > 2 else '')
        extra = sorted(set(answers) - set(range(1, len(lines) + 1)))
        if extra:
            print(f'answers: no such row(s): {extra}', file=sys.stderr)
            return 1
        missing = sorted(set(range(1, len(lines) + 1)) - set(answers))
        if missing:
            print(f'answers: {len(missing)} row(s) unanswered: '
                  f'{missing[:20]}{" ..." if len(missing) > 20 else ""}',
                  file=sys.stderr)
            return 1

    out, errors, seen = [], [], set()
    for n, line in enumerate(lines, 1):
        parts = line.split('\t')
        if len(parts) < 5:
            errors.append(f'line {n}: expected {len(FIELDS)} columns, '
                          f'got {len(parts)}')
            continue
        gloss, source, item, occ, sense = (p.strip() for p in parts[:5])
        note = parts[5].strip() if len(parts) > 5 else ''
        if n in answers:
            sense, note = answers[n]
        key = (gloss, source, item, occ)

        if key not in by_key:
            errors.append(f'line {n}: no such occurrence: {key}')
            continue
        if key in done:
            errors.append(f'line {n}: already judged: {key}')
            continue
        if key in seen:
            errors.append(f'line {n}: duplicated in this block: {key}')
            continue
        if not sense:
            errors.append(f'line {n}: sense is blank')
            continue
        canonical = resolve_sense(sense, roots[gloss])
        if canonical is None:
            errors.append(f'line {n}: {sense!r} is not a sense of {gloss} '
                          f'({", ".join(roots[gloss])})')
            continue
        if canonical in SPECIAL and not note:
            errors.append(f'line {n}: {canonical} requires a note')
            continue

        seen.add(key)
        out.append(dict(gloss=gloss, source=source, item=item, occ=occ,
                        sense=canonical, note=note))

    if errors:
        print(f'{len(errors)} problem(s), nothing written:', file=sys.stderr)
        for e in errors:
            print('  ' + e, file=sys.stderr)
        return 1

    append_senses(out)
    glosses = sorted({r['gloss'] for r in out})
    print(f'committed {len(out)} judgments for {", ".join(glosses)}')

    still = sum(1 for o in occurrences
                if o[0] in set(glosses) and key_of(o) not in done | seen)
    if still:
        print(f'{still} occurrence(s) of those roots still unjudged')
    return 0


def cmd_check(args, t, roots, occurrences, ledger):
    by_key = {key_of(o) for o in occurrences}
    problems, seen = [], set()
    for n, row in enumerate(ledger, 2):  # 2: header is line 1
        key = (row['gloss'], row['source'], row['item'],
               str(row['occ']).strip())
        if key in seen:
            problems.append(f'line {n}: duplicate key {key}')
        seen.add(key)
        if key not in by_key:
            problems.append(f'line {n}: orphan -- no such occurrence {key}')
            continue
        sense = (row.get('sense') or '').strip()
        if sense not in SPECIAL and sense not in roots.get(row['gloss'], []):
            problems.append(f'line {n}: {sense!r} is not a sense of '
                            f'{row["gloss"]}')
        if sense in SPECIAL and not (row.get('note') or '').strip():
            problems.append(f'line {n}: {sense} with no note')

    missing = len(by_key - seen)
    for p in problems:
        print(p, file=sys.stderr)
    print(f'{len(ledger)} judgments, {len(problems)} problem(s), '
          f'{missing} occurrence(s) not yet judged')
    return 1 if problems else 0


def ordered_senses(counts, senses):
    """The senses of one root, most-used first, ties in `covers` order."""
    return sorted(counts, key=lambda s: (-counts[s], senses.index(s)
                                         if s in senses else 99))


def cmd_report(args, t, roots, occurrences, ledger):
    out = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout

    tally = defaultdict(Counter)      # gloss -> sense -> count
    split = defaultdict(Counter)      # (gloss, sense) -> source -> count
    notes = defaultdict(list)         # gloss -> (sense, item, note)
    for row in ledger:
        gloss, sense = row['gloss'], (row.get('sense') or '').strip()
        tally[gloss][sense] += 1
        split[(gloss, sense)][row['source']] += 1
        note = (row.get('note') or '').strip()
        if note:
            notes[gloss].append((sense, row['item'], note))

    total = Counter(o[0] for o in occurrences)
    judged = Counter(r['gloss'] for r in ledger)

    print('# Root senses as actually used\n', file=out)
    print(f'{sum(judged.values())} of {sum(total.values())} occurrences judged '
          f'across {len(total)} roots.  Counts are `corpus + compound`; a sense '
          f'attested only in compounds is weaker evidence, since a lexicalized '
          f'compound\'s literal parse is a mnemonic rather than a derivation.\n',
          file=out)
    print(f'`{UNLISTED}` marks a use that no listed sense fits, `{AMBIGUOUS}` '
          f'one that is genuinely ambiguous.  Senses listed in `covers` but '
          f'never attested are called out per root.\n', file=out)

    for gloss in sorted(tally, key=lambda g: (-total[g], g)):
        senses = roots.get(gloss, [])
        counts = tally[gloss]
        head = f'## {t.form_of(gloss)} — *{gloss}*'
        if judged[gloss] < total[gloss]:
            head += f'  ({judged[gloss]} of {total[gloss]} judged)'
        print(head + '\n', file=out)
        print('| sense | uses | corpus | compound |', file=out)
        print('|---|---:|---:|---:|', file=out)
        for sense in ordered_senses(counts, senses):
            s = split[(gloss, sense)]
            label = f'`{sense}`' if sense in SPECIAL else sense
            print(f'| {label} | {counts[sense]} | {s["corpus"]} | '
                  f'{s["compound"]} |', file=out)
        unattested = [s for s in senses if s not in counts]
        if unattested:
            print(f'\nnever attested: {", ".join(unattested)}', file=out)
        if notes[gloss]:
            print('', file=out)
            for sense, item, note in notes[gloss]:
                # some `covers` entries hold backticks of their own, so only
                # the two special markers get quoted here
                label = f'`{sense}`' if sense in SPECIAL else sense
                print(f'- {label} in **{item}** — {note}', file=out)
        print('', file=out)

    if args.output:
        out.close()
        print(f'wrote {args.output}')
    return 0


def cmd_summary(args, t, roots, occurrences, ledger):
    """The whole sweep at a glance: one line per root, `report`'s order."""
    out = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout

    tally = defaultdict(Counter)      # gloss -> sense -> count
    for row in ledger:
        tally[row['gloss']][(row.get('sense') or '').strip()] += 1
    total = Counter(o[0] for o in occurrences)

    for gloss in sorted(tally, key=lambda g: (-total[g], g)):
        counts = tally[gloss]
        senses = ordered_senses(counts, roots.get(gloss, []))
        parts = ', '.join(f'{s} ({counts[s]})' for s in senses)
        print(f'{t.form_of(gloss)}: {parts}', file=out)

    if args.output:
        out.close()
        print(f'wrote {args.output}')
    return 0


COMMANDS = {'todo': cmd_todo, 'emit': cmd_emit, 'commit': cmd_commit,
            'check': cmd_check, 'report': cmd_report, 'summary': cmd_summary}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('todo', help='roots still unjudged, most-used first')
    p.add_argument('-n', '--limit', type=int, default=25)
    p = sub.add_parser('emit', help='the fill-in block for one or more roots')
    p.add_argument('roots', nargs='*')
    p.add_argument('--top', type=int, metavar='N',
                   help='instead: the most-used unjudged roots, ~N occurrences')
    p.add_argument('-o', '--output', help='write the block here, not to stdout')
    p = sub.add_parser('commit', help='validate a filled block and append it')
    p.add_argument('file')
    p.add_argument('-a', '--answers', metavar='FILE',
                   help='senses by row number, rather than filled into FILE')
    sub.add_parser('check', help='validate senses.tsv')
    p = sub.add_parser('report', help='the sense tallies, as markdown')
    p.add_argument('-o', '--output')
    p = sub.add_parser('summary', help='the sense tallies, one line per root')
    p.add_argument('-o', '--output')

    args = parser.parse_args(argv)
    t = pikotika.Tables(HERE)
    roots = load_roots()
    # The particles are out of scope: *RI*, *A* and *TE* have one sense each,
    # and `covers` only restates it in words ('predicate boundary'), so their
    # ~300 occurrences would be judged one way every time.
    roots = {g: s for g, s in roots.items() if not t.is_particle(g)}
    occurrences = [o for o in all_occurrences(t) if o[0] in roots]
    ledger = load_senses()
    return COMMANDS[args.command](args, t, roots, occurrences, ledger)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
