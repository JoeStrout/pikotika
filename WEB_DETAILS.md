# Website implementation notes

How pikotika.org is built, and the decisions a future session would otherwise
re-litigate. `WEBSITE_DESIGN.md` is the design brief — what the site should be;
this is what it *is*, and where the code lives. Where they disagree, this file
is what shipped, and the disagreement is called out below.

## Build model

No framework, no bundler, no npm. `build.py` renders hand-written fragments
through one template into a directory per section, so URLs are `/grammar/`
rather than `/grammar.html`.

| path | what |
|---|---|
| `web/pages/*.html` | body fragments, one per section; plain prose |
| `web/templates/base.html` | the only template; `{{field}}` placeholders |
| `web/{css,js,images,fonts,data}/` | copied to the output as-is |
| `build.py` | the whole build; `PAGES` is the nav, titles, and routing |
| `site/` | output — **gitignored, never edited, rebuilt from scratch** |

`python3 build.py --serve` builds and serves on :8000. CSS and JS are linked
with a `?v=<content hash>` (`asset_version`), because the dev server sends no
`Cache-Control` and a browser will otherwise run yesterday's JavaScript in a
brand-new tab — which looks exactly like a code change having no effect.
(Observed in Chrome; the fix is engine-independent.)

`build.py` fails rather than shipping something wrong: an unfilled template
field, a Han character with no glyph, or a Pikotika form that is not real.

## The Han font

**One font, not two** (decided 2026-08-18; supersedes `WEBSITE_DESIGN.md`
§"The Han subset font", which planned two `@font-face` rules with
`unicode-range` for the particles).

The premise there was that a CJK face would not have the particle symbols. It
nearly does: **Noto Sans CJK JP covers every character in the `han` column plus
`>` and ⇒, and misses only ⊢ (U+22A2)**. So `gen_han_font.py` subsets the face,
converts CFF outlines to `glyf`, and draws that one glyph — measuring the arm,
math axis and horizontal extent off the face's own U+2212, and the height and
stem ratio off its U+22A5. Nothing is hand-tuned, so Bold gets a heavier
turnstile automatically. A separate face could not match this well, which was
the design doc's actual worry.

- `gen_han_font.py` → `web/fonts/pikotika-han-{regular,bold}.woff2`, ~23 KB each.
- **The build is hermetic and reproducible.** It reads `vendor/`, not an
  installed font. What is vendored is not the 110 MB `NotoSansCJK.ttc` — that
  would grow a 3.6 MB repository thirtyfold for a build-time asset — but a CFF
  cut of it per weight (~45 KB) holding the characters Pikotika uses plus
  U+2212 and U+22A5, which the turnstile is measured against. Outlines are
  untouched, and building from `vendor/` is verified byte-identical to building
  from the full face.
- Reproducibility needed `recalcTimestamp = False` (`stable()`): fontTools
  stamps `head.modified` with the current time on save, which otherwise makes
  every rebuild a fresh binary in git.
- **Adding a root with a new Han character** is the one thing `vendor/` cannot
  cover. `gen_han_font.py` falls back to the full face, says so, and tells you
  to re-cut: `python3 gen_han_font.py --vendor`, then commit `vendor/`. That is
  the only time `NotoSansCJK.ttc` is needed.
- The subset also carries `0 1`, space, and `. , ; : ? !` — the `han` column has
  only 2–9 as root characters (一 is the *root* one; `30` is digits). **Latin
  names are deliberately excluded**: they stay in Latin inside Han text, and
  falling through to the body face is the intended contrast.
- `build.py:check_fonts` re-verifies coverage of every character on every build.
- **`/specimen/`** (`gen_specimen.py`) is a proof sheet of every glyph in both
  weights, generated from `roots.tsv`. Built but kept out of the nav via
  `build.py:UNLISTED`. Open it in an untried browser and look — a tofu box is
  obvious. Do not add an automated per-glyph check to it: a browser whose CJK
  fallback is the face we subset from renders a missing glyph identically to a
  present one, so it cannot be established in the page. Coverage is asserted at
  build time against the font file instead, where it can be.

Two traps, both already sprung: the subsetter leaves ~37 orphan Ideographic
Variation Sequence glyphs behind (`prune()` drops them, 18% of the file), and
the font keeps `sfntVersion = OTTO` after the CFF→glyf swap, which FreeType and
browsers both reject (fixed in `to_truetype`).

