#!/usr/bin/env python3
"""Build web/data/lessons.json -- the course, one entry per lesson.

`lessons.tsv` is the only hand-authored part of the course: per lesson, a page
to read and a list of new items.  Everything else is derived here, so the
course cannot drift from the tables the way a hand-copied lesson would.

What a lesson is
----------------
A short list of new words to look at, optionally a grammar or topic page to go
read, and a small deck of flashcards.  The deck is the drill; the page is the
explanation, and the site already has twenty of those.

A card is a prompt and an answer, self-graded.  `k` says what is on it --
`word` for a root or a compound, `sent` for a whole sentence -- and *not* which
way round it is asked.  Direction is a runtime matter: learn.js flips a card
every time it is dealt, so one card drills both English -> Pikotika and
Pikotika -> English without being two cards (decided 2026-08-26).  Recognition
and production are the same item seen from either side, and asking for the deck
to be twice as long to cover both would make it a chore.

Nothing checks the answer.  That is the design (decided 2026-08-26): a card the
learner grades themselves takes a few seconds, and a tile bank that could be
checked would both slow the card down and hand back the recall it was meant to
drive.  What the learner has to do is *say it*, unaided, and then look.

Spacing is a build-time decision
--------------------------------
There is no cross-session scheduler -- a visitor who comes back after a month
is never met with a debt.  So review has to be *placed*: each lesson's deck
carries four items drawn from two to eight lessons back, which is far enough
that they are no longer free and near enough that they have not gone cold.
The sample is seeded from the lesson id, so a rebuild produces the same deck.

Sentences come from corpus.tsv, and only from there.  A lesson can offer a
sentence exactly when every root in it has been taught, which `walk()` tracks;
the ones a lesson has just unlocked are offered first.  Three lessons in Levels
1-3 unlock nothing, which is left alone deliberately -- a deck with no
sentences in it is a short one, and a short one now and then is a rest.
"""

import csv
import json
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LESSONS_TSV = os.path.join(HERE, "lessons.tsv")
OUT = os.path.join(HERE, "web", "data", "lessons.json")

TSV = dict(delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None)

# The three particles are written in gloss notation as themselves.
PARTICLE_TOKENS = {"RI", "A", "TE"}

REVIEW_CARDS = 4        # older items mixed into an ordinary lesson
LESSON_SENTENCES = 3    # sentence cards in an ordinary lesson
REVIEW_SENTENCES = 8    # ... and in a level review

# How far back a review item is drawn from.  Nearer than MIN and it has not
# been away long enough to be worth asking; further than MAX and the lesson
# stops being a review of anything in particular.
REVIEW_MIN_BACK = 2
REVIEW_MAX_BACK = 8

# An English cell may list several equivalents; more than this on a card front
# reads as a paragraph rather than a prompt.
MAX_ENGLISH = 3


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, **TSV))


