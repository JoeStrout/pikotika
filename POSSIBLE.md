# Possible Future Enhancements

Ideas that are **not part of Pikotise** as it stands.  Nothing here should be taught,
used in examples, or treated as correct; the other documents describe the language,
and this one describes things we have merely thought about.

Most entries are shortcuts -- ways to say something with less effort than the plain
rules require.  Shortcuts are cheap to add later and expensive to take back, and a
shortcut invented before anyone has used the language in earnest is a guess about
where the effort will actually be felt.  So the standing policy is to wait: let real
use show where the pain is, and adopt only the shortcuts that answer a pain we have
actually observed.


## *RI* reduced to a pause

**Idea:** *RI* may be reduced to a brief pause -- written as a comma -- whenever the
meaning stays clear.

> **Eko, tuo pari.**  'I am your parent.'
> **Eko, eko pari nino.**  'I am my parent's child.'
> **Tuo, pona omo.**  'You are a good person.'

Each is the reduced form of the full sentence, which stays correct and is always
available: **Eko ri tuo pari**, **Eko ri eko pari nino**, **Tuo ri pona omo**.

**Why it might be worth having:** *RI* marks the boundary between subject and
predicate, and a pause is the smallest thing that can mark a boundary.  So this is a
reduction of the particle rather than a deletion of it -- the signal survives in
weaker form, and a speaker who does not trust the pause to carry (a noisy room, an
unfamiliar accent, a listener still learning) simply says **ri**.  Several natural
languages run their equivalent of this construction off prosody alone: Russian, which
writes the gap as a dash, along with Hebrew, Turkish, and Hungarian.

**Why it is not in the language:** we have no evidence yet that saying **ri** is
burdensome.  It is one syllable in the most common sentence type of all, which is
exactly the sort of thing that either grates in daily use or goes unnoticed forever,
and we do not yet know which.

**Note on a simpler version that does not work.**  The tempting form of this shortcut
is to drop *RI* outright after a pronoun subject, with no pause and no replacement.
That was in the documentation for a while and has been removed, because the resulting
sentences are genuinely ambiguous.  If possession is plain juxtaposition -- **eko
kanis** 'my dog', the same pattern as any other modifier before its head -- then a
pronoun can open a noun phrase, and with *RI* gone nothing shows where the subject
ends:

| String | One reading | The other |
|---|---|---|
| **eko tuo pari** | 'I am your parent' | 'my-your parent' (one phrase) |
| **eko pona omo** | 'I am a good person' | 'my good person' (one phrase) |

Note that this is not a problem about nouns specifically.  It is a boundary problem,
and it can reach any predicate long enough to have a modifier in front of it, so no
narrow exception ("*RI* drops except before a bare noun") is enough to contain it.
Whatever form this shortcut eventually takes, it has to leave a boundary behind.


## Adverbial phrases after the verb

**Idea:** a multi-word adverbial phrase may follow the verb instead of preceding it.

> **Eko ri ire piko tar piko.**  'I am going little by little.'

The rule today puts every modifier before what it modifies, which gives **Eko ri piko
tar piko ire** -- correct, but with four words wedged between *RI* and the verb, and
the listener holding all of them before learning what is being modified.  English and
Spanish both prefer such a phrase trailing ('go little by little', *ir poco a poco*),
which suggests the weight is felt elsewhere too.

**Why it is not in the language:** modifier-before-head is one of the few rules
Pikotise has, and it is currently exceptionless -- it holds inside compounds, inside
noun phrases, and before verbs alike.  Buying comfort in one construction with an
exception to a rule that general is a bad trade until we know the discomfort is real.
A single-word adverb before the verb is clearly fine, so the question is only where
the phrase gets long enough to hurt, and that is exactly the sort of threshold that
guessing gets wrong.


## Allow a secondary gloss?

Our root words, by necessity, cover many concepts, but currently we pick just one to represent it as the gloss.  This can lead to some initial confusion when using 'food' as a verb, or 'sun' to mean 'day', or 'open' to mean 'begin'.

