# Possible Future Enhancements

Ideas that are **not part of Pikotika** as it stands.  Nothing here should be taught,
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
Pikotika has, and it is currently exceptionless -- it holds inside compounds, inside
noun phrases, and before verbs alike.  Buying comfort in one construction with an
exception to a rule that general is a bad trade until we know the discomfort is real.
A single-word adverb before the verb is clearly fine, so the question is only where
the phrase gets long enough to hurt, and that is exactly the sort of threshold that
guessing gets wrong.


## Gapping a repeated predicate after **sets**

**Idea:** when a **sets** ('but') clause repeats the predicate of the clause before it
and differs only in polarity, the predicate may be left out, stranding **non** alone
after *RI*.

> **Soretar, eko vemapari ri veni, sets eko viropari ri non.**
> 'Tomorrow my mother is coming, but my father isn't.'

The full form stays correct and is always available: **sets eko viropari ri non
veni**.

**Why it might be worth having:** the reduced form is genuinely clear.  Word order is
rigid, so the empty slot is identifiable; the parallel clause supplies the only
candidate predicate; and **non** already stands alone as 'no' in short answers, so
nothing about a bare **non** is unfamiliar.  Pikotika also elides elsewhere already --
**Kum tuo, ker?** 'And you?' drops an entire predicate -- so ellipsis as such is not
foreign to the language.

**Why it is not in the language:** three reasons, in increasing order of weight.

First, it saves almost nothing.  **non veni** to **non** is one syllable, against a
new grammatical device to learn.

Second, sentence-final **non** is already the yes/no tag that expects the answer yes
(**Tuo ri vite a kanis, non?**).  Written, the comma keeps them apart.  Spoken,
**...ri non** and **..., non?** are separated only by a pause and intonation, and
Pikotika avoids resting a distinction on prosody everywhere else.

Third and decisive: **there is no affirmative counterpart.**  The shortcut works only
because **non** happens to be available to strand.  Reverse the polarity --
'Tomorrow my mother isn't coming, but my father is' -- and the second clause has an
empty predicate and no negator to fill it.  The obvious repair is to license **si**
in the slot (**sets eko viropari ri si**), but **si** is described as an interjection,
not a predicate, so that is a second new device rather than a free consequence of the
first.  A gapping rule that works in one polarity and not the other is worse than no
rule at all.

**Note on why the English intuition does not transfer.**  English gaps here by
stranding an auxiliary: 'my father isn't' keeps *is*, a real verb carrying tense, and
deletes the lexical verb under it.  Pikotika has no auxiliaries.  *RI* looks like the
place to strand something but is a particle marking the predicate boundary, not a verb
that can host anything -- so the only thing left to strand is **non** itself, which
means promoting a modifier to predicate.  That is a category shift the grammar asks
for nowhere else, and it is the reason this is a new mechanism rather than an
application of an existing one.

**If it is ever adopted**, prefer the narrow form -- "*RI* plus **non** alone answers a
parallel positive clause" -- over the general one, "elide any predicate recoverable
from a parallel clause."  The general version invites gapping in clause pairs that
differ in more than one slot, where rigid word order stops doing the recovery work.


## Allow a secondary gloss?

Our root words, by necessity, cover many concepts, but currently we pick just one to represent it as the gloss.  This can lead to some initial confusion when using 'food' as a verb, or 'sun' to mean 'day', or 'open' to mean 'begin'.

We could consider blessing a *secondary* gloss, and allowing the primary or secondary to  be used when writing gloss form.  Our tools could easily convert from gloss to Latin and Han using either word.  When converting *to* gloss automatically, it would be hard (without LLM-level AI) to reliably pick the clearest one, but maybe some heuristics will help... and anyway it couldn't come out worse than the current situation.  (It might complicate round-trip tests, though.)

## Shortening the most common readings

Right now almost all our roots are two syllables.  There is some scheme where only function words are one syllable, or something like that; but I can't remember exactly what the rule is and I don't find it very useful.  More useful would be shorter compound words.  So, when we have a big catalog of compounds, we could take inventory, see which roots are most commonly used, and shorten them to single syllables that play nicely with their neighbors.  This should have a noticeable impact on the fluency of the language.

(**verpo** was the first candidate examined, and it was retired outright rather than
shortened: every sense it carried was already inside **tika** 'say', so the root was
folded in and the six compounds reglossed -- *what-say* 'question', *say-way*
'language', *write-say* 'text', and so on.  See "Root Reductions" below.)

