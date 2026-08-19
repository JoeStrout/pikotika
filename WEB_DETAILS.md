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
| `docs/` | output — **never edited by hand, rebuilt from scratch, and committed** |

**Deploying is `python3 build.py` and a push** (decided 2026-08-19). GitHub
Pages publishes from a branch, and a branch source may be the repository root or
`docs/` and nothing else — which is why the output directory is named `docs/`
rather than `site/`, and why it is committed rather than ignored. `web/CNAME`
holds the custom domain and `web/.nojekyll` turns off the Jekyll pass a
branch-published site otherwise gets; `STATIC_FILES` copies both to the output
root, since `STATIC_DIRS` only handles directories.

The cost of this choice, taken knowingly: **nothing checks that you rebuilt.**
The site is generated from `roots.tsv`, `compounds.tsv` and `corpus.tsv`, so a
commit that edits a table without a rebuild silently publishes the old lexicon.
A GitHub Actions workflow building on push would make that impossible, and is
the alternative if the staleness ever bites.

`python3 build.py --serve` builds and serves on :8000. CSS and JS are linked
with a `?v=<content hash>` (`asset_version`), because the dev server sends no
`Cache-Control` and a browser will otherwise run yesterday's JavaScript in a
brand-new tab — which looks exactly like a code change having no effect.
(Observed in Chrome; the fix is engine-independent.)

**The data files carry a version too** (`data_version`, added 2026-08-19).
`lexicon.json`, `audio/words.json` and `audio/sentences.json` are rebuilt in
place under the same names, so a browser that cached yesterday's copy keeps
using it -- and the symptom is not an error but a word or a sentence that
silently has no audio, because the index it was added to is the stale one. The
version is a hash of all three, injected as `data-data-version` on the
`site.js` tag and read back by `DATA_V` in site.js from
`document.currentScript`. The clips and the pages do not need it: a clip has a
content hash in its filename, and an HTML page is not cached that way.

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

## Sentence schemas

`.schema` is a one-row table diagramming a sentence frame — one cell per
position, particles written as themselves, open positions dashed. Built for the
home page's `S RI V A O`, and meant to be reused wherever a construction is
introduced.

    <table class="schema"><tr>
    <td class="slot">subject</td>
    <td><span class="pk">ri</span></td>
    ...

The author marks only the placeholders: a plain `<td>` is a literal word. A
`<th>` row labels the columns, and a `tr.schema-eg` row sets a gloss or
translation under the frame in the same columns.

**Particle cells are deliberately not filled with the accent color.** They hold
live word chips, and an open chip marks itself by turning accent — which it
cannot do on an accent ground. They get `--bg-tint` and a solid border instead,
against the placeholders' dashed one. Checked open, and in both themes.

## Vocab (`/vocab/`)

One page, client-side, over `lexicon.json` — no per-entry pages (decided
2026-08-19; `WEBSITE_DESIGN.md` writes the permalink as `/vocab/riso`, and what
shipped is `/vocab/#riso`). Generating ~613 directories would have given real
paths, but at the cost of a second renderer for a full entry in Python beside
the one in JavaScript. One implementation, hash permalinks.

- **The hash is the search box** (decided 2026-08-19, after two worse tries).
  `/vocab/#riso` puts *riso* in the box and searches for it; typing a search
  writes itself back to the hash. A link and a search can therefore never
  describe two different pages. `fromUrl()` is the single path used on load, on
  `hashchange`, and after a related word is tapped.
  - The first attempt read the hash *only* as an entry to expand, so arriving
    at `/vocab/#komivakeomo` while "spicy" was still typed changed the URL and
    nothing else — the entry was filtered out of the list.
  - The second cleared the search instead and scrolled the full 613-row browse
    list to the word, which is more confusing than just searching for it.
- **A hash that names a form exactly also opens that entry**, which is what
  makes a permalink land *on* the word rather than beside it. Typing does not:
  `open` is cleared on input, so an entry does not pop open under the cursor
  because what you have typed so far happens to spell a word.