## Word chips

Every Pikotika word on the site is tappable. **The wrapping is done by
JavaScript at page load; the checking is done by the build** (decided
2026-08-18 — `WEBSITE_DESIGN.md` did not say which).

The reasoning: splitting words needs no lexicon (Pikotika is whitespace
delimited), so a runtime scan costs nothing and keeps the pages as readable
prose instead of build-generated `<button>` soup. What that would lose is
verification — a typo'd form becoming a chip that opens nothing — so the build
keeps that half. Chips are pure enhancement; without JavaScript the sentence is
still there and still reads.

- **Authors write `<span class="pk">Panyu ri kerroko?</span>`** and nothing else.
  `data-check="off"` opts a span out of both the check and the chipping — for a
  `.pk` that is not running Pikotika, such as the `S RI V A O` schema. Gloss
  notation is `.gloss`, not `.pk`.
- `build.py:PkCollector` / `check_forms` parse every `.pk` string through
  `pikotika.parse_latin` and fail the build on an unknown word.
- `gen_lexicon.py` → `web/data/lexicon.json`: every root, compound, name and
  loan, plus any form found only in page prose (the checker hands those over).
  ~613 entries, 124 KB raw / 22 KB gzipped, **fetched lazily on first tap**.
  Each entry carries form, kind, gloss, English, Han, level, and — for
  compounds — the parsed roots. The parse is precomputed on purpose: `segment()`
  has real linking-`e` and name-matching rules, and a JavaScript port would be a
  second implementation to keep honest.
- **The popover's third line is the parse for a compound and the mnemonic for a
  root** — never both, since a root has no parse and a compound has no mnemonic
  of its own. The parse reads **piko** *(small)* + **tempo** *(time)*, and each
  root in it is itself tappable: the box refills in place, keeping the original
  chip as its anchor and as the word marked open, so stepping into a root does
  not move the box out from under the reader. The gloss shown is the *primary*
  gloss of each root (`gloss_roots` normalizes), so `all-choose` displays as
  *every* + *choose*.
- **`roots.tsv` has both a `mnemonic` and an `etymology` column.** Only the
  mnemonic ships in `lexicon.json`: a chip tapped mid-sentence wants one catchy
  line, and the etymology belongs on the full entry page. Mnemonics mark the
  echoing letters with `*asterisks*`, which `appendEmphasis()` turns into `<em>`
  nodes — built as DOM, not handed to `innerHTML`.
- **A mnemonic must not begin with a `"`.** `private/detidy.py` reads a leading
  quote as a Numbers cell wrapper and strips it, so `"corpse"` silently becomes
  `corpse`. Use italics for a one-word mnemonic instead. Quotes inside a
  mnemonic are safe.
- `web/js/site.js`, "word chips" section: the scanner, and the popover.
  `window.pikotika.scanChips(scope)` is exposed for pages that build markup
  after load (Vocab results, the Tools converter).

Two implementation facts worth not rediscovering:

- **Every chip is underlined individually**, including on an all-Pikotika line
  where that means every word carries dots (decided 2026-08-18).
  `WEBSITE_DESIGN.md` proposed setting the underline once at block level there
  instead; built, it read as one long link across the sentence rather than as a
  row of separately tappable words. Dots per word is also what the Duolingo
  convention the doc cites actually looks like.
- Worth knowing if that is ever revisited: **`text-decoration` does not paint
  through a `<button>` child.** A block-level underline has to be a
  `border-bottom`; as `text-decoration` on the container it silently renders
  nothing.
- **Chips are `<span role="button" tabindex="0">`, not `<button>`** — because a
  sentence made of real buttons cannot be drag-selected or copied. Mousedown on
  a form control begins activation rather than a selection. This is cross-engine
  — observed in Firefox, diagnosed in Chrome — and it is *not* a `user-select`
  question: a `<button>` and a `<span>` both compute to `user-select: auto`, so
  no CSS fixes it. The span is verified selectable by hand in Firefox. The cost is wiring up the keyboard, which the Enter/Space handler in
  site.js does. A click that ends a drag-selection is also ignored, so selecting
  text does not open a popover.
- A sentence split into eight controls is announced as eight controls, so
  `chipify` puts the whole sentence on the container as `aria-label`.

