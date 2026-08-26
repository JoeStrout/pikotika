# Game Design

Design notes for the Pikotika learning website: a free, account-free course that
takes a learner through the five levels of `CURRICULUM.md`. This document records
decisions and their reasons.

> **Superseded in part, 2026-08-26 — read `WEB_DETAILS.md` §Learn for what was
> actually built.** Levels 1-3 now exist at `/learn/`, and three things here
> were decided the other way:
>
> - **One task type, not six.** A card is self-graded — prompt, spacebar, ✓ or
>   ✗ — because that is what makes a card *fast*, and because a tile bank hands
>   back the recall the card was there to drive. "Sentence build", "compound
>   forge", "comprehension MC" and "listening" are not built. Production is
>   still drilled: a card can say *say this sentence in Pikotika*, with no tiles
>   offered and nobody checking.
> - **The explanations are the pages that already exist.** A lesson links to
>   one of the twenty grammar pages or seven topic pages instead of carrying its
>   own explanation screen, which retires the "Grammar lesson design" open
>   question below. The order is `build.py:GRAMMAR_GROUPS`, not `CURRICULUM.md`.
> - **No story lessons, and no audio sprites.** `DIALOGS.md` stays a reading
>   page rather than a gated lesson type, so `check_level.py` was not needed.
>   Sentence cards are drawn from `corpus.tsv`, where every line already has its
>   clip, so the course added no audio at all and needs no per-lesson bundle.
>
> What survives intact: no accounts, no timers or hearts, nothing locked, the
> URL as the progress pointer, no cross-session SRS, and spacing as a
> build-time decision. Those sections are still live and still right.

The hard part of the course is vocabulary. Each level introduces about 40 roots,
and memorizing them is the work; the grammar, by comparison, is small and regular.
So most of what follows is about making root acquisition fast, spaced, and pleasant.


## Constraints and principles

- **No accounts, no logins, no backend.** A static site. Everything the learner
  needs is served as files.