- **Every related word in an open entry is an ordinary word chip** — the roots
  of a compound's parse, and the compounds under "Used in" — opening the
  standard popover rather than navigating to that entry (decided 2026-08-19;
  they navigated at first). By the time a reader is on this page, a dotted
  underline has meant "tap for the tile" everywhere else on the site, and one
  that moves the page instead is a surprise; the tile's own "Full entry" link
  is still the way through. `wordChip()` emits a bare `.pk` span and lets the
  `scanChips(box)` that already runs over a freshly opened detail box build the
  chip, so there is one chip implementation, not two. This retired
  `relatedChip`, the `go()` that searched for the tapped word, and the
  `.vocab-rel` CSS that was hand-copying the chip's dotted underline.
- **Expanding a row does not rewrite the hash.** Opening one result of a search
  is not a different search; the entry's own Permalink is the link to it opened.
- Nothing pushes history — a reader stepping through six compounds should not
  have to press Back six times — so `setHash()` uses `replaceState`, which also
  does not fire `hashchange`, so writing the hash cannot loop back into reading
  it. A kind or category chip can still hide the linked word, which is what
  `reveal()` clears.
- **`history.scrollRestoration = 'manual'`** when arriving on a hash. The row
  does not exist until the fetch lands, by which time the browser has already
  restored the scroll position of a page that was still empty, i.e. the top.
  The scroll aligns the row to the top, not the center — an open entry can be
  taller than the viewport — offset by the measured height of the two sticky
  bars.
- **The kind row and the category row are independent** (decided 2026-08-19).
  Categories used to be a roots-only column, so the page tried to afford the
  category chips only under All and Roots: they were dead under Compounds, and
  picking a category under All and then switching to Compounds left a chip
  highlighted that was no longer applied. Rather than police that, the data
  grew up — `compounds.tsv` and `names.tsv` now carry their own `categories`
  column (see `CLAUDE.md`), every entry in `lexicon.json` ships a `cats` list,
  and neither row clears or disables the other.
- **A root is filed under its category heading; a compound is not.** With a
  category chosen, the browse list shows that category's roots under its
  heading and then the matching compounds, names and loans under their own kind
  headings. Filing a compound under each of its categories would list the same
  word two or three times in one browse.
- **The empty state is the lexicon browsed by category**, roots under their
  `category` headings in `roots.tsv` order (editorial, so not sorted), then
  Compounds, Names and Loans under their own. A dictionary you can read down
  beats an empty box on arrival.
- **English matches only at a word boundary; the Latin form matches anywhere.**
  *price* contains *rice*, and a search for rice that turns up **moni** is worse
  than no result — but compounds are written solid, so "riso" has to find
  **yororiso** by plain substring. `score()` holds the ranking. The page's own
  example is *medicine* → **sana**, which is genuinely a `covers`-only hit;
  *rice* is not, being **riso**'s `gloss2`.
- **The sentence list opens at 8.** **ri** is in 279 corpus sentences and
  **eko** in 133; printed whole, the commonest words — the ones a beginner opens
  first — become the longest pages on the site. Compounds are not capped: the
  worst case is **non** at 27, and each is one word.
- Sentences are rendered as `.example` blocks, the same markup the rest of the
  site uses, so chipping and the play button come for free. `chipify` works on a
  detached node but `addSentencePlayers` queries the document, so it runs after
  `render()` has appended the list, not inside the row builder.
- **The controls bar measures the header** rather than hard-coding its height in
  two media queries that would then have to be kept in step (the mobile nav is
  two rows, the desktop one).

`gen_lexicon.py` carries what the detail view needs: the joined sense range
(`root_covers`, since the `covers` column holds only what the glosses do not
already name), `cat`, `strokes`
and `gloss2` on roots, `in` (the compounds built around this word) and `ex`
(corpus sentence indices) on both roots and compounds. **Sentences ship once in
a top-level array and are referred to by index** — written into each entry, the
common roots would carry the same string dozens of times. Both indexes are built
by walking every contiguous run of each word's roots (`subruns`), which is the
same question `pikotika.contains_run` answers, asked once instead of per word.
The file is 196 KB raw, 46 KB gzipped.

## Topics (`/topics/`)

