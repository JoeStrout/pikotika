#!/usr/bin/env python3
"""Pikotika lookup and conversion tool.

Reads roots.tsv, compounds.tsv and names.tsv, and converts between the four
ways of writing the language:

  1. English      a word or phrase listed in the roots or compounds tables
  2. gloss        hyphenated compounds, particles as RI / A / TE
                    e.g.  water-meal RI have A what

                  Most roots carry two glosses in roots.tsv, `gloss` and
                  `gloss2`, and learners memorize both; either one may be
                  written, so `I RI eat A food` and `me RI eat A food` are the
                  same sentence.  Reading *into* gloss always writes the
                  primary, which is the form the tables are keyed on.

  3. Latin        the phonological form, compounds written solid
                    e.g.  akukomi ri tene a ker
  4. Han          one character per root
                    e.g.  水食 ⊢ 有 ⇒ 何

Run with no arguments for an interactive prompt, or pass the query on the
command line for a single lookup.  No network and no model — just the tables.

Known bugs in this tool (issues with the *language* go in KNOWN_ISSUES.md; this
list is for defects in the code):

  - A numeral written against a following character in Han, with no space, is
    parsed as a compound rather than as a numeral plus a word.  DETAILS.md
    ("Dates") blesses exactly that spacing for years, so **2026年** is legal
    input, but it comes back as Latin `2026anyo` written solid instead of
    **pits kiru, pits tekas siks anyo**.  Not a simple fix: `2行片`
    (*2-go-paper*) really is a digit-initial compound, so the two forms are
    structurally identical and telling them apart needs a rule the language
    does not currently have.  Spelling the year with a space parses correctly.
"""

import csv
import os
import re
import readline
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The tables are TSV, not CSV, and the difference is the point: a tab never
# appears inside a cell, so nothing ever needs quoting and a comma is just a
# comma.  Turning quoting off on both sides keeps `"` a literal character --
# several mnemonics gloss their source that way, Latin *sive* "or else" -- and
# makes a writer the exact inverse of the reader, so rewriting a file to change
# one cell no longer requotes every other line.  A cell holding a tab would be
# unwritable, and csv raises rather than corrupting the file.
TSV = dict(delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None)

# A dialog line in corpus.tsv may open with a speaker label -- `Aras: si, pam.`
# -- naming who says it, so a conversation can be cast to more than one voice.
# The label is not part of the sentence: gen_audio strips it before the words
# reach the synthesizer and reads the voice off it, and gen_tables raises the
# word after it, since the label has taken the position the sentence-initial
# capital rule looks at.
#
# One word, then a colon and a space, at the very start.  That is deliberately
# narrow: a colon anywhere else is ordinary punctuation, so
# `6 ronkayoropomo kum 4 rotunpomo: 160 moni.` is left alone.
SPEAKER_LABEL = re.compile(r"^([A-Za-z][A-Za-z0-9]*): +")


def split_speaker(text):
    """(speaker, what they say) for a dialog line, (None, text) otherwise."""
    found = SPEAKER_LABEL.match(text)
    return (found.group(1), text[found.end():]) if found else (None, text)

# Particle names in gloss form are the particles' own pronunciations, upper-cased:
# ri / a / te.  This is the whole point — a name that is not the pronunciation is
# a second thing to keep in sync, which is how the old LI/E/PI naming drifted.
# roots.tsv uses these as the gloss keys too, so the mapping is the identity
# and is kept only so the two roles stay visibly distinct.
# **rite** is a fourth particle spelled out of two others
# (pikotika.org/grammar/relative/), so it costs no root and needs no character of its own.  It is not in
# roots.tsv; this table is folded into the root tables at load time so that every
# accessor -- is_particle, form_of, han_of -- treats it like any other particle.
COMPOUND_PARTICLES = {
    "RI-TE": {"form": "rite", "han": "⊢>",
              "covers": "relative clause marker, TE for clauses"},
}

PARTICLES = ("RI", "A", "TE") + tuple(COMPOUND_PARTICLES)
PARTICLE_GLOSS = {p: p for p in PARTICLES}
PARTICLE_ALIASES = {p: p for p in PARTICLES}

# The corpora write numerals as digits ("2-go-paper") as well as spelled out
# ("one night"), so a digit is accepted as an alias for its numeral root.
DIGITS = {"0": "no", "1": "one", "2": "two", "3": "three", "4": "four",
          "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
          "10": "ten", "100": "hundred", "1000": "thousand",
          "1000000": "million"}

# pikotika.org/topics/numbers/ gives the reading of any integer: positional, largest
# scale first, with the multiplier left off a leading scale word (11 is `ten one`,
# not `one ten one`; 500 is `five hundred` but 100 is just `hundred`).  A thousands
# or millions group is set off from the rest by a comma -- 12345 is read
# `ten two thousand, three hundred four ten five`.
SCALES = ((1000000, "million", True), (1000, "thousand", True),
          (100, "hundred", False), (10, "ten", False))


def counting_words(n):
    """An integer as the several words it is read as: 35 -> [three] [ten] [five]."""
    if n < 10:
        return [[DIGITS[str(n)]]]
    value, gloss, grouped = next(s for s in SCALES if n >= s[0])
    count, rest = divmod(n, value)
    words = (counting_words(count) if count > 1 else []) + [[gloss]]
    if rest:
        words += ([","] if grouped else []) + counting_words(rest)
    return words


