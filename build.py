#!/usr/bin/env python3
"""Build the pikotika.org static site into site/.

Everything the site shows is either a hand-written fragment in web/pages/ or,
later, generated from the .tsv tables.  There is no framework and no bundler:
the output is plain files at real URLs, one directory per section.

    python3 build.py            build into docs/
    python3 build.py --serve    build, then serve docs/ on :8000
"""

import argparse
import html.parser
import http.server
import functools
import re
import shutil
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
# docs/ rather than site/ because GitHub Pages, publishing from a branch, will
# serve the repository root or docs/ and nothing else.  The directory is
# committed: deploying is `python3 build.py` and a push.
OUT = ROOT / "docs"

SITE_URL = "https://pikotika.org"

# label, url, source fragment, <title>, meta description
PAGES = [
    ("Overview", "/",         "index.html",
     "Pikotika — a tiny language for real conversation",
     "A constructed international language of about 200 roots, built for travel "
     "and small talk. Learnable in a weekend and forgiving of accents."),
    ("Vocab",    "/vocab/",   "vocab.html",
     "Vocab — Pikotika",
     "Every Pikotika root, compound, name, and loanword, searchable."),
    ("Grammar",  "/grammar/", "grammar.html",
     "Grammar — Pikotika",
     "Pikotika grammar in full: rigid word order, no conjugation, nothing irregular."),
    ("Topics",   "/topics/",  "topics.html",
     "Topics — Pikotika",
     "How to talk about colors, feelings, numbers, time, food, and travel in Pikotika."),
    ("Tools",    "/tools/",   "tools.html",
     "Tools — Pikotika",
     "Convert between English, gloss, Latin, and Han; adapt a name; read a number."),
    ("Learn",    "/learn/",   "learn.html",
     "Learn — Pikotika",
     "A free Pikotika course with no account and no login. Fifty short lessons."),
    ("Why",      "/why/",     "why.html",
     "Why Pikotika",
     "Why a two-hundred-root auxiliary language is worth building."),
]

# --- Topics ----------------------------------------------------------------
# Seventeen situation-shaped pages under /topics/, grouped for the index.  A
# topic is written when web/pages/topics/<slug>.html exists; until then its
# card still appears, marked as not yet written, so the index shows the real
# shape of the section instead of a grid of links that 404.
#
# Navigation between topics is deliberately a hub and spoke (decided
# 2026-08-19): every topic page carries a "Back to Topics" link at the top and
# the bottom, added by the build, and nothing else.  A strip of all seventeen
# on every page was the alternative; it moves more of the section into reach
# but costs a row of chips on a page whose own content is the point, and the
# index -- cards, icons, groups -- is a better place to choose from than a
# chip row.  Reconsider if readers turn out to move sideways a lot.
#
#   slug, its Pikotika name, label, Han glyph (the fallback icon), and one
#   line of what you can say.  The Pikotika name is a word chip like any other,
#   so the build checks it and tapping it opens the entry -- the index teaches
#   seventeen words just by being browsed.
TOPIC_GROUPS = [
    ("Getting by", [
        ("numbers", "mesurtika", "Numbers", "\u4e00",
         "Counting, prices, and how many \u2014 with a reader that says any number aloud."),
        ("time", "oratika", "Telling time", "\u523b",
         "Clock time, half past, and early, late, and now."),
        ("dates", "tempokarta", "Dates and weekdays", "\u66dc",
         "Weekdays, months, and a live calendar in Pikotika names."),
        ("seasons", "anyoparte", "Seasons", "\u6728",
         "The four seasons, and the shape of the year."),
        ("money", "moni", "Money and shopping", "\u8d1d",
         "How much, too expensive, and paying for it."),
        ("travel", "veniire", "Travel and directions", "\u884c",
         "Getting there: left and right, near and far, and how you are going."),
        ("lodging", "tormikase", "Lodging", "\u5e8a",
         "A room for the night \u2014 checking in, keys, and what is included."),
    ]),
    ("People", [
        ("meeting", "sarve", "Meeting people", "\u4f1a",
         "Hello, your name, and where you are from."),
        ("smalltalk", "pikotika", "Small talk", "\u8a00",
         "The small talk the language is named for."),
        ("pleasantries", "pamtika", "Pleasantries and filler", "\u6069",
         "Please, thank you, sorry, and the words that fill a pause."),
        ("family", "parimen", "Family", "\u4eb2",
         "Parents, children, spouses, and who belongs to whom."),
        ("feelings", "senti", "Feelings", "\u5fc3",
         "Happy, tired, angry, surprised \u2014 and asking after someone."),
        ("health", "sana", "Health and the body", "\u533b",
         "Where it hurts, and how to ask for help."),
    ]),
    ("The world", [
        ("food", "komi", "Food and eating", "\u98df",
         "Eating, drinking, ordering, and the compounds that name every dish."),
        ("colors", "koror", "Colors", "\u8272",
         "Six color roots, and every other color built out of them."),
        ("weather", "ventomoto", "Weather", "\u96e8",
         "Rain, wind, sun, and hot and cold."),
        ("names", "nomen", "Names and loanwords", "\u540d",
         "Your own name in Pikotika, and the words it borrows outright."),
    ]),
]