An index of cards plus one page per topic at `/topics/<slug>/`. The seventeen
slugs are `WEBSITE_DESIGN.md`'s, and they are also `corpus.tsv`'s `topic`
values, so a page and the sentences that support it are named the same thing.

**Navigation between topics is hub and spoke** (decided 2026-08-19). Every
topic page carries a "← Back to Topics" link at the top and the bottom, added
by `topic_pages()` rather than written into each fragment, and there is nothing
else. The alternative considered was a strip of all seventeen topics under the
header of every page, which puts the whole section one tap away from anywhere;
it was passed over as a row of chips competing with the content on a page whose
own content is the point, and because the index — cards, icons, three groups —
is a better place to choose from than a chip row. Worth revisiting if readers
turn out to move sideways a lot.

- `build.py:TOPIC_GROUPS` is the whole table: three groups, and per topic a
  slug, its Pikotika name, a label, a Han glyph, and one line of what you can
  say. The label and the line are also the page's `<title>` and its meta/`og:`
  description.
- **Every card carries the topic's Pikotika name**, so browsing the index
  teaches seventeen words. Fourteen were already in the lexicon; the three that
  were not are coined in `compounds.tsv` — **oratika** *hour-say* 'clock time',
  **tempokarta** *time-page* 'calendar', and **ventomoto** *air-manner*
  'weather'. Each fills a real gap rather than existing only as a label.
- **The name is checked but not chipped**, via `data-chip="off"` — the other
  half of `data-check="off"`. The card is a link, and a word chip inside it
  would be a control nested in a control, where one tap means two things. The
  build still parses the form, so a typo'd name fails the build.
- **A topic is written when `web/pages/topics/<slug>.html` exists.** There is no
  second list to keep in step: the page appears, its card becomes a link, and
  until then the card renders inert and marked *not written yet*. An index of
  seventeen cards where four work is honest; seventeen links where thirteen 404
  is not, and thirteen empty pages are worse.
- **Icons are art if it has been drawn and the Han character if it has not.**
  `topic_icon()` looks for `web/images/topics/<slug>.svg`, then `.png`; drop the
  file in and rebuild, and nothing here needs editing. They go in
  `web/images/topics/`, not beside the fragment in `web/pages/topics/` — only
  `STATIC_DIRS` is copied to the output, so an image next to the prose would
  never reach the site. The Han fallback is a
  real placeholder, not a gap — it is the character of a root at the middle of
  the topic.
- `authored_pages()` is now the one definition of the reader-facing pages, used
  by `check_forms`, by `page_sentences` (so topic-page examples get audio like
  any other), and by the build. Topic pages could not be rendered without being
  checked and spoken even if someone wanted them to be.
- The index gets `main_class="wide"`; the measure column is for prose, and a
  card grid in it is two columns at most.
- `nav_html` marks a section by prefix, so Topics stays lit on `/topics/colors/`.

**The colors page is the first one written**, and it is the shape the others
should follow: the six roots as swatches, the seven built colors as swatches
showing their parse, then the grammar in one paragraph, then corpus sentences
as ordinary `.example` blocks so chips and the play button come for free. The
swatch list is `.swatches`; each `<li>` carries the color as `--sw`, and the
band has a border so a near-background swatch is still an object in both
themes.

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

**`build.py:check_audio` warns when the clips no longer match the site.**
`build.audio_sentences()` is the one definition of what needs a clip -- corpus
lines, then anything a page says -- and `gen_audio.sentence_items` renders
exactly that list, so the two cannot drift. The build compares it against
`web/audio/sentences.json` and names what is missing and what is now unused.

It warns rather than fails: generating audio needs Kokoro and the `pikotika`
environment, and a hard failure would leave anyone without that environment
unable to build the site at all. It has to be loud because the failure is
invisible -- a sentence with no clip still gets a play button, which disables
itself when tapped.

**Editing a sentence is the case that bites**, not adding one. Clips are keyed
by exact text, so a corrected line leaves its old clip behind and arrives with
none; the check found one already shipped that way. `gen_audio` does not delete
the orphan, so a clip named in the warning as no longer used has to be removed
by hand.

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