def split_covers(text):
    """A `covers` field as its separate entries.

    Commas separate entries, and a semicolon groups them into senses -- "see,
    look, watch, appear; understand, realize, get it" -- so both end an entry.

    A separator inside a parenthetical belongs to the parenthetical, not to the
    list: "for (a length of time), until" is two entries, not three.
    """
    entries, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            entries.append("".join(current))
            current = []
        else:
            current.append(ch)
    entries.append("".join(current))
    return entries


def split_alternatives(text):
    """An `EN` field from compounds.tsv as its separate English terms.

    A gloss gets one row, and the English words that render it are separated by
    semicolons -- "theater; playhouse".  Commas are not separators here: an
    entry may need one inside a phrase.  A semicolon inside a parenthetical
    belongs to the parenthetical.
    """
    entries, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            entries.append("".join(current))
            current = []
        else:
            current.append(ch)
    entries.append("".join(current))
    return [e.strip() for e in entries if e.strip()]


def split_categories(text):
    """A `categories` field from compounds.tsv or names.tsv as its category names.

    Semicolon-separated, and a comma is not a separator: "Places, arts,
    appearance" is one category.  Roots carry a single `category` instead, so
    this is only for the two tables where a word can sit in more than one place.
    """
    return [c.strip() for c in (text or "").split(";") if c.strip()]


def cover_keys(entry):
    """The lookup keys for one `covers` entry.

    Entries may carry a parenthetical that narrows or explains the sense --
    "creature (generic head)", "visit (socially)".  Readers want to see it, but
    nobody looking a word up will type it, so index the headword on its own as
    well as the entry in full.

    A backtick marks a pointer to some other root's compound rather than a word
    of English ("hurting (pain = `sick-feel`)"), so keys holding one are left
    out -- which is what makes stripping the parenthetical worthwhile here, as
    it is the bare headword that survives.
    """
    entry = entry.strip().lower()
    keys = [entry, entry.split("(")[0].strip()]
    return [k for i, k in enumerate(keys)
            if k and "`" not in k and k not in keys[:i]]


def level_key(level):
    """Sort key for a Level cell: blank is later than any number.

    A blank means the root has not been assigned to a teaching level yet, so
    nothing can be said about when a learner meets it -- treat that as the
    hardest case rather than the easiest.
    """
    return (1, 0) if not level else (0, int(level))


