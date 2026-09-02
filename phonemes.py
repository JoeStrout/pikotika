#!/usr/bin/env python3
"""Pikotika -> IPA phonemes, for any text-to-speech that can be fed phonemes.

Extracted from the `private/speak.py` prototype so that the interactive tool and
the batch audio build cannot drift apart: this is the one description of how the
language sounds, and it belongs beside the tables rather than inside a tool.

Nothing here is filtered through English spelling rules -- **pona** is spoken as
it is written, not as an English speaker would guess it.

    >>> to_phonemes("Pam sista wun pikotempo.")
"""

import re

import pikotika

# -- the sounds --------------------------------------------------------------

# Kokoro's vocabulary is a fixed set of 114 IPA symbols, and -- this is the trap
# -- anything outside it is dropped silently rather than raising, so a wrong
# symbol here would come out as a missing sound with no error.  Every symbol
# below was checked against kokoro_onnx.config.DEFAULT_VOCAB; check_symbols()
# re-checks at startup so an edit to these tables cannot fail quietly.

CONSONANTS = {
    "p": "p", "t": "t", "k": "k",
    "v": "v", "s": "s",
    "r": "ɾ",       # 'ɹ', 'l', and 'ɾ' are all valid here
    "m": "m", "n": "n",
    "w": "w", "y": "j",
}

# Pure monophthongs.  Kokoro also has the diphthong tokens A I O W Y (/eɪ aɪ oʊ
# aʊ ɔɪ/) which are what English 'they' and 'go' would give you -- exactly what
# Pikotika does not want, since it has no diphthongs.  If 'e' and 'o' sound too
# close for your ear, the open variants 'ɛ' and 'ɔ' are the ones to try.
VOWELS = {"a": "ɑ", "e": "e", "i": "i", "o": "o", "u": "u"}

STRESS = "ˈ"

# Two positional variants, both of them readings pikotika.org/grammar/pronunciation/
# already lists as correct for the letter.  Each is written into the word as a placeholder before
# the letters are looked up, so that the tables above stay a plain one-to-one
# map and the variants are visibly the exceptions they are.
VELAR_N = True      # `n` is 'ng' before p, t or k
INITIAL_Y = True    # `y` is 'zh' (the s of 'measure') at the start of a word

MARKS = {"\0": "ŋ", "\1": "ʒ"}

# The three particles lean on the neighboring word and take no stress of their
# own (pikotika.org/grammar/pronunciation/).  `rite` is a word and does take one.
CLITICS = {"ri", "a", "te"}

# -- transcription -----------------------------------------------------------


def syllabify(word):
    """Split a Pikotika word into syllables.

    Onsets are a single consonant at most, so of the consonants sitting between
    two vowels exactly the last one starts the next syllable and the rest close
    the current one: `kasepeste` -> ka-se-pes-te.
    """
    nuclei = [i for i, c in enumerate(word) if c in VOWELS]
    if not nuclei:
        return [word]
    out, start = [], 0
    for n, i in enumerate(nuclei):
        if n + 1 == len(nuclei):
            out.append(word[start:])
        else:
            j = nuclei[n + 1]
            split = j - 1 if j - 1 > i else j   # j-1 == i means two vowels meet
            out.append(word[start:split])
            start = split
    return out


def word_phonemes(word):
    """One Latin word -> its phonemes, with the stress mark in place."""
    w = word.lower()
    if not w:
        return ""
    clitic = w in CLITICS
    if VELAR_N:
        w = re.sub(r"n(?=[ptk])", "\0", w)
    if INITIAL_Y and w.startswith("y"):
        w = "\1" + w[1:]
    sylls = syllabify(w)
    # Stress is always penultimate, and a monosyllable carries its own.
    stressed = -1 if clitic else max(len(sylls) - 2, 0)
    out = []
    for i, syll in enumerate(sylls):
        sounds = ""
        for c in syll:
            # The stress mark goes immediately before the *vowel*, not at the
            # start of the syllable: espeak writes 'pico' as pˈiːkoʊ, with the
            # mark after the p.  Putting it before the onset consonant instead
            # makes the model expect a vowel there and supply a schwa, so
            # `pikoˈtika` comes out as "piko-uh-TI-ka".
            if i == stressed and c in VOWELS and STRESS not in sounds:
                sounds += STRESS
            sounds += MARKS.get(c) or VOWELS.get(c) or CONSONANTS.get(c, "")
        out.append(sounds)
    return "".join(out)


# A numeral is *written* in digits and *said* in words -- **20 moni** is `pits
# tekas moni` (pikotika.org/topics/numbers/) -- so the digits have to be spelled out
# before anything is phonemized.  Left alone they reach the engine as digits,
# which is an English text-to-speech model being handed an Arabic numeral: it
# says "twenty", in English, in the middle of a Pikotika sentence.
#
# The run must be free-standing.  A digit bound inside a compound is part of
# that word and stays a digit, which is the same test pikotika.numeral_words
# applies.  The marks that can sit inside one are the decimal point, the colon
# of a clock time, and the slash of a fraction; `%` closes one.
NUMERAL = re.compile(r"(?<![0-9A-Za-z])\d+(?:[./:]\d+)?%?(?![0-9A-Za-z])")

