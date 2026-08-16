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

# Particle names in gloss form are the particles' own pronunciations, upper-cased:
# ri / a / te.  This is the whole point — a name that is not the pronunciation is
# a second thing to keep in sync, which is how the old LI/E/PI naming drifted.
# roots.tsv uses these as the gloss keys too, so the mapping is the identity
# and is kept only so the two roles stay visibly distinct.
# **rite** is a fourth particle spelled out of two others (DETAILS.md, "Subordinate
# Clauses"), so it costs no root and needs no character of its own.  It is not in
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

# DETAILS.md "## Numbers" gives the reading of any integer: positional, largest
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
        self._load(directory)

    def _load(self, d):
        with open(os.path.join(d, "roots.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, **TSV):
                if not r["form"]:
                    continue
                self.gloss2root[r["gloss"]] = r
                self.form2gloss[r["form"]] = r["gloss"]
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

        names_path = os.path.join(d, "names.tsv")
        if os.path.exists(names_path):
            with open(names_path, encoding="utf-8") as fh:
                for r in csv.DictReader(fh, **TSV):
                    self.names[r["EN"].strip().lower()] = r["form"]
                    # keyed lowercase: a proper name's form is capitalized in
                    # names.tsv (Erena) but most lookup sites fold case first
                    self.form2name[r["form"].lower()] = r["EN"]
                    self.name_forms[r["form"]] = r["EN"]

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


# ---------------------------------------------------------------------------
# A parsed query is a list of words; each word is a list of glosses.  A word of
# one particle gloss is a particle; anything else is a compound (or single root).
# Names ride along as ("NAME", english) so they survive to output unsegmented.
# ---------------------------------------------------------------------------

# the corpora punctuate with free-standing , . : ? — these pass through every
# notation unchanged, so a corpus expression can be pasted in as-is
PUNCT = set(",.:;?!" "、。：；？！")

# Sentence-final punctuation.  Every word is capitalized after one of these, so
# capitalization stops distinguishing a name from a root there -- see name_wins.
SENTENCE_END = set(".?!" "。？！")


def ends_sentence(token):
    return any(c in SENTENCE_END for c in token)

# ...but ordinary writing attaches them ("a kanis, ker?"), so punctuation is peeled
# off the ends of each whitespace-delimited word.  Only off the ends: a decimal
# point belongs to its number (**1.25**), not to the sentence.
def tokenize(text):
    out = []
    for word in text.split():
        lead, tail = 0, len(word)
        while lead < tail and word[lead] in PUNCT:
            lead += 1
        while tail > lead and word[tail - 1] in PUNCT:
            tail -= 1
        out += [chunk for chunk in (word[:lead], word[lead:tail], word[tail:])
                if chunk]
    return out


def join_words(parts):
    """Join rendered words with spaces, but hang punctuation on the word before."""
    out = ""
    for part in parts:
        if out and not is_punct_text(part):
            out += " "
        out += part
    return out


def is_punct_text(s):
    return bool(s) and all(c in PUNCT for c in s)


# A decimal is written with digits but spoken as several words: the `.` is `part`,
# and the digits after it are read one at a time -- **1.25** is `one part two five`
# (DETAILS.md).  So a decimal token parses into that many words and renders as that
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
# **noks ora** (DETAILS.md, "Telling Time").
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


def numeral_words(word):
    """The several words a written numeral is read as, or None if it is not one.

    Free-standing numerals only.  A digit bound inside a compound stays a digit
    (`24-part-one`): a compound is one word, and a reading is several.
    """
    if word.isdigit():
        return counting_words(int(word))
    return decimal_words(word) or clock_words(word)


# A numeral is written with digits but read as several words, and the two must not
# be confused: 1.25 is *read* `one part two five` but stays **1.25** on the page, in
# Latin and Han alike (DETAILS.md, "## Numbers").  So a written numeral is kept as
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
# free-standing uses are "none", not zero ("no not-good-thing", "no other-person"),
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
    for n, piece in enumerate(word.split("-")):
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
            if raw[j:i] in t.name_forms:
                best[i] = head + [name_token(t.name_forms[raw[j:i]])]
                break
            # a multi-digit number keeps its digits inline (see DIGITS)
            if piece.isdigit() and piece not in DIGITS and \
                    (i == len(form) or not form[i].isdigit()):
                best[i] = head + [num_token(piece)]
                break
    return best[n]


def name_wins(token, start, t):
    """Does a capitalized token stand for a name rather than for roots?

    Names are capitalized in every notation (see DETAILS.md, Writing Systems),
    so case alone separates Mira the name from **mira** 'surprise'.  The one
    place it cannot is the start of a sentence, where every word is capitalized:
    there the root wins, and the name is only the fallback for a token no roots
    can spell.  Write **omo Mira** to force the name -- which is exactly the
    disambiguation DETAILS.md prescribes for a name that collides with a word.
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
        name = t.name_forms.get(word)
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


def english_match(words, t):
    """Exact English equivalents, when the whole query is one root or compound."""
    words = [w for w in expand_numerals(words) if not is_punct(w)]
    if len(words) != 1:
        return []
    word = words[0]
    if any(isinstance(g, tuple) for g in word):
        return [literal(g) for g in word if is_name(g)]
    gloss = "-".join(word)
    hits = list(t.compound_by_gloss.get(gloss, []))
    if len(word) == 1 and gloss in t.gloss2root:
        root = t.gloss2root[gloss]
        hits.append("%s  (root: %s)" % (root["gloss"], root["covers"]))
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
    return lines


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