class Course:
    """The tables the course is built from, indexed the way it needs them."""

    def __init__(self):
        self.roots = read_tsv(os.path.join(HERE, "roots.tsv"))
        self.compounds = read_tsv(os.path.join(HERE, "compounds.tsv"))
        self.corpus = read_tsv(os.path.join(HERE, "corpus.tsv"))
        self.names = read_tsv(os.path.join(HERE, "names.tsv"))
        self.plan = read_tsv(LESSONS_TSV)

        # gloss2 is a full alias for gloss -- either may be written in gloss
        # notation -- so a lesson may name a root by whichever reads better.
        self.alias = {}
        for row in self.roots:
            self.alias[row["gloss"]] = row["gloss"]
            if row["gloss2"]:
                self.alias.setdefault(row["gloss2"], row["gloss"])

        self.root = {row["gloss"]: row for row in self.roots}
        self.compound = {row["gloss"]: row for row in self.compounds}
        self.english_names = set()
        # The sanctioned loans, which are the one kind of name that may sit
        # inside a hyphenated gloss word (**kirumitar**, thousand-meter).  Like
        # any name they teach no root, so they gate no lesson -- see roots_of.
        self.loan_tokens = set()
        for row in self.names:
            english = [e.strip() for e in row["EN"].split(";")]
            self.english_names.update(english)
            if (row.get("kind") or "").strip() == "loan":
                self.loan_tokens.update(english)
                self.loan_tokens.add(row["form"])

    # --- reading gloss notation ------------------------------------------

    @staticmethod
    def gloss_words(text):
        return [w for w in re.sub(r'[.,?!;:"]', " ", text).split()
                if w and w != "..."]

    def roots_of(self, word):
        """The root glosses a gloss-notation word depends on.

        None means the word could not be read at all, which is a table
        problem rather than a course one -- check_lessons.py reports it."""
        if word in PARTICLE_TOKENS or re.fullmatch(r"[-\d%./]+", word):
            return set()
        if word in self.alias:
            return {self.alias[word]}
        # A name stays in Latin and teaches no root, so it gates nothing.
        if word in self.english_names or word[:1].isupper():
            return set()
        parts = set()
        for piece in word.split("-"):
            # a loan inside a compound is still a name: no root, no gate
            if piece in self.loan_tokens:
                continue
            if piece not in self.alias:
                return None
            parts.add(self.alias[piece])
        return parts

    def sentence_roots(self, row):
        need = set()
        for word in self.gloss_words(row["gloss"]):
            got = self.roots_of(word)
            if got is None:
                return None
            need |= got
        return need

    # --- walking the plan -------------------------------------------------

    def walk(self):
        """Yield the state after each row of lessons.tsv, in order.

        One pass serves both readers: this module builds decks from it and
        check_lessons.py validates against it, so there is no second opinion
        about what a learner knows by lesson N."""
        known_roots = set()
        known_items = []
        seen_sentences = set()
        for row in self.plan:
            items = [i for i in row["new"].split(";") if i]
            for item in items:
                got = self.roots_of(item)
                if got:
                    known_roots |= got
            known_items = known_items + items

            readable, fresh = [], []
            for line in self.corpus:
                need = self.sentence_roots(line)
                if need is None or not (need <= known_roots):
                    continue
                readable.append(line)
                if line["latin"] not in seen_sentences:
                    fresh.append(line)
            seen_sentences.update(line["latin"] for line in readable)

            yield {
                "row": row,
                "id": "%s.%s" % (row["level"], row["lesson"]),
                "items": items,
                "known_roots": set(known_roots),
                "known_items": list(known_items),
                "readable": readable,
                "fresh": fresh,
            }

    # --- turning a reference into something a card can show ---------------

    def entry(self, ref):
        """form, gloss, English, Han and hint for one item reference.

        `hint` is the card's third line, and it follows the same rule the word
        popover does (WEB_DETAILS, "Word chips"): the mnemonic for a root, the
        parse for a compound, never both -- a root has no parse and a compound
        has no mnemonic of its own.  Showing a root's *gloss* there, which is
        what this did at first, printed the English that was already on the
        card one line above it."""
        if ref in self.compound:
            row = self.compound[ref]
            import pikotika
            tables = _tables()
            words = pikotika.parse_gloss(row["gloss"], tables)
            return {
                "ref": ref,
                "kind": "compound",
                "form": pikotika.render_latin(words, tables),
                "gloss": row["gloss"],
                # A compound's hint is its parse -- *home-animal* -- which is
                # the thing that makes it guessable next time.
                "hint": row["gloss"],
                "han": pikotika.render_han(words, tables),
                "en": [e.strip() for e in row["EN"].split(";") if e.strip()],
            }
        gloss = self.alias[ref]
        row = self.root[gloss]
        if row["category"] == "Particles":
            # A particle has no English word to be asked for -- *RI* glosses
            # as itself -- so the prompt is the job it does, which is what
            # roots.tsv's `covers` already says: "object boundary" -> a.
            english = [row["covers"]]
        else:
            english = [row["gloss"]] + ([row["gloss2"]] if row["gloss2"] else [])
        return {
            "ref": gloss,
            "kind": "root",
            "form": row["form"],
            "gloss": gloss,
            # The cards are the only place on the site a learner meets the
            # mnemonics, and a card is exactly when they are wanted -- so they
            # go on both directions, not only on the one that shows the word.
            # The `*asterisks*` are rendered by site.js:appendEmphasis.
            "hint": row["mnemonic"],
            "han": row["han"],
            "en": english,
        }

    def sentence(self, row):
        return {"en": row["EN"], "form": row["latin"],
                "gloss": row["gloss"], "han": row["han"]}