TOPICS_URL = "/topics/"

# Where the index's cards get spliced into web/pages/topics.html.
TOPIC_CARDS_MARK = "<!--TOPIC-CARDS-->"


def topic_fragment_path(slug: str) -> Path:
    return WEB / "pages" / "topics" / f"{slug}.html"


def topic_icon(slug: str, han: str) -> str:
    """Art if it has been drawn, the Han character if it has not.

    Dropping web/images/topics/<slug>.svg in and rebuilding is the whole of
    adding an icon; nothing here needs editing for it."""
    for ext in ("svg", "png"):
        if (WEB / "images" / "topics" / f"{slug}.{ext}").is_file():
            return (f'<img class="topic-icon" src="/images/topics/{slug}.{ext}"'
                    f' alt="" width="72" height="72">')
    return f'<span class="topic-icon topic-icon-han han" aria-hidden="true">{han}</span>'


def topic_cards() -> str:
    """The index: one card per topic, grouped, with the unwritten ones inert."""
    out = []
    for group, topics in TOPIC_GROUPS:
        out.append('<section class="topic-group">')
        out.append(f"  <h2>{group}</h2>")
        out.append('  <ul class="topic-cards">')
        for slug, pk, label, han, blurb in topics:
            icon = topic_icon(slug, han)
            body = (f'{icon}\n        <span class="topic-text">'
                    f'\n          <span class="topic-name">{label}</span>'
                    f'\n          <span class="pk topic-pk" data-chip="off">{pk}</span>'
                    f'\n          <span class="topic-blurb">{blurb}</span>')
            if topic_fragment_path(slug).is_file():
                inner = (f'<a href="{TOPICS_URL}{slug}/">\n        {body}'
                         f'\n        </span>\n      </a>')
                cls = "topic-card"
            else:
                inner = (f'<div>\n        {body}'
                         f'\n          <span class="topic-soon">not written yet</span>'
                         f'\n        </span>\n      </div>')
                cls = "topic-card is-soon"
            out.append(f'    <li class="{cls}">{inner}</li>')
        out.append("  </ul>")
        out.append("</section>")
    return "\n".join(out)


BACK_TO_TOPICS = ('<p class="topic-back"><a href="/topics/">'
                  '\u2190 Back to Topics</a></p>')


def topic_pages() -> list:
    """(url, content, <title>, description) for every topic page written.

    The back links are added here rather than written into each fragment, so a
    topic page is just its content and the navigation cannot drift page to
    page."""
    pages = []
    for _group, topics in TOPIC_GROUPS:
        for slug, _pk, label, _han, blurb in topics:
            path = topic_fragment_path(slug)
            if not path.is_file():
                continue
            body = path.read_text(encoding="utf-8").strip("\n")
            content = "\n\n".join([BACK_TO_TOPICS, body,
                                    BACK_TO_TOPICS.replace(
                                        'topic-back"', 'topic-back is-end"')])
            pages.append((f"{TOPICS_URL}{slug}/", content,
                          f"{label} \u2014 Pikotika", blurb))
    return pages


# Built, but deliberately not in the navigation: pages for us, not for readers.
# `fragment` is a callable here rather than a filename under web/pages/.
UNLISTED = [
    ("/specimen/", "gen_specimen", "Han specimen — Pikotika",
     "Every character in the Pikotika Han font, with a per-glyph check that it "
     "actually came from that font."),
]

