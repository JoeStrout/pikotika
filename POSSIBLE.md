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
