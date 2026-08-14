# Pikotika

A constructed international auxiliary language of about 200 roots, built for real
travel and social conversation. The name is *piko-tika* — **small-talk**.

Pikotika is designed to be learnable in a weekend and forgiving of accents: ten
consonants, five vowels, no irregular verbs, and a rigid word order. Every root
has a Latin spelling and a single Han character, so it can be written either way.

**New here? Start with [QUICK_START.md](QUICK_START.md).**
For the full treatment — pronunciation, writing systems, numbers, colors, proper
nouns, and grammar — see [DETAILS.md](DETAILS.md).

## What's in this repository

| file | what it is |
|---|---|
| `roots.tsv` | the root lexicon: 193 roots + 3 particles, with forms and characters |
| `compounds.tsv` | the standing compound lexicon |
| `names.tsv` | proper nouns adapted to the phonology |
| `pikotika.py` | converts between English, gloss, Latin, and Han |
| `check_form.py` | screens a proposed root form, or audits the forms already in use |

```
$ python3 pikotika.py "water-grain"
  gloss: water-grain
  Latin: akuriso
  Han:   水米
  EN:    porridge; congee
```

Pikotika is a work in progress; the documentation is still being filled in.

## License

[CC BY 4.0](LICENSE) — use it, teach it, build on it; just credit the source.
