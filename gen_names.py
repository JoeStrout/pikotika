#!/usr/bin/env python3
"""Pour common given names into names.tsv, adapted from their pronunciation.

    python3 gen_names.py            merge into names.tsv
    python3 gen_names.py --dry-run  report what would change, write nothing

Two sources, cached in private/names-src/ and downloaded on first use:

  CMUdict      the pronunciations.  It does not say which of its 135,166
               entries are names -- *sandwich* and *smith* look alike to it --
               so it cannot be the name list as well.
  NLTK names   the name list: 7,944 given names, of which about 4,900 have a
               CMUdict pronunciation.

The forms are derived by web/js/adapt.js under node, the same code the site
runs and build.py:check_adapter re-verifies, so a poured row is checked against
its own `phones` exactly like a hand-written one.

Rows already in names.tsv are never touched: a curated adaptation outranks a
generated one, and several of them exist precisely because CMUdict records an
anglicized pronunciation we do not want (see build.py:ADAPTER_EXCEPTIONS).
"""

import argparse
import csv
import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import pikotika

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "private" / "names-src"
NAMES = ROOT / "names.tsv"

CMU_URL = "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
NLTK_URL = ("https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/"
            "packages/corpora/names.zip")

# What a poured row looks like.  Every one is a person's given name, which is
# also what keeps it out of the generated audio (build.py:wants_audio).
CATEGORY = "People and society"
ORIGIN = "cmudict"


def fetch(url: str, path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"  fetching {url}")
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    return path


def pronunciations() -> dict:
    """word -> ARPAbet, first pronunciation only.

    CMUdict lists alternates as word(2), word(3); the first is the common one
    and choosing among them is not something this can do."""
    out = {}
    text = fetch(CMU_URL, CACHE / "cmudict.dict").read_text(
        encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if not line.strip() or line.startswith(";;;"):
            continue
        word, _, rest = line.partition(" ")
        if "(" in word:
            continue
        out[word.lower()] = rest.split("#")[0].strip()
    return out


def given_names() -> list:
    data = fetch(NLTK_URL, CACHE / "nltk-names.zip").read_bytes()
    names = set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.namelist():
            if not member.endswith((".txt",)) or "names/" not in member:
                continue
            for line in archive.read(member).decode("utf-8", "replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    names.add(line.lower())
    return sorted(names)


def adapt(pairs: list) -> list:
    """Run adapt.js over [(name, phones), ...] and return the Pikotika forms."""
    node = shutil.which("node")
    if not node:
        raise SystemExit("gen_names.py needs node to run web/js/adapt.js")
    driver = """
      const adapt = require(process.argv[1]);
      const rows = JSON.parse(process.argv[2]);
      console.log(JSON.stringify(rows.map(function (r) {
        const form = adapt.adaptPhones(r[1], r[0]).form;
        return form ? form.charAt(0).toUpperCase() + form.slice(1) : '';
      })));
    """
    proc = subprocess.run(
        [node, "-e", driver, str(ROOT / "web" / "js" / "adapt.js"),
         json.dumps(pairs)],
        capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit("adapt.js failed:\n" + proc.stderr.strip())
    return json.loads(proc.stdout)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="report, write nothing")
    ap.add_argument("--limit", type=int, help="only the first N names")
    args = ap.parse_args()

    rows = list(csv.reader(NAMES.open(newline=""), **pikotika.TSV))
    head, body = rows[0], rows[1:]
    if "origin" not in head:
        head = head + ["origin"]
        body = [row + [""] for row in body]
    col = {name: i for i, name in enumerate(head)}

    have = {row[col["EN"]].lower() for row in body}
    curated = [row for row in body if row[col["origin"]] != ORIGIN]

    phones = pronunciations()
    wanted = [n for n in given_names() if n in phones and n not in have]
    if args.limit:
        wanted = wanted[:args.limit]
    print(f"  {len(wanted)} names with a pronunciation and no row yet")

    forms = adapt([[n, phones[n]] for n in wanted])
    tables = pikotika.Tables()

    # Pikotika draws fewer distinctions than English does, so names collapse:
    # Aaron, Aron, Ellen and Helen are all Eran.  One row per form, with the
    # English names sharing the EN cell exactly as compounds.tsv does.
    merged = {}
    for name, form in zip(wanted, forms):
        if not form:
            continue
        merged.setdefault(form, []).append(name)

    poured, shadowed = [], []
    for form, names in merged.items():
        name = names[0]
        # A name that spells an existing word is kept, not dropped: case tells
        # them apart everywhere but sentence-initially, where DETAILS.md's own
        # answer is to write `omo Mira`.  Counted, though -- it is worth knowing
        # how often the two collide.
        if pikotika.segment(form.lower(), tables) is not None:
            shadowed.append(f"{name} -> {form}")
        row = [""] * len(head)
        row[col["EN"]] = "; ".join(n.capitalize() for n in names)
        row[col["form"]] = form
        row[col["kind"]] = "name"
        row[col["categories"]] = CATEGORY
        row[col["phones"]] = phones[name]
        row[col["origin"]] = ORIGIN
        poured.append(row)

    print(f"  {len(poured)} poured for {len(wanted)} names, "
          f"{len(curated)} curated rows kept")
    print(f"  {len(shadowed)} forms also spell an ordinary word, e.g. "
          f"{', '.join(shadowed[:5])}")

    if args.dry_run:
        print("  (dry run -- names.tsv not written)")
        return

    poured.sort(key=lambda r: r[col["form"]])
    with NAMES.open("w", newline="") as fh:
        csv.writer(fh, lineterminator="\n", **pikotika.TSV).writerows(
            [head] + curated + poured)
    print(f"  wrote {NAMES.relative_to(ROOT)}: "
          f"{len(curated) + len(poured)} rows")


if __name__ == "__main__":
    main()
