This file collects issues/gaps we have discovered while working with the language, and not yet addressed.

Issues will be removed as they are resolved.

## Missing Words/Expressions

- **Body parts**.  We have a half-dozen, but we're still missing some important ones.
- **Fruits**.  We can describe them, and in the real world we could point, but it'd be nice if we could clearly say 'apple' (for example).
- **Measurement units.** We need some way to say (and write) at least cm, m, km, kg, l.
- **Seasons.**

## Missing Grammar

- **No 'so X that Y'** ("I was so late that I missed the train").  No word for 'so' would fix
  it, since the difficulty is attaching the result clause.  For now it inverts with **rason**
  ('I missed the train, because I was very late') or breaks in two with **tisrason** ('I was
  very late.  Therefore...'), losing the emphasis but not the content.  When this does get
  designed, **mesur** 'measure, amount, degree, extent' is the likely pivot: it is exactly
  Japanese *hodo* ('tired to the extent that I could not walk') and does the same job as
  Chinese 得.
- **Embedded questions clash with the in-situ question rule.**  A question word stays in its
  slot, so a **ker** inside a complement clause is indistinguishable from one asking the
  matrix question -- and if the matrix is itself a yes/no question, the sentence carries two
  unrelated **ker**s: **Tuo ri sape a rinekaro ri eksire in kerora, ker?** ('Do you know when
  the train leaves?')  We have no rule saying what an in-situ **ker** scopes over.
- We haven't entirely decided where the aspect marker (apa/vin/sista) goes in all cases, particularly whether it goes right after the verb (if there is one) or at the end of the sentence (after the object).  I'm leaning towards the former, even if it complicates the rule a little.

## Tooling

- **Compound headwords shadow root `covers` words, and that is silently shaping the
  lexicon.**  `pikotika.py` indexes each compound's English headword on its own -- "beer
  (any grain alcohol)" also answers to plain *beer* -- and it resolves compounds before it
  looks at any root's `covers` list.  So whenever an English word sits in both places, the
  compound wins and the root becomes unreachable by that word.

  Two entries have already been steered around this rather than through it.  *wait* was
  first recorded as the compound `wait (a while)`, whose bare headword *wait* then shadowed
  **sista**, which covers waiting directly; it was renamed to `wait a while` purely to stop
  the tool claiming the word.  Then *seat* was deliberately kept out of **seta**'s `covers`
  and left only as the compound *sit-place*, on the same reasoning.

  Both decisions were made for the tool's benefit, not the learner's.  The right question
  is which form a learner should reach first -- and sometimes that really is the root
  (**sista** for 'wait'), while sometimes it is the compound (**setaroko** for a seat you
  can point at).  The tool should be able to hold both and say so, presumably by reporting
  every hit rather than the first one, with some indication of which is the more basic.
  Until it can, revisit these case by case and record what is best for learners; do not let
  the resolution order decide the lexicon.