_tables = None


def _tables_once():
    global _tables
    if _tables is None:
        _tables = pikotika.Tables()
    return _tables


def spell_numerals(latin):
    """`Kamar 12, sur` -> `Kamar tekas pits, sur`.

    The comma pikotika puts between a thousands group and the rest survives
    into the phonemes, where Kokoro reads it as the pause it is."""
    def spell(match):
        words = pikotika.numeral_words(match.group(0))
        if words is None:
            return match.group(0)
        return pikotika.render_latin(words, _tables_once())
    return NUMERAL.sub(spell, latin)


# The hesitation filler (pikotika.org/topics/pleasantries/) is a held mid vowel, not
# the one-syllable word `e` would otherwise be phonemized as.  The trailing
# ellipsis is left in place and does the rest: Kokoro has it, and reads it as
# the trailing pause a hesitation ends on.  Stressed, because an unmarked lone
# vowel is what the model reduces to a schwa.
# Measured against Kokoro, bm_george, at speed 1.0: one "e\u02d0" is 0.26 s, which
# runs straight into the next word.  Stacking length marks is nearly inert
# ("e\u02d0\u02d0" buys 0.03 s); repeating the vowel is what scales -- 0.35 s for two,
# 0.43 s for three with the ellipsis, which sounds like a hesitation rather
# than a clipped vowel.  Re-measure if the voice or SPEED changes.
FILLER_LENGTH = 3
FILLER_SOUND = STRESS + "e\u02d0" * FILLER_LENGTH

# ...and the silence that follows it, in seconds.  It has to be spliced into
# the audio because no *token* produces it: fed phonemes, Kokoro reads
# punctuation as prosody but not as duration, and measured over "\u2026", ",", ".",
# an em dash, "\u2026\u2026", ", \u2026" and padding spaces the gap after the filler never
# exceeded 0.08 s.  Kokoro's own trailing and leading silence adds about
# 0.17 s on top of this, so 0.15 s here is a ~0.32 s pause in the clip.
FILLER_PAUSE = 0.15

# The filler first, so `e...` is a drawl and `eko` is still a word.  One pass,
# because a second one would re-phonemize the letters this one just wrote.
SPEAKABLE = re.compile(r"(?<![A-Za-z])[eE](?=\u2026|\.\.\.)|[a-zA-Z]+")

# The filler with the ellipsis it carries -- what `segments` splits a line on.
FILLER_PIECE = re.compile("(" + re.escape(FILLER_SOUND) + r"(?:\u2026|\.\.\.)?)")


def segments(latin):
    """A line as (phonemes, pause_after_seconds) pieces, in order.

    One piece for almost everything.  A hesitation filler is the exception: it
    ends in real silence, which means two renderings with a gap between them
    rather than one -- see FILLER_PAUSE.  Rendering the remainder separately is
    also what a hesitation sounds like, since the sentence picks up again with
    its own opening contour."""
    pieces = [p.strip() for p in FILLER_PIECE.split(to_phonemes(latin))]
    out = [(p, FILLER_PAUSE if FILLER_PIECE.fullmatch(p) else 0.0)
           for p in pieces if p]
    if out:
        out[-1] = (out[-1][0], 0.0)     # never trail a clip with silence
    return out


def to_phonemes(latin):
    """A line of Latin Pikotika -> a line of phonemes, punctuation intact.

    Punctuation is left alone deliberately: Kokoro reads commas, periods and
    question marks as prosody, which is most of what makes a sentence sound
    like a sentence rather than a list of words.
    """
    def sound(m):
        return (FILLER_SOUND if m.group(0).lower() == pikotika.FILLER
                else word_phonemes(m.group(0)))
    return SPEAKABLE.sub(sound, spell_numerals(latin))


ALPHABET = set(CONSONANTS) | set(VOWELS)


def foreign_letters(latin):
    """Letters that are not in the 15-letter alphabet, in order, deduplicated.

    These have no sound assigned and so are dropped -- the same silent-drop
    problem Kokoro's vocabulary has, one level up.  Worth saying out loud,
    because the usual cause is input meant as gloss or English that did not
    parse and is now being sounded out letter by letter.
    """
    seen = [c for c in latin.lower() if c.isalpha() and c not in ALPHABET]
    return list(dict.fromkeys(seen))


def to_latin(text, tables):
    """Normalize any notation to Latin.  Returns (latin, notation_or_None).

    Unparsable input comes back unchanged -- a name or a fresh coinage is still
    perfectly speakable, it just is not in the tables.
    """
    words, notation = pikotika.parse(text, tables)
    if not words:
        return text, None
    return pikotika.render_latin(words, tables), notation


def check_symbols():
    """Fail loudly if a symbol above is not one Kokoro knows (see CONSONANTS)."""
    from kokoro_onnx.config import DEFAULT_VOCAB
    ours = set(CONSONANTS.values()) | set(VOWELS.values()) | set(MARKS.values())
    ours.add(STRESS)
    ours.update(FILLER_SOUND)
    unknown = sorted(ours - set(DEFAULT_VOCAB))
    if unknown:
        raise SystemExit("Not in Kokoro's vocabulary: %s" % " ".join(unknown))
