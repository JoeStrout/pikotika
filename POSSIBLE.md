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

## Shortening the most common readings

Right now almost all our roots are two syllables.  There is some scheme where only function words are one syllable, or something like that; but I can't remember exactly what the rule is and I don't find it very useful.  More useful would be shorter compound words.  So, when we have a big catalog of compounds, we could take inventory, see which roots are most commonly used, and shorten them to single syllables that play nicely with their neighbors.  This should have a noticeable impact on the fluency of the language.

(For some reason I find **verpo** especially grating; hopefully that will earn a chance to be shorter and more euphonious.)


## Root Reductions

(Currently all resolved.)

## Root Additions

The other half of the same question: if reductions freed up space, what would be
worth spending it on?  What follows are concepts the current 185 roots do not touch,
where the workaround is either long, unguessable, or missing entirely.

A concept belongs here only if *both* tests fail: no root covers it, and no short
compound reaches it.  'Health' does not qualify, for instance -- **sana** covers
"heal, cure, medicine, health, repair", so *sana-komi* 'health food' and
*sana-korpo-rapo* 'exercise' are already available.  The gloss `heal` simply hides
what the root holds, which is an argument for the secondary gloss above, not for a
new root.  The same goes for 'love' (inside **kusta**) and 'permission' (inside
**reke**).

### Strongest candidates

These resist compounding: the parts needed to build them are themselves missing, so
the workaround is a definition rather than a word.

| concept | why it is not reachable | what it unlocks |
|---|---|---|
| **find** | opposite of **perti** 'lose', but *see-get* is wrong (you can find without looking) and *want-see* is searching, not finding | find, search, look for, discover, lost-and-found, look up, hunt |
| **remember** | nothing in the set touches memory.  *not-forget* is circular; **sape** is the state of knowing, not its retention | remember, forget, memory, remind, memorize, souvenir, monument |
| **try** | no root for attempt.  *want-do* is intention, *work* is effort with no sense of uncertain outcome | try, attempt, test, taste-test, practice, experiment, "let me try" |
| **choose** | no root for selection.  *want-get* is desire, *think-after* is deliberation | choose, decide, pick, vote, option, menu, election, prefer |
| **join** | nothing expresses connection.  **sam** is sameness and **kum** is conjunction; neither attaches two things | connect, attach, tie, link, network, internet, cable, relationship, join a group |
| **carry** | *hand-go* and *with-go* both miss.  A traveler with a bag needs this constantly | carry, bring, take along, transport, luggage handling, delivery, wear |
| ~~**fight**~~ | *Adopted 2026-08-12 as **patar** 争.*  It also unlocked 'peace' (*no-fight*), which nothing else in the set could reach | fight, argue, war, compete, sport, oppose, resist, protest |
| **beautiful** | **pona** covers "pleasant", but *good-see* is faint praise for a concept this frequent in travel talk | beautiful, pretty, handsome, view, scenery, ugly (*not-*), decoration, style |
| **heavy** | no root for weight, and weight is not derivable from **meka** 'big' or **turus** 'hard' | heavy, light, weight, mass, burden, luggage limit, scales, "how much does it weigh" |
| **holy** | **temper** 'temple' exists with nothing to put in it -- no god, spirit, soul, or sacredness anywhere in the set | god, religion, spirit, soul, sacred, prayer, bless, church-vs-building, ghost |

Other ideas:
- collect/gather


### Worth considering

Reachable by compound, but common enough that the compound may be paying rent every
day:

| concept | current workaround | note |
|---|---|---|
| **die** | *not-life*, *life-close* | works, but death is basic vocabulary in every language; also gives 'kill' (*death-make*) and 'dead' |
| landscape | *up-earth* 'mountain', *long-water* 'river', *big-water* 'sea' | the three big ones are now coined.  What is still unbuilt is the finer grain: lake, island, beach, coast, forest, valley, desert -- worth revisiting once we see whether the coined three feel thin in use |
| **cook** | *food-make* (already coined as *food-make-person* 'cook') | the verb works; what is missing is 'kitchen, raw, restaurant, recipe' -- all buildable, but all through the same two roots |
| **push / pull** | nothing | *pull* is the single most common instruction on a door.  One root with both senses (direction supplied by **ver**/**vons**) may cover it |
| **safe / protect** | *not-fear* | 'safe' as a state is reachable; 'protect, guard, shelter, insurance' as an act is not |
| **laugh / smile** | *happy-say*, *happy-see* | badly served, and socially loaded; we also have no **face** to build on |
| **cloud** | *sky-water* -- now a direct collision, since 'rain' is recorded as *air-water* and **vento** covers 'sky' | weather talk is the canonical small-talk topic and we have only air, sun, and the *air-water* compound.  Cutting **ruva** raised the price of this gap, not lowered it |
| **clear** | ??? | useful for description, as well as for "is that clear?", and weather; not-clear could also mean cloudy |
| **read** | *see-word*, *see-write* | acceptable, but for a language that wants to scale to writing it is doing a lot of work |
| **full** | **pan** covers "whole, complete, enough" | may already be fine; worth checking against 'the hotel is full', 'I am full' |

### Whole domains with no coverage

Stepping back from individual words, four areas of the set are thin in a way that
single additions may not fix:

- **Body detail.**  The senses are covered -- *see-part* 'eye', *hear-part* 'ear',
  *air-taste* 'smell' -- but the substance of the body is not: no face, blood, skin,
  bone, tooth, or hair.  Medical emergencies and doctor visits are exactly the
  situation where a traveler cannot afford to paraphrase, and *see-part* does not
  help you say where it hurts.
- **Manipulation.**  We have **toma**, **tare**, **tene**, **seta**, and then
  nothing: no carry, push, pull, throw, drop, catch, turn (as an action), open-with-
  force.  The set can describe transfers of possession but not much physical handling.
- **Cognition.**  **sape**, **pensa**, **impar**, **vite** -- knowing, thinking,
  learning, understanding -- but no remembering, finding, choosing, trying, doubting,
  or deciding.  The mental verbs we have are static states; the ones missing are the
  processes.
- **Belief and ceremony.**  **temper** and **maris** are the only two entries, and
  both name buildings or events rather than the things inside them.  A language meant
  to scale past small talk will meet religion early.



### Metric sub-unit prefixes

Metric units are handled by loan words (**metoru**, **ritoru**, **kuramu** in
`names.tsv`), and the *kilo-* prefix needs nothing new: **kiru** 'thousand' already
gives **tets kiru metoru** '3 km', whose literal reading "three thousand meters" is
arithmetically exact.  Mandarin builds 千米 the same way.

What is not covered is the other direction.  Decimals reach it in writing -- 3 mm is
**0.003 metoru** -- but nobody says that out loud, and small measurements are common
in shops and repairs.  Mandarin's answer is native fraction words (厘 'hundredth',
毫 'thousandth') rather than borrowed *centi-* and *milli-*, which suggests that if
this gap bites, the fix is one Pikotise fraction root usable everywhere, not two
borrowed prefixes usable only on units.

**Why it is not in the language:** we have no observed need yet.  Adding *centi* and
*milli* as loans would be cheap; adding a general fraction root would be better and
is a bigger decision.  Waiting costs nothing, and the decimal workaround is correct
in the meantime -- it is only clumsy in speech.