_TABLES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        import pikotika
        _TABLES = pikotika.Tables()
    return _TABLES


def prompt_english(entry):
    return "; ".join(entry["en"][:MAX_ENGLISH])


def word_card(entry):
    return {"k": "word", "form": entry["form"], "han": entry["han"],
            "hint": entry["hint"], "en": prompt_english(entry)}


def sentence_card(sent):
    # A sentence's hint is its gloss notation, which is what shows how the
    # sentence is put together rather than merely what it says.
    return {"k": "sent", "form": sent["form"], "han": sent["han"],
            "hint": sent["gloss"], "en": sent["en"]}


def pick_sentences(state, want):
    """Sentence cards for one lesson: what it just unlocked, then older ones.

    Leading with the fresh ones is the point -- a sentence a learner could
    already read is review, and a sentence that has just become readable is
    the lesson's payoff."""
    rng = random.Random("sent:" + state["id"])
    fresh = list(state["fresh"])
    rng.shuffle(fresh)
    picked = fresh[:want]
    if len(picked) < want:
        rest = [line for line in state["readable"] if line not in state["fresh"]]
        rng.shuffle(rest)
        picked += rest[:want - len(picked)]
    return picked


def pick_review(course, states, index, want):
    """Items from two to eight lessons back, as review cards.

    Drawn from the lessons rather than from everything known, so the sample
    stays in the window: everything a learner has ever seen would put Level 1
    lesson 1 into the deck at Level 3, where it is neither due nor useful."""
    window = []
    for back in range(REVIEW_MIN_BACK, REVIEW_MAX_BACK + 1):
        j = index - back
        if j >= 0:
            window += states[j]["items"]
    if not window:
        return []
    rng = random.Random("review:" + states[index]["id"])
    rng.shuffle(window)
    return window[:want]


def interleave(new_cards, review_cards, sentence_cards, seed):
    """One deck, shuffled but not evenly.

    The new material leads -- it is what the lesson is for, and it has just
    been read off the page above -- and the review and the sentences are dealt
    into the back two thirds rather than stacked at the end, so the deck does
    not turn into two decks."""
    rng = random.Random("deck:" + seed)
    deck = list(new_cards)
    rng.shuffle(deck)
    extras = list(review_cards) + list(sentence_cards)
    rng.shuffle(extras)
    floor = max(1, len(deck) // 3)
    for card in extras:
        deck.insert(rng.randrange(floor, len(deck) + 1), card)
    return deck


def build():
    """The whole course as one JSON-ready dict."""
    course = Course()
    states = list(course.walk())

    lessons = []
    for i, state in enumerate(states):
        row = state["row"]
        is_review = row["lesson"] == "R"

        if is_review:
            # A level review gathers that level's own items, not everything
            # known: the point is to close the level, and the earlier levels
            # have had reviews of their own.
            refs = [ref for s in states[:i]
                    if s["row"]["level"] == row["level"]
                    for ref in s["items"]]
            entries = [course.entry(ref) for ref in refs]
            new_cards = [word_card(e) for e in entries]
            review_cards = []
            sentences = pick_sentences(state, REVIEW_SENTENCES)
        else:
            entries = [course.entry(ref) for ref in state["items"]]
            new_cards = [word_card(e) for e in entries]
            review_cards = [word_card(course.entry(ref))
                            for ref in pick_review(course, states, i, REVIEW_CARDS)]
            sentences = pick_sentences(state, LESSON_SENTENCES)

        sentence_cards = [sentence_card(course.sentence(s)) for s in sentences]

        lessons.append({
            "id": state["id"],
            "level": int(row["level"]),
            "n": row["lesson"],
            "title": row["title"],
            "page": row["page"] or None,
            "note": row.get("note") or None,
            "review": is_review,
            "words": entries,
            "cards": interleave(new_cards, review_cards, sentence_cards,
                                state["id"]),
        })

    return {"lessons": lessons}


def write(course=None):
    data = course if course is not None else build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    return OUT


if __name__ == "__main__":
    data = build()
    path = write(data)
    total = sum(len(l["cards"]) for l in data["lessons"])
    print("Wrote %s: %d lessons, %d cards, %d bytes."
          % (os.path.relpath(path, HERE), len(data["lessons"]), total,
             os.path.getsize(path)))