STATIC_DIRS = ["css", "js", "images", "fonts", "data", "audio"]

# Loose files copied to the output root.  CNAME is what keeps the custom domain
# attached across a redeploy; .nojekyll turns off the Jekyll pass that branch
# published Pages otherwise runs, which would drop anything beginning with `_`.
STATIC_FILES = ["CNAME", ".nojekyll"]


def asset_version(*parts: str) -> str:
    """A short content hash for a ?v= query on css and js.

    Without it a browser is free to keep serving the copy it already has --
    including the dev server's, which sends no Cache-Control at all, so a fresh
    tab can still run yesterday's JavaScript.  Hashing the content means the URL
    changes exactly when the file does, and never otherwise."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update((WEB / part).read_bytes())
    return digest.hexdigest()[:10]


def render(template: str, **fields) -> str:
    """Fill {{name}} placeholders.  Fails loudly on an unfilled one, since a
    literal {{title}} shipping to the site is the kind of thing nobody sees."""
    out = template
    for key, value in fields.items():
        out = out.replace("{{%s}}" % key, value)
    leftover = re.findall(r"\{\{(\w+)\}\}", out)
    if leftover:
        raise SystemExit(f"unfilled template fields: {sorted(set(leftover))}")
    return out


def nav_html(current_url: str) -> str:
    lines = []
    for label, url, *_ in PAGES:
        # A topic page is still "in" Topics: match the section, not the URL.
        here = current_url == url or (url != "/" and current_url.startswith(url))
        current = ' aria-current="page"' if here else ""
        lines.append(f'      <li><a href="{url}"{current}>{label}</a></li>')
    return "\n".join(lines)


class PkCollector(html.parser.HTMLParser):
    """Pull the text of every <span class="pk"> out of a page fragment.

    Chips are wrapped by JavaScript at page load, not here -- pages keep plain
    prose and the HTML stays readable.  What the build owes in exchange is that
    the *forms* are real, which is what this collects and check_forms verifies.
    A `.pk` that is not running Pikotika -- a word-order schema like S RI V A O
    -- opts out with data-check="off"."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []          # (text, line)
        self._depth = 0          # nesting depth inside the current .pk
        self._buf = []
        self._line = 0

    def handle_starttag(self, tag, attrs):
        if self._depth:
            self._depth += 1
            return
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if "pk" in classes and attrs.get("data-check") != "off":
            self._depth = 1
            self._buf = []
            self._line = self.getpos()[0]

    def handle_endtag(self, tag):
        if not self._depth:
            return
        self._depth -= 1
        if self._depth == 0:
            text = " ".join("".join(self._buf).split())
            if text:
                self.found.append((text, self._line))

    def handle_data(self, data):
        if self._depth:
            self._buf.append(data)


def pk_strings(fragment: str):
    parser = PkCollector()
    parser.feed(fragment)
    return parser.found


def authored_pages() -> list:
    """(url, content, <title>, description) for every reader-facing page.

    One list, used for the form check, for the audio, and for the build, so a
    page cannot be rendered without being checked or spoken."""
    pages = []
    for _label, url, fragment, title_tag, description in PAGES:
        content = (WEB / "pages" / fragment).read_text(encoding="utf-8")
        if url == TOPICS_URL:
            content = content.replace(TOPIC_CARDS_MARK, topic_cards())
        pages.append((url, content, title_tag, description))
    return pages + topic_pages()


def page_sentences() -> list:
    """Every multi-word Pikotika string on the site, in page order.

    These need audio just as the corpus does -- an example on the Overview page
    is not necessarily a corpus line -- and gen_audio reads them from here so
    there is one definition of what the site says out loud."""
    out = []
    for _url, text, _title, _description in authored_pages():
        for string, _line in pk_strings(text):
            if len(string.split()) > 1 and string not in out:
                out.append(string)
    return out