- **State is a lesson pointer.** Nothing else persists between sessions. See
  [Progress and state](#progress-and-state).
- **Payoff over points.** The motivating moment is "I can read this sentence,"
  not a streak counter. Because `CURRICULUM.md` orders roots by frequency, that
  moment is available from the first lesson onward, and every lesson should end
  on it.
- **No timers, hearts, or lives.** Time pressure suppresses the retrieval effort
  that makes recall stick, and a self-paced constructed language should not feel
  like an obligation.
- **Generated from the tables.** Lesson content is derived from `roots.tsv`,
  `compounds.tsv`, and `corpus.tsv` at build time, never hand-copied. The tables
  stay authoritative; the site cannot drift from them.


## Course structure

Five levels, about ten lessons each — roughly 50 lessons total, each a single
sitting of five to eight minutes.

Within a level, a lesson is one of:

| kind | count per level | what it does |
|---|---|---|
| **vocabulary lesson** | ~6 | introduces ~7 new roots, drills them, reviews older ones |
| **grammar lesson** | ~2 | introduces a construction (the `A` particle, aspect words, `TE` grouping) |
| **story lesson** | 2 | a dialog with comprehension questions; see [Story lessons](#story-lessons) |

Seven new roots per lesson is the key structural move. Level 1's 42 roots as a
single unit is daunting; seven is a five-minute sitting with a real ending. The
two story lessons sit mid-level and at the end — the capstone earns the level,
and the mid-level one supplies a payoff before fatigue sets in.


## Progress and state

The lesson pointer *is* the URL: `/level/3/lesson/7`. That makes progress
bookmarkable, shareable, and resumable on another device by pasting a link, with
no storage involved.

`localStorage` holds only:

- furthest lesson reached (to render the map screen and target the resume button)
- audio on/off

If that storage is cleared, the map screen simply unlocks everything and the
learner picks up where they remember being, or backs up a few lessons if they
feel rusty. This is a better failure mode than most apps achieve with accounts.

**No cross-session SRS.** Scheduling is confined to within a lesson: a Leitner
queue over that lesson's items, where a root is not done until it has been
answered correctly twice from cold. A visitor who returns after three weeks is
never greeted by a debt of overdue cards.


## Spacing is a build-time decision

Dropping the scheduler moves spacing from runtime to authoring. Nothing will
bring a Level 1 root back in Level 2 unless the lesson plan *puts* it there.

So each vocabulary lesson mixes roughly **60% new material with 40% review**,
where the review items are sampled from roots introduced two to eight lessons
back and fixed when the lesson is generated. This is curriculum-designed spacing
rather than algorithmic, and it is slightly worse per learner — but it has one
advantage a scheduler cannot match: the review items can be chosen to *combine*
with the new material, so review sentences are real sentences rather than
arbitrary pairings.


## Task types

A lesson is a series of atomic tasks. Six types, each drilling something the
others do not.

| task | direction | drills |
|---|---|---|
| **tap the meaning** | Latin → English | recognition; warmup |
| **type the root** | English → Latin | production |
| **compound forge** | English → root tiles | composition, head-final order |
| **sentence build** | English → Pikotika tiles | word order, particles |
| **comprehension MC** | Pikotika → English | precise reading |
| **listening** | audio → Pikotika tiles | phoneme decoding |

### Tap the meaning

Latin form, four English choices. Distractors are drawn from the same `category`
column in `roots.tsv` — *hand / head / leg / mouth* — so the task stays honest
rather than solvable by elimination.

### Type the root

English gloss (either `gloss` or `gloss2`) → typed Latin form. The high-value
task: production is where retention comes from. Pikotika's ten-consonant
phonology makes this genuinely easy to type and forgiving to spell-check.

### Compound forge

Given 'cat', assemble **kase** + **peste** from a bank of root tiles. This is the
task that is actually fun, and it drills roots and head-final order at once.
Compounds are the *reason* to know roots, so this makes the roots feel
load-bearing rather than arbitrary.

### Sentence build

English prompt, Pikotika word tiles, assembled into `S RI V A O`. The rigid word
order makes it mechanically checkable, and a wrong order can produce a precise
correction — "*RI* always follows a stated subject" — instead of a red X.

### Comprehension MC

The workhorse for Pikotika → English. A sentence, four English renderings, one
correct.

The power is entirely in the distractors, and the language's rigidity makes them
generative: perturb exactly one feature of the true reading.

- swap subject and object across *A* — 'The child sees me' for **Eko ri vite a nino.**
- add or drop **non**
- change the aspect word — *began* / *have* / *still* eating
- swap a root for a `category` neighbor — *father* for *mother*
- misgroup a modifier phrase — 'a big fish' versus 'a sea creature', which drills
  *TE* directly

Each is derivable from the gloss column programmatically, and a learner skimming
content words while ignoring grammar fails immediately.

This is preferred over English-tile assembly, which has a weakness in this
direction: with English tiles the content words give the answer away, and a
learner can assemble a correct sentence by recognizing **aku** and **nino**
without ever parsing *RI* or *A*.

**English tile build** is still worth having, sparingly, for sentences long
enough that four full renderings would be a wall of text. The free-variation
problem is tractable if the tile bank is constrained: offer exactly the tiles
needed plus two or three distractors, treat contractions as single tiles, and
never offer both *I'm* and *I am*. Genuine remaining alternates ('mom' /
'mother') go in an `EN_alt` column on `corpus.tsv`, semicolon-separated, matching
how `compounds.tsv` already packs English equivalents into one cell. Ship one
alternate and add the others reactively, as real learners hit them.

### Listening

Audio plays; the learner assembles what they heard from Pikotika tiles.

English cannot do "type what you hear" honestly — homophones, opaque spelling.
Pikotika can. Ten consonants, five vowels, one-to-one grapheme–phoneme mapping,
predictable penultimate stress: hearing a word *is* knowing how to spell it. The
task has exactly one correct answer with no fudging, and free typing works as a
harder variant.

That also determines the distractor tiles: **minimal pairs on the contrasts
learners actually miss** — `p`/`t`/`k`, the codas `n`/`m`, `r` versus `w`.
**pona** against **tona**, **kum** against **kun**. Random unrelated tiles teach
nothing; near-pairs make it a real discrimination drill and train the phonology
without a pronunciation lesson.


## Story lessons

A short dialog, with an English comprehension question every three or four lines.
Two per level.

`DIALOGS.md` has ten conversations already, but they were written deliberately
*without* vocabulary restriction, to find gaps in the language. They are a model
of house voice and dialog shape, not drop-in content. Story lessons need
level-gated authoring, which implies one piece of tooling:

> **`check_level.py`** — takes a draft story and a lesson number, and flags every
> root and compound not yet introduced. Without it, writing gated stories by hand
> is miserable and error-prone.

### Question types

In rough order of value:

1. **Fact retrieval** — "Who is Carla?" The floor.
2. **Why questions** that require combining two lines.
3. **Inference about a word never taught** — show a new compound in a context
   that gives it away, ask what it means, then confirm.

The third is the most valuable, and it is where the language's design and the
course mechanic fit together best: Pikotika's transparent compounding makes the
guess genuinely derivable. A learner who knows **kase** 'home' and **peste**
'animal' can work out **kasepeste**. That is a much fairer inference task than
the equivalent in a natural language.

Questions are in English, so they test comprehension rather than becoming another
vocabulary exercise.

### Presentation

- Two voices, used consistently as the same characters across all ten stories.
  Recurring characters cost nothing and make the stories a thread rather than ten
  disconnected exercises; `DIALOGS.md` already has a cast.
- Autoplay each line as it appears; tap a line to replay; tap a word for its gloss.
- A wrong comprehension answer re-asks rather than penalizing. The drilling
  happened in the preceding lessons; the story is where the learner feels that it
  worked.
- **Text shown by default**, with a "hide text" toggle for the ambitious. Hidden
  by default only in Level 5, as a deliberate step up.


## Audio

`private/speak.py` runs Kokoro locally and offline, so every clip is generated at
build time and shipped as a static file. The site needs no TTS at runtime.

### Format

**AAC (`.m4a`), mono, ~48 kbps.** Plays everywhere including iOS Safari, which is
the platform that spoils otherwise-tidy Opus plans. Opus is smaller and better for
speech if we ship two sources with `<source>` fallback. A word is roughly 3 KB, a
sentence roughly 15 KB; the entire course's audio is under 10 MB.

### Playback

Use the Web Audio API, not `<audio>` elements. `new Audio(url).play()` has
perceptible startup delay, cannot overlap with itself, and gets flaky under rapid
taps. Instead:

1. On lesson load, fetch, `decodeAudioData` once, keep the `AudioBuffer`.
2. Each tap creates a throwaway `AudioBufferSourceNode`. Sub-millisecond;
   overlapping taps are fine.

Bundle **one audio sprite per lesson** — a single concatenated file plus a JSON
map of `{form: [offsetSeconds, durationSeconds]}`. One request, one decode, and
`source.start(0, offset, duration)` slices it for free. Much better than forty
separate fetches per lesson.

### The autoplay wall

Browsers block audio until the user has interacted with the page, so "speak
automatically when the task appears" fails silently on the *first* task. The
lesson's start button is the unlock: resume the `AudioContext` from inside that
click handler. iOS requires it be inside the gesture, not merely after it.
Everything downstream then autoplays freely.

Pair this with an **audio toggle** in the header, persisted to `localStorage`.
People do lessons on trains, and a course that starts talking unprompted gets
closed.

### Two granularities

- **per word and compound** — for tile taps and word prompts
- **per whole sentence** — for sentence tasks

Do not build sentences by concatenating word clips. Each word carries its own
penultimate stress and its own final fall; strung together they produce a
robotic list rather than an utterance, with audible joins. Generate sentences as
single Kokoro passes.

Kokoro takes a **speed parameter**, so a slow variant is a second generation pass
rather than a playback trick — better quality than `playbackRate`, which
pitch-shifts under Web Audio. That gives a "turtle button" essentially free.

### Build pipeline

A batch mode alongside `speak.py` walks `roots.tsv`, `compounds.tsv`, and
`corpus.tsv`; writes WAV to a cache keyed by Latin form; skips anything already
generated; then shells to `ffmpeg` for the `.m4a` files and the per-lesson
sprites. Regeneration after a new coinage costs one clip, not the whole corpus.

Voices need an audition pass before any of this is generated in bulk. Kokoro's
voices are English-trained models being handed raw phonemes, and they will not
all handle the vowel set equally well.


## Open questions

- **Lesson plan format.** Lesson content should be generated, not hand-authored
  fifty times. Needs a table saying, per lesson: which roots are new, which are
  review, which task types run, and in what proportion.
- **Grammar lesson design.** The six task types above are vocabulary-shaped. A
  grammar lesson probably needs an explanation screen plus heavily scaffolded
  sentence builds, but this has not been worked out.
- **Level 5's 40 compounds** are not yet listed in `CURRICULUM.md`.
- **Han** is out of scope for this course. `CURRICULUM.md` lists it as an
  optional bonus level; it may become a separate mode later, but no task type
  here touches it.