I did a quick search for roots that were used in a large number of compounds (at least 7 of our current set), are multisyllable, have a high frequency of use overall, and no good reason to stay what they are.  Here are the best candidates:

aku, ire, omo, orten, sore, komi, roko, vite, riso, arpo, karo, nino, ruti, peste, voka, kase, vento, propa, panto, kosa, konten, verya, ruper, uter, rapo, pena

So, we'd need to examine each of these, particularly in terms of the compounds they participate in, and look for a shorter/easier word that maybe still has some mnemonic value.  (**verpo** was on this list, but it got removed and merged into **tika**.)



## Root Reductions

(Currently all resolved.)

**Done: `word` folded into `say` (2026-08-13).**  **verpo** covered "word, language,
speech, message", all of which **tika** already reaches -- **tikakosa** (*say-thing*)
'story' was treating **tika** as a noun head before the merge, so nothing new was
asked of the root.  The six compounds recoined without collision: *what-say*
'question', *say-way* 'language', *write-say* 'text', *measure-say* 'numeral',
*key-say* 'password', *say-fight* 'argue'.  Two consequences worth remembering:

- **kertika** now carries "question; ask; inquire" and **voritika** was narrowed to
  "request; ask for", splitting the two senses English writes as one word (compare
  *fragen*/*bitten*, *preguntar*/*pedir*, 問う/頼む).
- The merged root took **言** and gave up 云.  言 is 'word' and 'speak' in both Chinese
  and Japanese, where 云 reads as 'cloud' outside classical Chinese, so the character
  now covers what the root covers -- at a cost of 3 strokes on the most-used root in
  the set.  A pleasant side effect: the Han text of every affected compound is
  unchanged (何言 is still 何言), since 言 simply moved to the surviving root.

The cost is polysemy: **tika** now holds six senses under the gloss `say`, which is
the strongest case yet for the secondary gloss proposed above -- a secondary gloss of
`word` would carry all six compounds on its own.

## Root Additions

The other half of the same question: if reductions freed up space, what would be
worth spending it on?  What follows are concepts the current 188 roots do not touch,
where the workaround is either long, unguessable, or missing entirely.

A concept belongs here only if *both* tests fail: no root covers it, and no short
compound reaches it.  'Health' does not qualify, for instance -- **sana** covers
"heal, cure, medicine, health, repair", so *sana-komi* 'health food' and
*sana-korpo-rapo* 'exercise' are already available.  The gloss `heal` simply hides
what the root holds, which is an argument for the secondary gloss above, not for a
new root.  The same goes for 'love' (inside **kusta**) and 'permission' (inside
**reke**).


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
| **clear** | ??? | useful for description, as well as for "is that clear?", and weather; not-clear could also mean cloudy |

### Whole domains with no coverage

Stepping back from individual words, four areas of the set are thin in a way that
single additions may not fix:

- **Body detail.**  The senses are covered -- *see-part* 'eye', *hear-part* 'ear',
  *air-taste* 'smell' -- but the substance of the body is not: no face, blood, skin,
  bone, tooth, or hair.  Medical emergencies and doctor visits are exactly the
  situation where a traveler cannot afford to paraphrase, and *see-part* does not
  help you say where it hurts.
- **Manipulation.**  We have **toma**, **tonar**, **tene**, **seta**, and then
  nothing: no carry, push, pull, throw, drop, catch, turn (as an action), open-with-
  force.  The set can describe transfers of possession but not much physical handling.


### Metric sub-unit prefixes

Metric units are handled by loan words (**metoru**, **ritoru**, **kuramu** in
`names.tsv`), and the *kilo-* prefix needs nothing new: **kiru** 'thousand' already
gives **tets kiru metoru** '3 km', whose literal reading "three thousand meters" is
arithmetically exact.  Mandarin builds 千米 the same way.

What is not covered is the other direction.  Decimals reach it in writing -- 3 mm is
**0.003 metoru** -- but nobody says that out loud, and small measurements are common
in shops and repairs.  Mandarin's answer is native fraction words (厘 'hundredth',
毫 'thousandth') rather than borrowed *centi-* and *milli-*, which suggests that if
this gap bites, the fix is one Pikotika fraction root usable everywhere, not two
borrowed prefixes usable only on units.

**Why it is not in the language:** we have no observed need yet.  Adding *centi* and
*milli* as loans would be cheap; adding a general fraction root would be better and
is a bigger decision.  Waiting costs nothing, and the decimal workaround is correct
in the meantime -- it is only clumsy in speech.