## Audio

Generated at build time by Kokoro running locally; the site does no
text-to-speech at runtime. `GAME_DESIGN.md` §Audio is the design; this is the
implementation.

**Environment.** Kokoro does not work in the base Python. Everything audio runs
in the `pikotika` micromamba environment (python 3.12, numpy, onnxruntime,
ffmpeg 9, plus `kokoro-onnx` and `sounddevice` from pip):

    micromamba run -n pikotika python gen_audio.py

It carries its own ffmpeg, so the encode does not depend on whatever is on
`PATH` — the base one is 4.2.2.

| file | what |
|---|---|
| `phonemes.py` | Pikotika → IPA. The one description of how the language sounds. |
| `gen_audio.py` | renders clips, builds the sprites |
| `private/audio-cache/` | WAVs keyed by voice and utterance; gitignored |
| `web/audio/words/*.m4a` + `words.json` | one file per word |
| `web/audio/sentences/*.m4a` + `sentences.json` | one file per sentence |

`phonemes.py` was lifted out of the `private/speak.py` prototype, which now
imports it. Do not let a second copy of the phoneme tables come back — Kokoro
drops symbols outside its vocabulary *silently*, so a divergence between the
tool and the build would surface as a missing sound and no error.
`check_symbols()` guards the vocabulary itself.

**Voices.** `af_sky` and `bm_george`, chosen by ear over the full set
(`af_nicole` is unusable). Word tiles alternate between them so the learner is
not tuned to one speaker; dialogs and stories will pick by character instead,
which is why `assign_voices()` is a function rather than a constant.

The split is **exact, not hashed**. Hash parity is only even on average and came
out 54/46 over 613 words. Instead the keys are ordered by hash — arbitrary but
fixed, so neither voice collects all the short words — and cut at the median.
Still stable as the lexicon grows: measured, adding five coinages moves 0–2
words to the other voice, against the ~half a re-hash would reassign.

**Files, not sprites, for everything the site plays.** `GAME_DESIGN.md`
specifies sprites throughout; that is right for a lesson, which plays many clips
from a known set and would otherwise make forty fetches. It is wrong for
anything played one at a time: measured, fetching and decoding the 613-word
sprite put **6 to 14 seconds** in front of the first tap, against **7–44 ms**
for a single file. `build_sprite()` is kept, unused, for the course.

Sentences come from `corpus.tsv` plus `build.page_sentences()` — every
multi-word `.pk` string on the site, since an example on a page is not
necessarily a corpus line. `build.py` keeps its `fontTools` import inside
`check_fonts` so that `gen_audio` can import it from the `pikotika`
environment, which has Kokoro but not fontTools.

**Sentence play buttons** are added by `addSentencePlayers()` to any `.example`
line of two or more words, keyed on the line's exact text. The button is a
sibling of the `.pk` span, not a child: inside, its glyph would be swept into
the sentence's `aria-label` and into anything copied.

Sprite mechanics, when used: a JSON map of `{form: [offset, duration, voice]}`
and `start(0, offset, duration)`. Clips are separated by `PAD_SECONDS` of
silence, because AAC carries encoder priming and padding that a decoder does not
always return exactly, and without a gap a slice bleeds into its neighbor.
Verified: slices correlate 0.999+ with their source clips and show no priming
drift. Sentences are generated whole, never stitched from word clips — each word
has its own penultimate stress and final fall, so a concatenation is a robotic
list.

**Trimming.** Kokoro leaves silence at both ends — measured, 79 ms before the
word and 139 ms after. The trailing silence is only weight; the leading silence
is a lag on every tap. `trim()` strips both to a 20 ms margin, at sprite/file
build time rather than when caching, so re-tuning costs a re-encode instead of
re-rendering a thousand clips.

**Playback** is Web Audio, not `<audio>` (`site.js`, "audio" section). Clips are
fetched on first press and kept once decoded; that press is also the user
gesture that permits resuming the `AudioContext`. Lessons that autoplay will
need the unlock moved to their start button, and a header audio toggle; neither
exists yet.

## Not built yet

The header audio toggle, and slow ("turtle") variants — Kokoro takes a speed
parameter, so those are a second generation pass rather than `playbackRate`,
which pitch-shifts. Vocab search, the grammar and topic pages, and the Tools
converter are all still placeholders.