We could consider blessing a *secondary* gloss, and allowing the primary or secondary to  be used when writing gloss form.  Our tools could easily convert from gloss to Latin and Han using either word.  When converting *to* gloss automatically, it would be hard (without LLM-level AI) to reliably pick the clearest one, but maybe some heuristics will help... and anyway it couldn't come out worse than the current situation.  (It might complicate round-trip tests, though.)


## Root Reductions

We currently have four roots describing different parts of the day, in addition to **sore** itself:

| Pikotise | Han | Meaning |
|---|---|---|
| **sore** | 日 | day, daytime |
| **matin** | 朝 | morning |
| **mesyo** | 午 | noon, midday |
| **vesper** | 夕 | evening |
| **note** | 夜 | night |

That seems extravagant.  These do combine with 'meal' to make breakfast, etc.; and we combine this+night to make tonight.  But it's still a lot.

We could consider eliminating these and building them in other ways, for example, by assigning each part of the day a color and using the color word plus day, hour, or time.

We also have a separate word for 'meal' (**senar**), which seems excessive when we already have 'food' (**komi**).

**Already covered by another root's `covers` list.**  These are the cheapest to look
at, because the overlap is written down in our own table:

| root | overlaps | note |
|---|---|---|
| **kosto** 'price' (1) | **moni** 'money' | *moni* already covers "price, cost, value, payment" |
| **mets** 'middle' (0) | **in** | *in* already says "middle/between = `in-side`" |
| **torer** 'pain' (1) | **mara** 'sick' | *mara* already says "pain = `sick-feel`" |
| **poten** 'power' (0) | **rapo** 'work', **kan** 'able' | *rapo* covers "effort, use" and its han is 力; *kan* covers "ability, capable" |
| **paror** 'language' (1), **nomen** 'name' (1) | **verpo** 'word' | *verpo* covers "language, speech, name, message" outright |
| **ravor** 'job' (1) | **rapo** 'work' | *rapo* covers "job" |
| **ras** 'side' (1) | **eks**, **in** | maybe; *ras* is load-bearing for *morning-side* 'east' |

**Concrete nouns that look like ordinary compounds.**  Most of these have zero
recorded uses:

| root | possible replacement |
|---|---|
| **uter** 'tool' (0) | *work-thing* |
| **tapur** 'table' (0) | *flat-thing*, *food-flat* |
| **panyu** 'toilet' (0) | *water-room* |
| **oster** 'hotel' (0) | *sleep-home*, *money-home* |
| **komer** 'shop' (0) | *buy-place* |
| **kirmen** 'crime' (0) | *not-law thing*, *bad-work* |
| **venter** 'stomach' (0) | *food-room*, *food-place* |
| **ropa** 'cloth' (0) | *body-cover* (we have no *cover* -- *out-body cloth* problem) |
| **sares** 'salt' (0) | *white-stone*, *food-stone* |
| **oren** 'oil' (0) | *meat-water*, *food-water* |
| **raten** 'milk' (0) | *animal-water*, *white-drink* |
| **ovum** 'egg' (1) | *bird-child* |
| **karne** 'meat' (1) | *animal-food* |
| **avis** 'bird' (0), **inses** 'bug' (0), **kanis** 'dog' (0) | *air-animal*, *small-many-leg animal*, ? -- these were kept when `fish`/`cat` were cut, so the reasoning is already on record |
| **ruva** 'rain' (0) | *sky-water*, *down-water* |
| **metar** 'metal' (1) | *hard-stone* |
| **karta** 'paper' (2) | *write-thing*, *flat-write* |
| **arti** 'art' (0) | *make-way*, *see-make* |
| **pitur** 'picture' (1) | *see-thing*, *see-make* |
| **seman** 'week' (2) | *seven-day* -- transparent, and it is what the root means |
| **verya** 'weekday' (3) | *day-number*, *week-part* |
| **kina** 'relative' (0) | *parent-group*, *big-parent group* |
| **korpo** 'body' (0) | *self-thing* -- weak; body is basic |
| **testa** 'head' (2) | *up-part*; the 'leader, chief' sense is the one worth keeping |

**Antonym pairs where one member could be `not-` the other.**  We already do this for
front (`not-back`) and that/there (`not-this`), so the pattern is established:

| pair | candidate to drop | replacement |
|---|---|---|
| **voka** 'fire, hot' / **yeru** 'cold' (2) | *yeru* | *not-fire* |
| **nova** 'new' / **vetus** 'old' (1) | *vetus* | *not-new* |
| **pona** 'good' / **marum** 'bad' (5) | *marum* | *not-good* -- but *marum* is frequent and *mara* 'sick' already carries "bad" flavor; note *mara*/*marum* are near-homophones, which is its own problem |
| **ron** 'far' (0) / **nir** 'near' (2) | *ron* | *not-near*; also note *ron* and **ronka** 'long' are near-homophones with overlapping senses ("distant" appears in both) |
| **mara** 'sick' / **sana** 'heal' (2) | *sana* | *not-sick make*, *good-make* |
| **non** 'not' / **nem** 'zero' (4) | *nem* | *not-number*, *not-one* |
| **rotun** 'round' (2) / **reto** 'straight' (2) / **kurva** 'bend' (1) | *rotun* or *kurva* | *round* = *all-bend*; *straight* = *not-bend* |

**Verb clusters.**  Looser, and the ones most likely to be false economies:

- **impar** 'learn' (2) -- *new-know*, *become-know*.  We have **sape** 'know',
  **pensa** 'think', and **vite** 'see (understand)' already.
- **asper** 'wait' (0) -- *time-remain*, given **sista** 'remain, stay'.
- **seta** 'put' (0) -- *place-make*, given **roko** and **vake**.
- **perti** 'lose' (0) -- *not-have become*, *bad-get*.
- **kompar** 'buy' (0) -- *money-change*, given **moni** and **muta**; *muta* itself
  covers "exchange".
- **tiven** 'become' (1) vs **muta** 'change' (0) -- one of these two, probably.
- **monta** 'ride' (1) -- *vehicle-in be*, *vehicle-remain*.
- **neses** 'need' (3) -- *big-want*, given **kere**.
- **servi** 'help' (0) -- *for-work*, *good-work*.
- **ruti** 'play' (1) -- *happy-work*, *fun-do*.
- **akor** 'agree' (1) -- *same-think*, *same-say*; note **reke** 'law' covers "rule,
  permission" and **maris** 'marry' (0) could be *law-pair* or *always-agree*.
- **toma** 'get' (3) -- *to-have*, *become-have*, given **tene** and **tare**.

**Feelings and social formulae.**  The politeness words (**pam**, **perton**,
**mersi**) earn their keep on frequency, but the rest are thin:

- **putor** 'shame' (0) -- *bad-feel*, *self-bad feel*.
- **kortes** 'polite' (0) -- *good-way*, *good-say*.
- **kansa** 'tired' (1) -- *sleep-want*, *work-after*.
- **timo** 'fear' (0) -- *bad-if feel*; but 'danger' is a travel-critical sense.
- **seren** 'calm' (1) -- *not-fast*, *not-noise*; 'quiet' is already reachable from
  **oti** 'sound, noise'.
- **sapor** 'taste' (3) -- *mouth-feel*.

**Grammar and quantity overlaps.**  Small set, high frequency, so removals here are
expensive -- but the overlaps are real:

- **kan** 'able' (4) / **pos** 'if, possible' (2) / **poten** 'power' (0) -- three
  roots on the *posse* concept.  *pos* is the odd one, glossed 'if' but covering
  "possible, chance, luck".
- **mens** 'measure' (3) / **nus** 'number' (1) / **mur** 'many, quantity' (3) --
  *nus* could be *number-word* or just *mens*.
- **son** 'only' (2) / **wun** 'one' (10) -- *only* = *one-ly*, *just-one*.
- **ves** 'true' (8) / **si** 'yes' (11) -- distinct classes (interjection vs
  modifier), but the same content; **reto** 'straight, direct' adds "correct" on top.
- **mas** 'more, again, another' (6) / **ar** 'other, different' (1) / **muta**
  'differ' (0) -- three roots touching sameness and difference, opposite **sam**.
- **panto** 'group' (11) / **pan** 'all' (6) -- near-homophones; *panto* is frequent
  enough to keep, but the phonetic collision is worth noting on its own.
- **katon** 'hundred' (3) / **kiru** 'thousand' (1) / **miron** 'million' (0) -- a
  place-value system built from **tekas** could reach these, at a cost in length.

