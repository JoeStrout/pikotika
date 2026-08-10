#!/usr/bin/env python3
"""Pikotise lookup and conversion tool.

Reads roots_4.tsv, compounds.tsv and names.tsv, and converts between the four
ways of writing the language:

  1. English      a word or phrase listed in the roots or compounds tables
  2. gloss        hyphenated compounds, particles as RI / A / TE
                    e.g.  water-meal RI have A what
  3. Latin        the phonological form, compounds written solid
                    e.g.  akusenar ri tene a ker
  4. Han          one character per root
                    e.g.  水飯 ⊢ 有 ⇒ 何

Run with no arguments for an interactive prompt, or pass the query on the
command line for a single lookup.  No network and no model — just the tables.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Particle names in gloss form are the particles' own pronunciations, upper-cased:
# ri / a / te.  This is the whole point — a name that is not the pronunciation is
# a second thing to keep in sync, which is how the old LI/E/PI naming drifted.
# roots_4.tsv now uses these as the gloss keys too, so the mapping is the identity
# and is kept only so the two roles stay visibly distinct.
PARTICLES = ("RI", "A", "TE")
PARTICLE_GLOSS = {p: p for p in PARTICLES}
PARTICLE_ALIASES = {p: p for p in PARTICLES}

# The corpora write numerals as digits ("2-go-paper") as well as spelled out
# ("one night"), so a digit is accepted as an alias for its numeral root.  Numbers
# with no root of their own -- 11, 20, 302 -- pass through as literals: the rule for
# composing them out of roots is not settled and this tool will not invent one.
DIGITS = {"0": "no", "1": "one", "2": "two", "3": "three", "4": "four",
          "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
          "10": "ten", "100": "hundred", "1000": "thousand",
          "1000000": "million"}


class Tables:
    def __init__(self, directory=HERE):
        self.gloss2root = {}      # gloss -> {gloss, form, han, covers, wclass}
        self.form2gloss = {}
        self.han2gloss = {}
        self.covers = {}          # english word -> [gloss, ...]
        self.compounds = {}       # english phrase -> gloss string
        self.compound_by_gloss = {}
        self.names = {}           # english name -> form
        self.form2name = {}
        self._load(directory)

    def _load(self, d):
        # the file is roots.tsv in the pikotise repo, roots_4.tsv in the old notes dir
        roots = next(os.path.join(d, n) for n in ("roots_4.tsv", "roots.tsv")
                     if os.path.exists(os.path.join(d, n)))
        with open(roots, encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if not r["form"]:
                    continue
                self.gloss2root[r["gloss"]] = r
                self.form2gloss[r["form"]] = r["gloss"]
                if r["han"]:
                    self.han2gloss[r["han"]] = r["gloss"]
                for word in r["covers"].split(","):
                    word = word.strip().lower()
                    if word and "`" not in word:
                        self.covers.setdefault(word, []).append(r["gloss"])

        with open(os.path.join(d, "compounds.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                english = r["EN"].strip()
                self.compounds[english.lower()] = r["gloss"]
                # entries are labelled "beer (any grain alcohol)"; index the
                # headword on its own too, so plain "beer" finds it
                head = english.split("(")[0].strip().lower()
                if head:
                    self.compounds.setdefault(head, r["gloss"])
                self.compound_by_gloss.setdefault(r["gloss"], []).append(english)

        names_path = os.path.join(d, "names.tsv")
        if os.path.exists(names_path):
            with open(names_path, encoding="utf-8") as fh:
                for r in csv.DictReader(fh, delimiter="\t"):
                    self.names[r["EN"].strip().lower()] = r["form"]
                    self.form2name[r["form"]] = r["EN"]

    # -- root-level accessors -------------------------------------------------

    def is_particle(self, gloss):
        root = self.gloss2root.get(gloss)
        return bool(root) and root["wclass"] == "particle"

    def form_of(self, gloss):
        return self.gloss2root[gloss]["form"]

    def han_of(self, gloss):
        return self.gloss2root[gloss]["han"]


# ---------------------------------------------------------------------------
# A parsed query is a list of words; each word is a list of glosses.  A word of
# one particle gloss is a particle; anything else is a compound (or single root).
# Names ride along as ("NAME", english) so they survive to output unsegmented.
# ---------------------------------------------------------------------------

# the corpora punctuate with free-standing , . : ? — these pass through every
# notation unchanged, so a corpus expression can be pasted in as-is
PUNCT = set(",.:;?!" "、。：；？！")


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


def parse_gloss(text, t):
    """'water-meal RI have A what' -> [[water, meal], [RI], [have], [A], [what]]"""
    words = []
    for word in text.split():
        if all(c in PUNCT for c in word):
            words.append(word)
            continue
        upper = word.upper()
        if upper in PARTICLE_ALIASES:
            words.append([PARTICLE_ALIASES[upper]])
            continue
        parts = []
        for piece in word.split("-"):
            if piece.isdigit():
                if piece in DIGITS:
                    parts.append(DIGITS[piece])
                else:
                    parts.append(num_token(piece))
                continue
            key = piece
            if key in t.gloss2root and not t.is_particle(key):
                parts.append(key)
            elif piece.lower() in t.names:                 # "Joe"
                parts.append(name_token(t.form2name[t.names[piece.lower()]]))
            elif piece.lower() in t.form2name:             # "yoe"
                parts.append(name_token(t.form2name[piece.lower()]))
            else:
                return None
        words.append(parts)
    return words or None


def segment(form, t):
    """Split a solid Latin word into root forms.  Returns one segmentation."""
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
            if piece in t.form2name:
                best[i] = head + [name_token(t.form2name[piece])]
                break
            # a multi-digit number keeps its digits inline (see DIGITS)
            if piece.isdigit() and piece not in DIGITS and \
                    (i == len(form) or not form[i].isdigit()):
                best[i] = head + [num_token(piece)]
                break
    return best[n]


def parse_latin(text, t):
    words = []
    for word in text.split():
        if all(c in PUNCT for c in word):
            words.append(word)
            continue
        if word.isdigit():
            words.append([DIGITS[word]] if word in DIGITS else [num_token(word)])
            continue
        low = word.lower()
        gloss = t.form2gloss.get(low)
        if gloss and t.is_particle(gloss):
            words.append([gloss])
            continue
        if low in t.form2name:
            words.append([name_token(t.form2name[low])])
            continue
        parts = segment(low, t)
        if parts is None:
            return None
        words.append(parts)
    return words or None


def parse_han(text, t):
    words = []
    for word in text.split():
        if all(c in PUNCT for c in word):
            words.append(word)
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
                if word[i:j].lower() not in t.form2name:
                    return None
                parts.append(name_token(t.form2name[word[i:j].lower()]))
                i = j
                continue
            ch = word[i]
            gloss = t.han2gloss.get(ch) or FREE_DIGIT_TO_GLOSS.get(ch)
            if gloss is None:
                return None
            parts.append(gloss)
            i += 1
        # a particle character stands alone as its own word
        if len(parts) == 1 and not isinstance(parts[0], tuple) \
                and t.is_particle(parts[0]):
            words.append(parts)
        else:
            if any(not isinstance(g, tuple) and t.is_particle(g) for g in parts):
                return None
            words.append(parts)
    return words or None


def parse_english(text, t):
    key = text.strip().lower()
    if key in t.compounds:
        return parse_gloss(t.compounds[key], t)
    if key in t.gloss2root and not t.is_particle(key):
        return [[key]]
    if key in t.covers:
        return [[t.covers[key][0]]]
    if key in t.names:
        return [[name_token(t.form2name[t.names[key]])]]
    return None


def looks_like_han(text, t):
    chars = [c for c in text if not c.isspace()]
    return bool(chars) and all(c in t.han2gloss or c in PUNCT
                               or c in FREE_DIGIT_TO_GLOSS
                               or c.isdigit() or c.isascii() and c.isalpha()
                               for c in chars)


def parse(text, t):
    """Try each notation in turn; returns (words, source_notation)."""
    if looks_like_han(text, t):
        words = parse_han(text, t)
        if words:
            return words, "Han"
    for fn, label in ((parse_gloss, "gloss"), (parse_latin, "Latin"),
                      (parse_english, "English")):
        words = fn(text, t)
        if words:
            return words, label
    return None, None


# -- rendering ---------------------------------------------------------------

def render_gloss(words, t):
    out = []
    for w in words:
        if is_punct(w):
            out.append(w)
        elif len(w) == 1 and not is_name(w[0]) and t.is_particle(w[0]):
            out.append(PARTICLE_GLOSS[w[0]])
        else:
            out.append("-".join(literal(g) if isinstance(g, tuple) else g
                                for g in w))
    return " ".join(out)


def render_latin(words, t):
    out = []
    for w in words:
        if is_punct(w):
            out.append(w)
            continue
        out.append(join_latin([
            t.names[g[1].lower()] if is_name(g) else literal(g) if is_num(g)
            else t.form_of(g) for g in w]))
    return " ".join(out)


def render_han(words, t):
    out = []
    for w in words:
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
    return " ".join(out)


def english_match(words, t):
    """Exact English equivalents, when the whole query is one root or compound."""
    words = [w for w in words if not is_punct(w)]
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


def lookup(text, t):
    words, source = parse(text, t)
    if not words:
        return ["  no match — not in roots_4.tsv, compounds.tsv or names.tsv"]
    lines = ["  gloss: " + render_gloss(words, t),
             "  Latin: " + render_latin(words, t),
             "  Han:   " + render_han(words, t)]
    hits = english_match(words, t)
    if hits:
        lines.append("  EN:    " + "; ".join(hits))
    return lines


def main(argv):
    t = Tables()
    if len(argv) > 1:
        print("\n".join(lookup(" ".join(argv[1:]), t)))
        return 0
    print("Pikotise — %d roots, %d compounds, %d names."
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