class Tables:
    def __init__(self, directory=HERE):
        self.gloss2root = {}      # gloss -> {gloss, form, han, covers, ...}
        self.alias2gloss = {}     # gloss2 -> gloss (see roots.tsv `gloss2`)
        self.form2gloss = {}
        self.han2gloss = {}
        self.covers = {}          # english word -> [gloss, ...]
        self.compounds = {}       # english phrase -> gloss string
        self.compound_by_gloss = {}
        self.names = {}           # english name -> form
        self.form2name = {}       # form, case-folded -> english name
        self.name_forms = {}      # form, exactly as written -> english name
        # ...and the full semicolon list for the same form, for display.  The
        # two differ once a form answers to several names: parsing needs one
        # canonical name that round-trips back to this form, while a dictionary
        # entry wants to show all of them.
        self.name_english = {}    # form, exactly as written -> "Aaron; Ellen; ..."

        self.name_kind = {}       # form -> "name" or "loan" (names.tsv `kind`)
        # The loan register, reachable from gloss notation.  A loan is written
        # lowercase, so it can never pass name_wins' capital test; this is the
        # index split_gloss_word consults instead.  Keyed by every lowercase
        # token that names the loan -- its English and its own form -- and
        # valued with the one English key self.names renders back through.
        self.loans = {}           # lowercase token -> english key in self.names
        # ...and the same register keyed by form alone.  `loans` above answers
        # to a loan's English too, which is right for gloss notation and wrong
        # for parsing Latin: **Meter** must not resolve just because 'meter'
        # names the loan whose form is **mitar**.
        self.loan_forms = {}      # lowercase form -> english key in self.names
        self.compound_cats = {}   # compound gloss -> [category, ...]
        self.name_cats = {}       # name/loan form -> [category, ...]
        self.name_origin = {}     # form -> "" (curated) or "cmudict" (poured)
        self.category_order = []  # roots.tsv `category` values, in table order
        self.compound_roots = {}  # gloss -> [root gloss, ...]
        self.corpus = []          # corpus.tsv rows, in file order
        self._load(directory)

    def _load(self, d):
        with open(os.path.join(d, "roots.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, **TSV):
                if not r["form"]:
                    continue
                self.gloss2root[r["gloss"]] = r
                self.form2gloss[r["form"]] = r["gloss"]
                # The order is editorial -- body and life first, grammar words
                # last -- so it is kept as the table gives it, not sorted.  This
                # is the whole category vocabulary: compounds.tsv and names.tsv
                # pick from it and may not invent one.
                cat = (r.get("category") or "").strip()
                if cat and cat not in self.category_order:
                    self.category_order.append(cat)
                if r["han"]:
                    self.han2gloss[r["han"]] = r["gloss"]
                alias = (r.get("gloss2") or "").strip()
                if alias:
                    # a space-separated gloss2 ("one who") cannot be a token in
                    # gloss notation, where a space ends the word and a hyphen
                    # joins roots into a compound.  Underscore is free in both
                    # roles, so it is what holds such a gloss together: `one_who`.
                    self.alias2gloss["_".join(alias.split())] = r["gloss"]
                for entry in split_covers(r["covers"]):
                    for key in cover_keys(entry):
                        self.covers.setdefault(key, []).append(r["gloss"])

        for gloss, spec in COMPOUND_PARTICLES.items():
            row = dict(spec, gloss=gloss)
            # a compound particle is learned once both its parts are
            row["Level"] = max((self.level_of(p) for p in gloss.split("-")),
                               key=level_key, default="")
            self.gloss2root[gloss] = row
            self.form2gloss[row["form"]] = gloss
            self.han2gloss[row["han"]] = gloss
        # han2gloss keys are single characters except for these; parse_han has to
        # try the long ones before falling back to character-at-a-time
        self.multi_han = sorted((h for h in self.han2gloss if len(h) > 1),
                                key=len, reverse=True)

        with open(os.path.join(d, "compounds.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, **TSV):
                # one row per gloss; its English equivalents are separated by
                # semicolons, e.g. "theater; playhouse"
                for english in split_alternatives(r["EN"]):
                    self.compounds[english.lower()] = r["gloss"]
                    # entries are labelled "beer (any grain alcohol)"; index the
                    # headword on its own too, so plain "beer" finds it
                    head = english.split("(")[0].strip().lower()
                    if head:
                        self.compounds.setdefault(head, r["gloss"])
                    self.compound_by_gloss.setdefault(
                        r["gloss"], []).append(english)
                roots = self.gloss_roots(r["gloss"])
                if roots:
                    self.compound_roots[r["gloss"]] = roots
                self.compound_cats[r["gloss"]] = split_categories(
                    r.get("categories"))

        corpus_path = os.path.join(d, "corpus.tsv")
        if os.path.exists(corpus_path):
            with open(corpus_path, encoding="utf-8") as fh:
                self.corpus = list(csv.DictReader(fh, **TSV))

        names_path = os.path.join(d, "names.tsv")
        if os.path.exists(names_path):
            with open(names_path, encoding="utf-8") as fh:
                for r in csv.DictReader(fh, **TSV):
                    # One form can answer to several English names -- Pikotika
                    # draws fewer distinctions, so Aaron, Aron, Ellen and Helen
                    # are all Eran -- and they share the EN cell, semicolon
                    # separated, exactly as in compounds.tsv.
                    for english in r["EN"].split(";"):
                        english = english.strip().lower()
                        if english:
                            self.names[english] = r["form"]
                    # Two rows can share a form -- a poured row for Dom, Thom
                    # and Tome spells the same Tom a curated row already does.
                    # The english -> form direction above takes them all; every
                    # form-keyed map below keeps the FIRST row, which is the
                    # curated one, since gen_names.py writes those first.
                    if r["form"] in self.name_forms:
                        continue
                    # keyed lowercase: a proper name's form is capitalized in
                    # names.tsv (Erana) but most lookup sites fold case first.
                    # Only the first English name goes here: this is the
                    # direction gloss notation is rendered from, and it has to
                    # come back through self.names to the same form, so it must
                    # be one name rather than the whole semicolon list.
                    self.form2name[r["form"].lower()] = r["EN"].split(";")[0].strip()
                    self.name_forms[r["form"]] = r["EN"].split(";")[0].strip()
                    self.name_english[r["form"]] = r["EN"].strip()
                    # proper nouns and the sanctioned loan register share the
                    # table; Vocab filters them apart, so keep which is which
                    self.name_kind[r["form"]] = (r.get("kind") or "name").strip()
                    self.name_cats[r["form"]] = split_categories(
                        r.get("categories"))
                    # `origin` says where the row came from: blank for a
                    # curated adaptation, "cmudict" for one poured in by
                    # gen_names.py.  The site browses the first and only
                    # searches the second.
                    self.name_origin[r["form"]] = (r.get("origin") or "").strip()
                    if self.name_kind[r["form"]] == "loan":
                        english = self.name_forms[r["form"]]
                        self.loans[r["form"].lower()] = english
                        self.loan_forms[r["form"].lower()] = english
                        for alt in r["EN"].split(";"):
                            alt = alt.strip().lower()
                            if alt:
                                self.loans[alt] = english

    # -- root-level accessors -------------------------------------------------

    def is_particle(self, gloss):
        return gloss in PARTICLE_GLOSS

    def root_gloss(self, key):
        """The primary gloss `key` names, whether it is the primary or the gloss2.

        Most roots carry two glosses, and learners memorize both, so either may
        be written -- `I RI eat A food` and `me RI eat A food` are the same
        sentence.  Nothing downstream sees the alias: this resolves to the
        primary gloss, which is what indexes the root and what render_gloss
        writes back out.  A primary gloss always wins over another root's
        gloss2, though as of this writing no gloss2 collides with anything.
        """
        if key in self.gloss2root and not self.is_particle(key):
            return key
        return self.alias2gloss.get(key)

    def gloss_roots(self, word):
        """One gloss word as its list of primary root glosses, or None.

        None for anything that is not roots all the way through -- a name, a
        numeral, a word with a typo -- since those are what the index of roots
        below has nothing to say about.
        """
        roots = []
        for piece in word.strip("".join(PUNCT)).split("-"):
            gloss = self.root_gloss(piece) or (
                piece if piece in PARTICLE_GLOSS else None)
            if gloss is None:
                return None
            roots.append(gloss)
        return roots or None

    def form_of(self, gloss):
        return self.gloss2root[gloss]["form"]

    def han_of(self, gloss):
        return self.gloss2root[gloss]["han"]

    def level_of(self, gloss):
        """The root's teaching level as written in roots.tsv; "" if unleveled."""
        return (self.gloss2root.get(gloss) or {}).get("Level", "") or ""

    def name_of(self, token):
        """The English name a token spells, in either notation; None if neither.

        Accepts the English spelling ("Elena") and the Pikotika form ("Erena"),
        since gloss notation is written with English keywords but readers paste
        Latin forms into it all the time.
        """
        english = self.names.get(token.lower())
        if english is not None:
            return self.form2name[english.lower()]
        return self.form2name.get(token.lower())

    def loan_of(self, token):
        """The English key for a sanctioned loan, or None.

        Accepts the English ("meter") and the Pikotika form ("mitar"), as
        name_of does.  Case is what separates the two registers: **mitar** the
        metric unit is an ordinary lowercase word, Mitar the adaptation of
        Michal is a capitalized name, and they are otherwise homographs.  The
        caller is what enforces that -- see split_gloss_word.
        """
        return self.loans.get(token.lower())


# ---------------------------------------------------------------------------
# A parsed query is a list of words; each word is a list of glosses.  A word of
# one particle gloss is a particle; anything else is a compound (or single root).
# Names ride along as ("NAME", english) so they survive to output unsegmented.
# ---------------------------------------------------------------------------

# the corpora punctuate with free-standing , . : ? — these pass through every
# notation unchanged, so a corpus expression can be pasted in as-is
#
# A dash or an ellipsis is punctuation too, and prose written for the site uses
# both -- an em dash sets off an aside, and the pages are typed with the real
# characters, not with "--".  They are listed apart from the rest only because
# they space differently (see join_words) and because a dash, unlike a comma,
# is written free-standing as often as attached.
DASH = set("—–")                        # em dash, en dash
PUNCT = set(",.:;?!…" "、。：；？！") | DASH

# Sentence-final punctuation.  Every word is capitalized after one of these, so
# capitalization stops distinguishing a name from a root there -- see name_wins.
SENTENCE_END = set(".?!" "。？！")


def ends_sentence(token):
    return any(c in SENTENCE_END for c in token)

# ...but ordinary writing attaches them ("a kanis, ker?"), so punctuation is peeled
# off the ends of each whitespace-delimited word.  Only off the ends: a decimal
# point belongs to its number (**1.25**), not to the sentence.  A dash is the
# exception: it is cut out wherever it falls, since "opus—tistempo" is two words
# with a dash between them and not a word with a dash in the middle of it.
DASH_SPLIT = re.compile("([" + "".join(DASH) + "])")


def tokenize(text):
    out = []
    for word in text.split():
        for chunk in DASH_SPLIT.split(word):
            lead, tail = 0, len(chunk)
            while lead < tail and chunk[lead] in PUNCT:
                lead += 1
            while tail > lead and chunk[tail - 1] in PUNCT:
                tail -= 1
            out += [piece for piece in
                    (chunk[:lead], chunk[lead:tail], chunk[tail:]) if piece]
    return out


def join_words(parts):
    """Join rendered words with spaces, but hang punctuation on the word before.

    A dash is the exception: it stands between two words with a space on each
    side, so it takes one in front of it like an ordinary word."""
    out = ""
    for part in parts:
        if out and (not is_punct_text(part) or is_dash_text(part)):
            out += " "
        out += part
    return out


def is_punct_text(s):
    return bool(s) and all(c in PUNCT for c in s)


def is_dash_text(s):
    return bool(s) and all(c in DASH for c in s)


# A decimal is written with digits but spoken as several words: the `.` is `part`,
# and the digits after it are read one at a time -- **1.25** is `one part two five`
# (pikotika.org/topics/numbers/).  So a decimal token parses into that many words and renders as that
# many words; only the written digit form is one token.
DECIMAL_POINT = "part"


def decimal_words(word):
    """'1.25' -> [[one], [part], [two], [five]].  None if not a decimal numeral."""
    whole, point, frac = word.partition(".")
    if not point or not whole.isdigit() or not frac.isdigit():
        return None
    return counting_words(int(whole)) + [[DECIMAL_POINT]] + \
        [[DIGITS[d]] for d in frac]


# A clock time is written the same way, with `hour` standing in for the colon:
# **9:30** is `nine hour three ten`, and :00 minutes go unsaid -- **9:00** is just
# **noks ora** (pikotika.org/topics/time/).
CLOCK_MARK = "hour"


def clock_words(word):
    """'9:30' -> [[nine], [hour], [three], [ten]].  None if not a clock time."""
    hour, mark, minute = word.partition(":")
    if not mark or not hour.isdigit() or not minute.isdigit():
        return None
    if not 1 <= len(hour) <= 2 or len(minute) != 2 or int(minute) > 59:
        return None
    return counting_words(int(hour)) + [[CLOCK_MARK]] + \
        (counting_words(int(minute)) if int(minute) else [])


# A fraction is written with a slash, as in English, and read with `in` between
# the two numbers: **3/4** is `three in four`.  `in` is the ordinary preposition
# doing its ordinary job, so there is no special word here.
FRACTION_MARK = "in"

# A percentage is a fraction whose denominator is already agreed on, and 'in a
# hundred' is a standing compound, so **50%** is `five ten in-hundred` -- as is
# **50/100**, written the long way.
PERCENT_WORD = ["in", "hundred"]
PERCENT_DENOMINATOR = 100


def fraction_words(word):
    """'3/4' -> [[three], [in], [four]].  None if not a written fraction."""
    top, slash, bottom = word.partition("/")
    if not slash or not top.isdigit() or not bottom.isdigit():
        return None
    if int(bottom) == PERCENT_DENOMINATOR:
        return counting_words(int(top)) + [list(PERCENT_WORD)]
    return counting_words(int(top)) + [[FRACTION_MARK]] + \
        counting_words(int(bottom))


def percent_words(word):
    """'50%' -> [[five], [ten], [in, hundred]].  None if not a percentage."""
    if not word.endswith("%"):
        return None
    body = word[:-1]
    amount = counting_words(int(body)) if body.isdigit() else decimal_words(body)
    return amount + [list(PERCENT_WORD)] if amount else None


def numeral_words(word):
    """The several words a written numeral is read as, or None if it is not one.

    Free-standing numerals only.  A digit bound inside a compound stays a digit
    (`24-part-one`): a compound is one word, and a reading is several.
    """
    if word.isdigit():
        return counting_words(int(word))
    return (decimal_words(word) or clock_words(word)
            or fraction_words(word) or percent_words(word))


# A numeral is written with digits but read as several words, and the two must not
# be confused: 1.25 is *read* `one part two five` but stays **1.25** on the page, in
# Latin and Han alike (pikotika.org/topics/numbers/).  So a written numeral is kept as
# one word carrying both -- the digits it was written with, and the words it is read
# as -- and each notation takes the half it needs.  Deriving the digits back from the
# reading is what loses `.` and `:`, and turns 12345 into `十 2 千, 3 百 4 十 5`.
def numeral_word(text, reading):
    return ("NUMERAL", text, reading)


def is_numeral(w):
    return isinstance(w, tuple) and len(w) == 3 and w[0] == "NUMERAL"


def expand_numerals(words):
    """The word list with each written numeral replaced by the words it reads as."""
    return [x for w in words for x in (w[2] if is_numeral(w) else [w])]


def name_token(english):
    return ("NAME", english)


def is_name(tok):
    return isinstance(tok, tuple) and tok[0] == "NAME"


def is_punct(word):
    return isinstance(word, str)


def num_token(text):
    return ("NUM", text)


def is_num(tok):
    return isinstance(tok, tuple) and tok[0] == "NUM"


def literal(tok):
    """the text a NAME or NUM token contributes, in any notation"""
    return tok[1]


# `one` and `no` are the two numerals that lead a double life -- `one` also carries
# single / same / the very, `no` also carries none / absent / without -- so their
# character depends on the use.  §8's bound/free test separates them: free-standing
# `one` is counting (118 of 135 uses: "one small-time", "one new-man"), bound `one`
# is not ("one-way", "one-price", "self-one-time").  `no` gets no such rule -- its
# free-standing uses are "none", not zero ("no bad-thing", "no other-person"),
# so it stays 无 throughout.  two..nine never lead a double life and stay digits.
DIGIT_WHEN_FREE = {"one": "1"}
FREE_DIGIT_TO_GLOSS = {v: k for k, v in DIGIT_WHEN_FREE.items()}


# Roots ending in `-ts`, `-ns`, `-ks` (the digits 2-9, plus `from out back middle
# measure but`) carry a cluster that is licensed word-finally, and before a vowel,
# where it straddles the syllable boundary: `tets`+`omo` -> **tetsomo**.  Before a
# consonant it needs a linking `e` that belongs to neither root: `tets`+`kurva` ->
# **tetsekurva**.  The `e` is unambiguous -- no root ends in a plain stop, so the
# cluster can never be re-split across the join.
CLUSTERS = ("ts", "ns", "ks")
VOWELS = "aeiou"
LINK = "e"


def links(prev, nxt):
    """Does a linking `e` go between these two adjacent root forms?"""
    return (prev.endswith(CLUSTERS) and prev[-1].isalpha()
            and nxt[:1].isalpha() and nxt[0] not in VOWELS)


def join_latin(pieces):
    """Concatenate root forms into one solid word, inserting linking `e`."""
    out = ""
    for piece in pieces:
        if out and links(out, piece):
            out += LINK
        out += piece
    return out


def blame(fail, words, token, why=None):
    """Record the token a parse died on, for the error message.

    Every notation is tried on every query, so most of the failures are
    uninteresting -- Latin has nothing to say about a Han sentence.  Keeping
    the attempt that got the furthest picks out the notation the user was
    actually writing in, and so the token they actually got wrong.  `why`
    overrides the default "no such word" explanation.
    """
    if fail is not None and fail.get("words", -1) < len(words):
        fail.clear()
        fail.update(words=len(words), token=token, why=why)


def parse_gloss(text, t, fail=None):
    """'water-meal RI have A what' -> [[water, meal], [RI], [have], [A], [what]]"""
    words = []
    start = True
    for word in tokenize(text):
        if is_punct_text(word):
            words.append(word)
            if ends_sentence(word):
                start = True
            continue
        numeral = numeral_words(word)
        if numeral is not None:
            words.append(numeral_word(word, numeral))
            start = False
            continue
        upper = word.upper()
        if upper in PARTICLE_ALIASES:
            words.append([PARTICLE_ALIASES[upper]])
            start = False
            continue
        parts = split_gloss_word(word, t, words, start, fail)
        if parts is None:
            return None
        words.append(parts)
        start = False
    return words or None


def split_gloss_word(word, t, words, start, fail):
    """One hyphenated gloss word as its list of glosses, or None."""
    parts = []
    pieces = word.split("-")
    for n, piece in enumerate(pieces):
        if piece.isdigit():
            if piece in DIGITS:
                parts.append(DIGITS[piece])
            else:
                parts.append(num_token(piece))
            continue
        # either of the root's two glosses names it; see Tables.root_gloss
        gloss = t.root_gloss(piece)
        if gloss is not None:
            parts.append(gloss)
            continue
        # A loan is an ordinary lowercase word (names.tsv `kind` = loan), so
        # it can never pass name_wins' capital test, and **kirumitar** had no
        # way to be written in gloss notation at all.  Take it here, ahead of
        # the name branch, so lowercase **mitar** reaches the metric unit
        # rather than Mitar, the adaptation of Michal, which it collides with.
        #
        # This once fired only inside a hyphenated word, on the grounds that a
        # loan standing alone could stay Latin to the converter.  It reads the
        # same either way -- both notations resolve the token to the same loan
        # -- and the restriction made a sentence with a *standing* loan in it
        # unwritable in gloss notation at all, which is the notation the corpus
        # is authored in ("I RI like A tanko music-go").  So the register, not
        # the hyphen, is what the branch turns on now.
        #
        # A loan opening a sentence is capitalized like any other word and so
        # falls through to the name; write it mid-sentence, or spell the name
        # out as **omo Mitar**, exactly as /topics/names/ prescribes.
        loan = t.loan_of(piece)
        if loan is not None and not piece[:1].isupper():
            parts.append(name_token(loan))
            continue
        # "Joe" by its English spelling, "Yo" by its Pikotika form
        name = t.name_of(piece)
        if name is not None and name_wins(piece, start and not n, t):
            parts.append(name_token(name))
            continue
        blame(fail, words, piece)   # the piece, not the whole compound
        return None
    return parts


def segment(form, t, raw=None):
    """Split a solid Latin word into root forms.  Returns one segmentation.

    `raw` is the word as written, same length as `form`; names are matched
    against it so that their capitalization still counts inside a compound.
    """
    raw = form if raw is None else raw
    n = len(form)
    best = [None] * (n + 1)
    best[0] = []

    def prior(j, piece):
        """The segmentation `piece` continues, over a linking `e` if there is one."""
        if best[j] is not None:
            return best[j]
        # form[j-1] is an `e` belonging to neither root: `tets` + e + `kurva`
        if j and form[j - 1] == LINK and best[j - 1]:
            prev = best[j - 1][-1]
            if not isinstance(prev, tuple) and links(t.form_of(prev), piece):
                return best[j - 1]
        return None

    for i in range(1, n + 1):
        for j in range(i):
            piece = form[j:i]
            head = prior(j, piece)
            if head is None:
                continue
            gloss = t.form2gloss.get(piece)
            if gloss and not t.is_particle(gloss):
                best[i] = head + [gloss]
                break
            # a name inside a compound is only recoverable because the reader
            # knows the name -- so names are part of the segmentation lexicon
            piece_name = name_at(raw[j:i], t)
            if piece_name is not None:
                best[i] = head + [name_token(piece_name)]
                break
            # a multi-digit number keeps its digits inline (see DIGITS)
            if piece.isdigit() and piece not in DIGITS and \
                    (i == len(form) or not form[i].isdigit()):
                best[i] = head + [num_token(piece)]
                break
    return best[n]


def name_at(token, t):
    """The names.tsv entry a Latin token stands for, or None.

    A proper name is capitalized in every notation, so it has to match exactly
    -- that is the whole of what separates Mira the name from **mira**.  A loan
    is an ordinary lowercase word, so it takes a capital at the start of a
    sentence like any other word, and folding the case down is what lets
    **Wivi ri...** parse.  Only down, never up: a lowercase token still cannot
    stand for a capitalized proper name.
    """
    if token in t.name_forms:
        return t.name_forms[token]
    low = token.lower()
    return t.loan_forms.get(low) if low != token else None


def name_wins(token, start, t):
    """Does a capitalized token stand for a name rather than for roots?

    Names are capitalized in every notation (pikotika.org/grammar/writing/),
    so case alone separates Mira the name from **mira** 'surprise'.  The one
    place it cannot is the start of a sentence, where every word is capitalized:
    there the root wins, and the name is only the fallback for a token no roots
    can spell.  Write **omo Mira** to force the name -- which is exactly the
    disambiguation pikotika.org/topics/names/ prescribes for a name that
    collides with a word.
    """
    if not token[:1].isupper():
        return False
    return not start or segment(token.lower(), t) is None


def parse_latin(text, t, fail=None):
    words = []
    start = True
    for word in tokenize(text):
        if is_punct_text(word):
            words.append(word)
            if ends_sentence(word):
                start = True
            continue
        numeral = numeral_words(word)
        if numeral is not None:
            words.append(numeral_word(word, numeral))
            start = False
            continue
        low = word.lower()
        gloss = t.form2gloss.get(low)
        if gloss and t.is_particle(gloss):
            words.append([gloss])
            start = False
            continue
        # an outright win takes the name; otherwise the roots get first refusal
        # and the name catches what they cannot spell
        name = name_at(word, t)
        parts = None
        if name is None or start:
            parts = segment(low, t, word)
        if parts is None and name is not None:
            parts = [name_token(name)]
        if parts is None:
            blame(fail, words, word)
            return None
        words.append(parts)
        start = False
    return words or None


def parse_han(text, t, fail=None):
    words = []
    for word in tokenize(text):
        if is_punct_text(word):
            words.append(word)
            continue
        numeral = numeral_words(word)
        if numeral is not None:
            words.append(numeral_word(word, numeral))
            continue
        # no digit shortcut here: the characters for two..nine *are* the digits,
        # so the per-character lookup below is what resolves them
        parts = []
        i = 0
        while i < len(word):
            # a run of two or more digits is a number with no root of its own
            # (20, 302); a single digit is a character -- two..nine are stored
            # as digits, and render_han writes free-standing `one` as 1
            j = i
            while j < len(word) and word[j].isdigit():
                j += 1
            if j - i > 1:
                parts.append(num_token(word[i:j]))
                i = j
                continue
            # a run of Latin letters inside Han text is a name (names have no
            # character of their own -- see names.tsv)
            j = i
            while j < len(word) and word[j].isascii() and word[j].isalpha():
                j += 1
            if j > i:
                # no roots are written in Latin here, so nothing competes with
                # the name and case can stay a courtesy rather than a rule
                name = t.name_forms.get(word[i:j]) or \
                    t.form2name.get(word[i:j].lower())
                if name is None:
                    blame(fail, words, word[i:j])
                    return None
                parts.append(name_token(name))
                i = j
                continue
            # a particle written as several characters (⊢> for RI-TE)
            multi = next((h for h in t.multi_han if word.startswith(h, i)), None)
            if multi:
                parts.append(t.han2gloss[multi])
                i += len(multi)
                continue
            ch = word[i]
            gloss = t.han2gloss.get(ch) or FREE_DIGIT_TO_GLOSS.get(ch)
            if gloss is None:
                blame(fail, words, ch)
                return None
            parts.append(gloss)
            i += 1
        # a particle character stands alone as its own word
        if len(parts) == 1 and not isinstance(parts[0], tuple) \
                and t.is_particle(parts[0]):
            words.append(parts)
        else:
            stuck = next((g for g in parts
                          if not isinstance(g, tuple) and t.is_particle(g)), None)
            if stuck:
                blame(fail, words, t.han_of(stuck),
                      "a particle has to stand as its own word")
                return None
            words.append(parts)
    return words or None


def parse_english(text, t, fail=None):
    key = text.strip().lower()
    if key in t.compounds:
        return parse_gloss(t.compounds[key], t)
    gloss = t.root_gloss(key) or t.root_gloss("_".join(key.split()))
    if gloss is not None:
        return [[gloss]]
    if key in t.covers:
        return [[t.covers[key][0]]]
    if key in t.names:
        return [[name_token(t.form2name[t.names[key].lower()])]]
    return None


def looks_like_han(text, t):
    chars = [c for c in text if not c.isspace()]
    # digits and names are written in Latin inside Han text, so an all-ASCII
    # string satisfies the test below while being no such thing -- it takes one
    # actual character to make the notation Han
    if not any(not c.isascii() for c in chars):
        return False
    return bool(chars) and all(c in t.han2gloss or c in PUNCT
                               or c in FREE_DIGIT_TO_GLOSS
                               or c.isdigit() or c.isascii() and c.isalpha()
                               for c in chars)


def parse(text, t, fail=None):
    """Try each notation in turn; returns (words, source_notation).

    `fail` is an optional dict; on failure it comes back holding the token
    that could not be resolved (see blame).
    """
    if looks_like_han(text, t):
        words = parse_han(text, t, fail)
        if words:
            return words, "Han"
    else:
        # one stray character keeps the whole query out of parse_han, and the
        # other notations can only blame the word it sits in -- so name it here
        stray = next((c for c in text if not c.isascii() and c not in PUNCT
                      and c not in t.han2gloss
                      and c not in FREE_DIGIT_TO_GLOSS), None)
        if stray:
            blame(fail, [], stray)
    for fn, label in ((parse_gloss, "gloss"), (parse_latin, "Latin"),
                      (parse_english, "English")):
        words = fn(text, t, fail)
        if words:
            return words, label
    return None, None


# -- rendering ---------------------------------------------------------------

def render_gloss(words, t):
    out = []
    for w in words:
        if is_numeral(w):
            out.append(render_gloss(w[2], t))
        elif is_punct(w):
            out.append(w)
        elif len(w) == 1 and not is_name(w[0]) and t.is_particle(w[0]):
            out.append(PARTICLE_GLOSS[w[0]])
        else:
            out.append("-".join(literal(g) if isinstance(g, tuple) else g
                                for g in w))
    return join_words(out)


def render_latin(words, t):
    out = []
    for w in words:
        if is_numeral(w):
            out.append(w[1])          # digits stay digits, `.` and `:` included
            continue
        if is_punct(w):
            out.append(w)
            continue
        out.append(join_latin([
            t.names[g[1].lower()] if is_name(g) else literal(g) if is_num(g)
            else t.form_of(g) for g in w]))
    return join_words(out)


def render_han(words, t):
    out = []
    for w in words:
        if is_numeral(w):
            out.append(w[1])          # digits stay digits, `.` and `:` included
            continue
        if is_punct(w):
            out.append(w)
            continue
        if len(w) == 1 and not isinstance(w[0], tuple) and w[0] in DIGIT_WHEN_FREE:
            out.append(DIGIT_WHEN_FREE[w[0]])
            continue
        # names have no character; they stay in Latin inside Han text
        out.append("".join(
            t.names[g[1].lower()] if is_name(g) else literal(g) if is_num(g)
            else t.han_of(g) for g in w))
    return join_words(out)


def root_glosses(root):
    """"gloss; gloss2" for a roots.tsv row -- a learner memorizes both.

    One keyword only ever points at part of a root's range, so anything that
    names a root for a learner shows the pair.  A few rows carry only the
    primary (the particles, and roots such as `blue` with nothing to add).
    """
    return "; ".join(g for g in (root["gloss"],
                                 (root.get("gloss2") or "").strip()) if g)


def root_covers(root):
    """A root's full sense range for display: gloss, gloss2, then `covers`.

    The column holds only the senses the two glosses do not already name -- for
    eleven roots that leaves it blank -- so anything showing a reader what a
    root spans joins all three rather than printing the column alone.  Sense
    groups inside `covers` keep their semicolons.
    """
    named = [root["gloss"], (root.get("gloss2") or "").strip()]
    rest = (root.get("covers") or "").strip()
    return ", ".join([g for g in named if g] + ([rest] if rest else []))


def english_match(words, t):
    """Exact English equivalents, when the whole query is one root or compound."""
    words = [w for w in expand_numerals(words) if not is_punct(w)]
    if len(words) != 1:
        return []
    word = words[0]
    # A bare name or numeral has no gloss entry, only its own English.  A
    # compound that merely *contains* one still does, though -- **kirumitar**
    # is thousand-meter -- so only an all-token word takes this path.
    if all(isinstance(g, tuple) for g in word):
        return [literal(g) for g in word if is_name(g)]
    gloss = render_gloss([word], t)
    hits = list(t.compound_by_gloss.get(gloss, []))
    if len(word) == 1 and gloss in t.gloss2root:
        root = t.gloss2root[gloss]
        hits.append("%s  (root: %s)" % (root_glosses(root), root_covers(root)))
    return hits


def max_level(words, t):
    """"<level> (gloss, ...)" for the hardest roots used, or None if no roots.

    A written numeral is read out first, so "2" costs the root `two`.
    """
    glosses = []
    for word in expand_numerals(words):
        if is_punct(word):
            continue
        for gloss in word:
            if (not isinstance(gloss, tuple) and gloss in t.gloss2root
                    and gloss not in glosses):
                glosses.append(gloss)
    if not glosses:
        return None
    top = max((t.level_of(g) for g in glosses), key=level_key)
    at_top = [g for g in glosses if t.level_of(g) == top]
    return "%s (%s)" % (top, ", ".join(at_top))


# A common root is in dozens of compounds and hundreds of sentences, so both
# lists are capped and the rest is counted.  The point of these sections is to
# show the word in use, and a handful of uses does that as well as all of them.
COMPOUND_LIMIT = 24
SENTENCE_LIMIT = 6


def query_roots(words, t):
    """The roots a one-word query is made of, or None if it is not one word.

    Anything longer is a phrase, and looking for a phrase inside the lexicon
    finds nothing useful; names and numerals index nothing.
    """
    words = [w for w in expand_numerals(words) if not is_punct(w)]
    if len(words) != 1 or any(isinstance(g, tuple) for g in words[0]):
        return None
    return list(words[0])


def contains_run(haystack, needle):
    """Does `needle` appear in `haystack` as a contiguous run of elements?

    Roots, not characters: **moni** 'money' does not contain **wun** 'one' just
    because *money* spells *one* -- the glosses are what the query names.
    """
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def compound_hits(roots, t):
    """(latin, english) for every compound built around `roots`, minus itself."""
    hits = []
    for gloss, parts in t.compound_roots.items():
        if parts != roots and contains_run(parts, roots):
            hits.append((join_latin([t.form_of(g) for g in parts]),
                         "; ".join(t.compound_by_gloss.get(gloss, []))))
    return sorted(hits)


def sentence_hits(roots, t):
    """(latin, english) for every corpus sentence using `roots`, in file order."""
    hits = []
    for row in t.corpus:
        for word in row["gloss"].split():
            parts = t.gloss_roots(word)
            if parts and contains_run(parts, roots):
                hits.append((row["latin"], row["EN"]))
                break
    return hits


def more(hits, limit):
    """The note that stands in for whatever the limit cut off."""
    return [] if len(hits) <= limit else \
        ["    ... and %d more" % (len(hits) - limit)]


def usage_lines(words, t):
    """The `Compounds:` and `Sentences:` sections, for a query that is one word."""
    roots = query_roots(words, t)
    if roots is None:
        return []
    lines = []
    compounds = compound_hits(roots, t)
    if compounds:
        lines.append("  Compounds:")
        lines += ["    %s — %s" % hit for hit in compounds[:COMPOUND_LIMIT]]
        lines += more(compounds, COMPOUND_LIMIT)
    sentences = sentence_hits(roots, t)
    if sentences:
        lines.append("  Sentences:")
        for latin, english in sentences[:SENTENCE_LIMIT]:
            lines += ["    " + latin, "      " + english]
        lines += more(sentences, SENTENCE_LIMIT)
    return lines


def lookup(text, t):
    fail = {}
    words, source = parse(text, t, fail)
    if not words:
        if "token" not in fail:
            return ["  no match — not in roots.tsv, compounds.tsv or names.tsv"]
        return ['  no match — "%s" %s' % (
            fail["token"],
            fail["why"] or "is not in roots.tsv, compounds.tsv or names.tsv")]
    lines = ["  gloss: " + render_gloss(words, t),
             "  Latin: " + render_latin(words, t),
             "  Han:   " + render_han(words, t)]
    top = max_level(words, t)
    if top:
        lines.append("  Max. root level: " + top)
    hits = english_match(words, t)
    if hits:
        lines.append("  EN:    " + "; ".join(hits))
    return lines + usage_lines(words, t)


def main(argv):
    t = Tables()
    if len(argv) > 1:
        print("\n".join(lookup(" ".join(argv[1:]), t)))
        return 0
    print("Pikotika — %d roots, %d compounds, %d names."
          % (len(t.gloss2root), len(t.compounds), len(t.names)))
    print("Enter English, gloss (RI / A / TE), Latin, or Han.  Ctrl-D to quit.")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in ("quit", "exit"):
            return 0
        print("\n".join(lookup(text, t)))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