def audio_sentences() -> list:
    """Every utterance that needs a clip: corpus lines, then anything a page
    says.  Corpus first, so a sentence that appears in both keeps its corpus
    form.  gen_audio renders exactly this list, and check_audio verifies that
    what shipped still matches it -- one definition, two readers."""
    import csv
    import pikotika

    with (ROOT / "corpus.tsv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, **pikotika.TSV))
    wanted = []
    for latin in [(r.get("latin") or "").strip() for r in rows] + page_sentences():
        if latin and latin not in wanted:
            wanted.append(latin)
    return wanted


# Person names get no clip (decided 2026-08-19).  names.tsv is meant to grow to
# thousands of them, each of which would otherwise cost ~7 KB of generated
# audio for a word whose pronunciation is entirely regular and already spelled
# out.  Place names and loans keep theirs: those are vocabulary.  The category
# is the discriminator because it is already there and already means this.
NO_AUDIO_CATEGORY = "People and society"


def wants_audio(entry) -> bool:
    return not (entry.get("kind") == "name"
                and NO_AUDIO_CATEGORY in (entry.get("cats") or []))


def audio_words() -> list:
    """Every word that needs a clip: the lexicon, including the forms that
    appear only in page prose, minus the person names.

    gen_audio used to build the lexicon without the page-only forms, so a word
    written on a page but in no table -- monivaso, say -- silently had no
    audio.  Same arrangement as audio_sentences: this is the definition,
    gen_audio renders it, check_audio verifies what shipped."""
    import gen_lexicon
    import pikotika

    tables = pikotika.Tables()
    authored = authored_pages()
    forms = check_forms(tables, [(url, content) for url, content, _t, _d in authored])
    lexicon, _ = gen_lexicon.build(tables, forms)
    return sorted({entry["form"] for entry in lexicon["words"].values()
                   if wants_audio(entry)})


def check_audio(lexicon) -> None:
    """Warn when the shipped clips no longer match what the site says.

    Both halves: every sentence on the site, and every word in the lexicon.
    The word half exists because the same drift happened there -- three loans
    were respelled and their old clips stayed behind, which nothing noticed.

    Audio is generated by a separate pass that needs Kokoro and the `pikotika`
    environment, so this cannot fail the build -- anyone without that
    environment could then never build the site at all.  It has to be loud
    instead, because the failure is invisible: a sentence with no clip still
    gets a play button, and the button just disables itself when tapped.

    Editing an utterance is the case that bites, not adding one.  The clip is
    keyed by the exact text, so a corrected line leaves its old clip behind and
    arrives with none."""
    import json

    wanted = {
        "sentences": audio_sentences(),
        "words": sorted({e["form"] for e in lexicon["words"].values()
                         if wants_audio(e)}),
        "numbers": audio_numbers(),
    }
    for kind, texts in wanted.items():
        index = WEB / "audio" / f"{kind}.json"
        if not index.is_file():
            print(f"  ! no web/audio/{kind}.json -- run gen_audio.py")
            continue
        clips = json.loads(index.read_text(encoding="utf-8"))["clips"]
        missing = [t for t in texts if t not in clips]
        stale = [t for t in clips if t not in texts]
        if not missing and not stale:
            continue
        print(f"  ! {kind} audio is out of date: {len(texts)} on the site, "
              f"{len(clips)} clips")
        for label, items in (("no clip", missing), ("clip no longer used", stale)):
            for text in items[:6]:
                print(f"      {label}: {text}")
            if len(items) > 6:
                print(f"      ... and {len(items) - 6} more with {label}")
        print("    fix: micromamba run -n pikotika python gen_audio.py")


# Rows of names.tsv whose form is deliberately not what the pronunciation
# gives.  Each needs a reason: an exception nobody can justify is a bug that
# has been written down.
ADAPTER_EXCEPTIONS = {
    "Ivan": "the Russian /\u026a\u02c8van/, not the anglicized /\u02c8a\u026av\u0259n/ CMUdict records",
    "Lena": "the continental /\u02c8lena/, not the English /\u02c8lin\u0259/",
}


def check_adapter() -> None:
    """Check every name in names.tsv against its own recorded pronunciation.

    names.tsv carries a `phones` column (ARPAbet, from CMUdict), and the form
    beside it should be what adapt.js:adaptPhones makes of those phones.  That
    is the real test now: the forms are derived from sound, so checking them
    against the spelling fallback would only measure how badly English spells.

    A row with no phones is not checked -- there is nothing to check it
    against.  Needs node, and skips with a note when there is none, since a
    contributor without it should still be able to build."""
    import csv
    import json
    import shutil
    import subprocess

    import pikotika

    node = shutil.which("node")
    if not node:
        print("  (no node -- skipping the name adapter check)")
        return

    with (ROOT / "names.tsv").open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh, **pikotika.TSV) if r.get("phones")]

    driver = """
      const adapt = require(process.argv[1]);
      const rows = JSON.parse(process.argv[2]);
      console.log(JSON.stringify(rows.map(function (r) {
        const form = adapt.adaptPhones(r[2], r[0]).form;
        /* Names are capitalized; loans are ordinary lowercase words. */
        return r[3] === 'name' ? form.charAt(0).toUpperCase() + form.slice(1) : form;
      })));
    """
    # A poured row can carry several English names sharing one form; the first
    # is the one its phones were taken from, and the only one the AA tie-break
    # should look at.
    pairs = [[r["EN"].split(";")[0].strip(), r["form"], r["phones"], r["kind"]]
             for r in rows]
    proc = subprocess.run(
        [node, "-e", driver, str(WEB / "js" / "adapt.js"), json.dumps(pairs)],
        capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit("the name adapter would not run:\n" + proc.stderr.strip())

    got = json.loads(proc.stdout)
    problems = []
    for (english, want, phones, _kind), have in zip(pairs, got):
        if have == want:
            if english in ADAPTER_EXCEPTIONS:
                problems.append(f"{english}: {want!r} now falls out of {phones!r} "
                                f"-- drop it from ADAPTER_EXCEPTIONS")
        elif english not in ADAPTER_EXCEPTIONS:
            problems.append(f"{english}: names.tsv says {want!r}, but {phones!r} "
                            f"gives {have!r}")
    if problems:
        raise SystemExit("names.tsv disagrees with the pronunciations it "
                         "records:\n  " + "\n  ".join(problems))
    derived = len(pairs) - len(ADAPTER_EXCEPTIONS)
    print(f"  name adapter: {derived}/{len(pairs)} names derived from their "
          f"recorded pronunciation, {len(ADAPTER_EXCEPTIONS)} exceptions")


# --- the number reader (/topics/numbers/) ----------------------------------
# Every word a reading can be made of: the ten digits, the four named powers of
# ten, and the four words that join them -- the decimal point, `in` for a
# fraction, `in-hundred` for a percentage, and `sequence` for an ordinal.
# Written as glosses and resolved through the tables, so it is the same list
# pikotika.py counts with, and audio_numbers below is derived from it rather
# than typed out again.
NUMBER_GLOSSES = ["part", "in", "in-hundred", "sequence"]


def ordinal_glosses(tables) -> list:
    """The ordinals that have a standing compound: `one-sequence` and friends.

    Read out of compounds.tsv rather than listed here, because that is what
    decides the question -- an ordinal with an entry is one word and gets one
    clip, and `tets orten` said as two clips is exactly what having the entry
    is for.  Recording `hundred-sequence` later therefore gives *hundredth* a
    clip too; the build will then ask for `numbers.js` to be told about it, via
    the vocabulary check in check_numbers."""
    import pikotika

    numerals = set(pikotika.DIGITS.values())
    return sorted(gloss for gloss in tables.compound_by_gloss
                  if gloss.endswith("-sequence")
                  and gloss[:-len("-sequence")] in numerals)


def number_forms(tables) -> list:
    import pikotika

    glosses = (list(dict.fromkeys(pikotika.DIGITS.values())) + NUMBER_GLOSSES
               + ordinal_glosses(tables))
    return sorted({pikotika.render_latin(pikotika.parse_gloss(g, tables), tables)
                   for g in glosses})


def audio_numbers() -> list:
    """The clips the number reader chains together.

    A reading is unbounded -- there is no clip for `12345` and never can be --
    so this is the one thing on the site that is stitched from word clips
    rather than spoken whole.  They are therefore rendered again in a single
    voice: the site-wide word clips alternate between two speakers, which over
    `tekas pits kiru, tets katon wats tekas kins` would change speaker four
    times in one number."""
    import pikotika

    return number_forms(pikotika.Tables())


# What the number reader is checked over: every shape it accepts, at every
# size where the reading changes shape.  Small numbers are enumerated because
# that is where the special cases live (the dropped multiplier at 10, 100, and
# 1000); past that it is one per decade plus a handful of awkward ones.
def number_checks() -> list:
    cases = [str(n) for n in range(0, 121)]
    cases += [str(n) for n in (200, 500, 510, 678, 999, 1000, 1001, 1010, 1100,
                               2026, 9999, 10000, 12345, 100000, 999999,
                               1000000, 1000001, 1234567, 10000000, 999999999,
                               1000000000, 1000000000000, 12345678901234)]
    cases += ["0.5", "1.25", "3.14159", "0.007", "12.5", "1000.001"]
    cases += ["3/4", "1/2", "7/8", "2/3", "22/7", "1/1000"]
    cases += ["1%", "50%", "7.5%", "100%", "3/100", "0.5%", "1000%"]
    cases += ["1st", "2nd", "3rd", "7th", "10th", "11th", "21st", "42nd",
              "100th", "101st", "1000th", "1000000th", "12345th"]
    return cases


def check_numbers(tables) -> None:
    """Check web/js/numbers.js against pikotika.py, over every shape it reads.

    The reader is a port -- pikotika.counting_words and decimal_words already
    say how a numeral is read -- and a port is a second implementation, so the
    two get run over the same inputs on every build.  The comparison goes
    through the *written* form the port produces, so the check covers both
    halves of what it claims: that `3/4` is written **3 in 4**, and that
    **3 in 4** is said `tets in wats`.

    Needs node, and skips with a note when there is none, exactly as
    check_adapter does."""
    import json
    import shutil
    import subprocess

    import pikotika

    node = shutil.which("node")
    if not node:
        print("  (no node -- skipping the number reader check)")
        return

    cases = number_checks()
    driver = """
      const numbers = require(process.argv[1]);
      console.log(JSON.stringify({
        vocabulary: numbers.vocabulary(),
        read: JSON.parse(process.argv[2]).map(function (s) {
          return numbers.read(s);
        })
      }));
    """
    proc = subprocess.run(
        [node, "-e", driver, str(WEB / "js" / "numbers.js"), json.dumps(cases)],
        capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit("the number reader would not run:\n" + proc.stderr.strip())

    result = json.loads(proc.stdout)
    problems = []
    # The clips are generated from number_forms(); if the reader can say a word
    # that is not in it, that word is silent and nothing else would notice.
    want = number_forms(tables)
    if result["vocabulary"] != want:
        extra = [f for f in result["vocabulary"] if f not in want]
        short = [f for f in want if f not in result["vocabulary"]]
        problems.append(
            f"numbers.js and build.number_forms disagree about what the reader "
            f"can say: {extra} only in numbers.js (those would be silent -- "
            f"nothing renders a clip for them), {short} only in build.py "
            f"(those would be clips nothing plays; if one is a newly recorded "
            f"ordinal, ORDINAL_CLIPS in numbers.js needs it)")
    for case, got in zip(cases, result["read"]):
        if not got.get("ok"):
            problems.append(f"{case}: the reader refused it "
                            f"({got.get('error', 'no reason given')})")
            continue
        fail = {}
        words = pikotika.parse_latin(got["spelled"], tables, fail)
        if words is None:
            problems.append(f"{case}: spells out {got['spelled']!r}, which is "
                            f"not Pikotika ({fail.get('token')!r})")
            continue
        spoken = pikotika.expand_numerals(words)
        for label, want in (("latin", pikotika.render_latin(spoken, tables)),
                            ("gloss", pikotika.render_gloss(spoken, tables)),
                            ("han", pikotika.render_han(words, tables))):
            if got[label] != want:
                problems.append(f"{case}: {label} is {got[label]!r} in "
                                f"numbers.js, {want!r} in pikotika.py")
        # pikotika.py reads `/` and `%` as well, so most cases can also be
        # compared as typed, with no spelled-out form in between.  An ordinal
        # cannot: `7th` is English, and only its reading is Pikotika.
        raw = pikotika.parse_latin(case, tables)
        if raw is not None:
            said = pikotika.render_latin(pikotika.expand_numerals(raw), tables)
            if said != got["latin"]:
                problems.append(f"{case}: read as typed, pikotika.py says "
                                f"{said!r} where numbers.js says {got['latin']!r}")
    if problems:
        raise SystemExit("the number reader disagrees with pikotika.py:\n  "
                         + "\n  ".join(problems))
    print(f"  number reader: {len(cases)} numbers read the same in "
          f"numbers.js and pikotika.py")


def check_forms(tables, sources) -> list:
    """Parse every Pikotika string on the site; fail on a form that is not real.

    This is the build-time half of the word chips.  Returns the forms in use,
    which gen_lexicon folds into lexicon.json so that a word written only in
    page prose still has an entry for its chip to open."""
    import pikotika

    forms, problems = [], []
    for label, fragment in sources:
        for text, line in pk_strings(fragment):
            fail = {}
            words = pikotika.parse_latin(text, tables, fail)
            if words is None:
                token = fail.get("token", text)
                problems.append(f"{label}:{line}: no such word {token!r}  "
                                f"in {text!r}")
                continue
            for word in words:
                if not pikotika.is_punct(word):
                    forms.append(pikotika.render_latin([word], tables))
    if problems:
        raise SystemExit("Pikotika in the pages does not check out:\n  "
                         + "\n  ".join(problems)
                         + "\n(mark a non-Pikotika span data-check=\"off\")")
    return forms


def check_fonts() -> None:
    """Refuse to ship a Han face that is missing a character.  A tofu box turns
    up on the one page that uses that root, and nobody notices for months."""
    import gen_han_font
    from fontTools.ttLib import TTFont

    wanted = gen_han_font.wanted_chars()
    for _, slug, _, _ in gen_han_font.FACES:
        path = WEB / "fonts" / f"pikotika-han-{slug}.woff2"
        if not path.exists():
            raise SystemExit(f"{path} is missing -- run python3 gen_han_font.py")
        gen_han_font.verify(TTFont(str(path)), wanted, path.name)


def build() -> None:
    import gen_lexicon
    import pikotika

    check_fonts()
    check_adapter()

    tables = pikotika.Tables()
    check_numbers(tables)
    authored = authored_pages()
    forms = check_forms(tables, [(url, content)
                                 for url, content, _t, _d in authored])
    lexicon, unresolved = gen_lexicon.build(tables, forms)
    if unresolved:
        raise SystemExit(f"cannot build a lexicon entry for: {unresolved}")
    path = gen_lexicon.write(lexicon)
    print(f"  {len(forms)} words checked; {len(lexicon['words'])} in "
          f"{path.relative_to(ROOT)}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for name in STATIC_DIRS:
        src = WEB / name
        if src.is_dir():
            shutil.copytree(src, OUT / name,
                            ignore=shutil.ignore_patterns(".DS_Store", "*.swp"))

    for name in STATIC_FILES:
        src = WEB / name
        if src.is_file():
            shutil.copy2(src, OUT / name)

    template = (WEB / "templates" / "base.html").read_text(encoding="utf-8")
    css_version = asset_version("css/site.css")
    js_version = asset_version("js/site.js")
    adapt_version = asset_version("js/adapt.js")
    numbers_version = asset_version("js/numbers.js")
    # The lexicon and the two audio indexes are rebuilt in place under the same
    # names, so they need the same cache-busting; site.js reads this off its own
    # script tag.  Computed after gen_lexicon.write above, or it would hash the
    # previous build's lexicon.
    data_version = asset_version("data/lexicon.json", "audio/words.json",
                                 "audio/sentences.json", "audio/numbers.json")

    import importlib

    pages = list(authored)
    pages += [(url, importlib.import_module(module).fragment(),
               title_tag, description)
              for url, module, title_tag, description in UNLISTED]

    for url, content, title_tag, description in pages:
        html = render(
            template,
            title_tag=title_tag,
            description=description,
            site_url=SITE_URL,
            url=url,
            nav=nav_html(url),
            css_version=css_version,
            js_version=js_version,
            adapt_version=adapt_version,
            numbers_version=numbers_version,
            data_version=data_version,
            # The topic index is a card grid; the measure column is for prose.
            main_class="wide" if url == TOPICS_URL else "",
            content=content.rstrip("\n"),
        )
        target = OUT / url.lstrip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        print(f"  {url}")

    check_audio(lexicon)
    print(f"built {len(pages)} pages into {OUT}/")


def serve(port: int = 8000) -> None:
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(OUT))
    print(f"serving {OUT}/ at http://localhost:{port}/  (ctrl-C to stop)")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="serve docs/ after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build()
    if args.serve:
        try:
            serve(args.port)
        except KeyboardInterrupt:
            print()
