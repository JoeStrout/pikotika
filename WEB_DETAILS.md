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
`document.currentScript`. An HTML page does not need it, not being cached that
way.

**The clips are not covered, and the reason first given here was wrong**
(corrected 2026-08-20). It said a clip carries a content hash in its filename.
It does not: `gen_audio.cache_path` hashes the *utterance text*, so the name is
stable across any change to the audio for that text. Re-render at a different
voice or a different speed and `ora-1d7d2b95.m4a` keeps its URL and changes its
bytes -- which is precisely what a cache is entitled to ignore. Anyone holding
the old file, browser or CDN, goes on playing the old voice.

Left alone for now, deliberately: a voice swap is rare, Pages caches assets for
about ten minutes, and the clips are fetched on first press rather than
precached. But **if a service worker ever precaches audio, this becomes a real
staleness bug**, and the fix is to fold the audio into a version query the way
the data files are, or to hash the encoded bytes into the name and let
`check_audio` clean up the orphans that would then exist.

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
- **The compressed bytes also depend on the brotli version**, which nothing
  pins (found 2026-08-20). WOFF2 is brotli-compressed, so the same font
  compresses to a different file under a different compressor: moving the
  build from the base environment's brotli 1.0.9 to `pikotika`'s 1.2.0 grew
  the regular face 23,564 → 23,608 bytes. **The font was unchanged** — same
  table set, same glyph order, and the decompressed sfnt byte-for-byte equal;
  only the packing differed. Regenerated under 1.2.0 and committed on that
  date, and two consecutive runs there are byte-identical, so the anti-churn
  property `stable()` exists for still holds. What "reproducible" means here
  is therefore *given the same fontTools and brotli* — check those two before
  concluding that a woff2 diff means the font changed. The test that settles
  it is comparing the decompressed sfnt, not the file.
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

**`DETAILS.md` is emptied as pages are written**, as `WEBSITE_DESIGN.md` asks:
its Numbers, Colors, Proper Nouns and Loan Words, and Telling Time sections
were deleted once `/topics/numbers/`, `/topics/colors/`, `/topics/names/` and
`/topics/time/` covered them, and a
comment at the head of the file records where each one went. The two
cross-references from sections that stayed now link to the pages, and the
comments in `pikotika.py`, `phonemes.py`, `numbers.js` and `adapt.js` that used
to cite a `DETAILS.md` section cite the page instead. Nothing reads
`DETAILS.md` at build time, so this cannot break a build -- which is exactly
why a stale citation in it would go unnoticed.

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

**Five topic pages are written so far**: colors, names, numbers, seasons and
time. Colors is the shape the plain ones should follow, and numbers the shape
of one with a tool in it -- the tool first, under a one-paragraph lede, then
the reference that explains what the tool just did. Time follows numbers, and
seasons follows colors.

Colors: the six roots as swatches, the seven built colors as swatches
showing their parse, then the grammar in one paragraph, then corpus sentences
as ordinary `.example` blocks so chips and the play button come for free. The
swatch list is `.swatches`; each `<li>` carries the color as `--sw`, and the
band has a border so a near-background swatch is still an object in both
themes.

Numbers: the reader, then `.digits` -- a grid of numeral, word and character,
with a fixed-width numeral column so the words line up and the list reads as a
table rather than as prose. `.reader` is the name adapter's box with three
lines reserved under the input, and `.aside` is a bordered note for the sort of
aside that is only for some readers (兆 is a million here, not a trillion).

Time: the same box with three `<select>` fields and a clock face in it
(`.clock-grid`, `.clock-face`), then the colon rule, the parts of the day as a
`.digits-words` list -- the digit list with a word where the numeral goes --
and the rest as ordinary tables and examples. See The clock below.

Seasons: `.swatches` with a picture where the color band goes (`.seasons`), the
four seasons and then the wet/dry pair, then one table of `in` / `tis` /
`yer`-`tar` and two corpus sentences. The art is 72×72 PNGs in `web/images/`,
drawn for a light ground, so `.seasons img` puts `--bg-tint` behind them rather
than needing a second set of files for dark mode. It is the shortest page in
the section on purpose: the whole topic is six compounds built from roots the
reader already has.

## The number reader (`web/js/numbers.js`)

The interactive half of `/topics/numbers/`: type a number, see how it is said,
hear it. Unlike the name adapter, this one is **a port, not a first
implementation** -- `pikotika.counting_words` and `decimal_words` already say
how a numeral is read -- so it gets the conformance test `WEBSITE_DESIGN.md`
asks for.

- `build.py:check_numbers` runs both implementations over
  `build.number_checks()` (170 numbers: every integer to 120, where the special
  cases live, then one per decade, plus decimals, fractions, percentages and
  ordinals) and fails the build on any disagreement in Latin, gloss or Han.
  **The comparison goes through the reader's `spelled` form** -- the reading
  written out in words. Nobody writes that (a number is written in digits,
  `3/4` with a slash), but `parse_latin` can read it and `3/4` it cannot, so it
  is the only bridge between a JavaScript reading and a Python one.
- **The module takes no position on how a number is written**, only on how it
  is said. That was not true at first: it returned a `written` form and the
  page printed it, from when `DETAILS.md` had fractions written **3 in 4**.
- **Most cases are now also compared as typed.** `pikotika.py` learned `/` and
  `%` (see below), so `check_numbers` parses the raw case as well and checks
  that both implementations read it the same. An ordinal is the exception:
  `7th` is English, and only its reading is Pikotika.
- **Han is checked too**, and it is where the reading gets interesting: a free
  `wun` renders as `1` but a bound one as 一, so **21st** is `2 十 一序`.
- `build.number_forms()` is the reader's whole vocabulary -- the ten digits, the
  four powers of ten, and `parte` / `in` / `inkaton` / `orten` -- derived from
  `pikotika.DIGITS` rather than typed out. `check_numbers` asserts that
  `numbers.js:vocabulary()` agrees with it, because a word the reader can say
  that is not in that list would simply be **silent**, and nothing else would
  notice.
- Integers go through `BigInt`, so the port matches Python's unbounded ints
  instead of going fuzzy at 2^53. Input is capped at 24 digits: nothing breaks
  past that (a million millions is `miron miron`), but the reading is no longer
  something anyone would say.
- **Negatives are refused with a note**, not adapted. There is no settled
  Pikotika word for a minus sign, and the reader is not the place to invent
  one.
- A denominator of 100 is read as a percentage: `50/100` and `50%` are the same
  answer.

### Its audio is the one thing on the site that is stitched

`GAME_DESIGN.md` and the Audio section below both say sentences are generated
whole, never concatenated from word clips, because each word carries its own
stress and final fall. That still holds -- but a reading is **unbounded**.
There is no clip for `12345` and there never can be, so the reader chains word
clips and takes the seams.

- **A third clip set, `numbers`** (`gen_audio.number_items`,
  `web/audio/numbers/` + `numbers.json`), 31 clips, ~180 KB. Rendered again
  rather than reusing the `words` set, because that set alternates between two
  voices -- which over `tekas pits kiru, tets katon wats tekas kins` would
  change speaker four times inside one number. `NUMBER_VOICE` is one voice for
  the whole set.
- `site.js:playSequence` schedules the clips against `AudioContext.currentTime`
  rather than chaining `onended` handlers: `onended` fires on the main thread
  and would inherit whatever jank is there, which on a chain is audible as
  uneven gaps. `CHAIN_GAP` between words, `CHAIN_PAUSE` at the comma pikotika
  puts before a thousands group. A second press stops the first reading rather
  than talking over it.
- Tapping one of the **Try** chips fills the box *and* plays, since the tap is
  already the user gesture that unlocks the `AudioContext`.
- **The reading is chipped like any other Pikotika on the site.** That works
  because a reading is only ever the fourteen number words plus, for an
  ordinal, one compound -- and **every ordinal is a standing compound**, 1st
  through 10th and 100th, 1000th and 1000000th, which is the complete set
  because a reading always ends in a digit or a scale word. So `tekas wunorten`
  is two real entries and there is no chip on the page that opens nothing.
- **An ordinal with a standing compound gets one clip, not two.**
  `numbers.js:ORDINAL_CLIPS` is the set, and `suffix()` emits `a: [form]` for a
  member and `a: [digit, 'orten']` otherwise. It matters: `sensorten` is a
  0.94 s clip against 0.69 + 0.75 s of two separately-stressed words, which is
  audibly two words and not one. The last word of *any* ordinal reading is one
  of these, so 12345th ends in a single `kinsorten` like 5th does, and nothing
  chains.
- `build.py:ordinal_glosses` reads the set **out of compounds.tsv** rather than
  listing it, so an ordinal recorded on one side and not the other fails the
  build -- a form claimed in `numbers.js` with no clip is simply silent, and
  `check_numbers` names both directions of the mismatch.

### `pikotika.py` reads `/` and `%` too

Added after the page settled on writing a fraction **3/4** and a percentage
**50%** rather than spelling them **3 in 4** and **50 inkaton**. The tool is
internal, but a converter that cannot read the notation its own site teaches is
a trap for a later session.

`fraction_words` and `percent_words` join `decimal_words` and `clock_words`
under `numeral_words`, which is the single hook both `parse_latin` and
`parse_han` go through -- so the notation works in every direction at once, and
`3/4` renders back as `3/4` in Latin and Han while reading as `tets in wats`.
**A denominator of 100 folds to `inkaton`**, so `50/100` and `50%` give the
same reading, which is what the web reader already did.

`phonemes.NUMERAL` grew the same two marks, so a sentence with `30%` in it is
spoken as `tets tekas inkaton` instead of being handed to an English voice as
"thirty percent".

### A numeral in a sentence had never been spoken right

Found while writing the page, and older than it: `phonemes.py` passed digits
through untouched, so Kokoro -- an English model being handed an Arabic numeral
-- said them **in English**. Every corpus clip with a digit in it had been
saying "twenty moni por wun" since the audio pipeline was built.

`phonemes.spell_numerals` now expands a free-standing numeral to its reading
before anything is phonemized, which is where the fix belongs: `phonemes.py` is
the one description of how the language sounds, and the sound of **20** is
`pits tekas`. The run has to be free-standing -- a digit bound inside a
compound is part of that word -- which is the same test
`pikotika.numeral_words` applies.

The trap this sprang: **clips are cached by their text, and the text did not
change.** Both `private/audio-cache/` and the encoded `.m4a` had to be deleted
for every utterance containing a digit before `gen_audio` would re-render them;
`build_files` skips an `.m4a` that already exists. 24 sentences were affected.

## The clock (`/topics/time/`)

Three `<select>` fields -- hour, minute, AM/PM -- an SVG clock face beside
them, and the reading under both.

- **The face is drawn in `time.html`; JavaScript only rotates the hands.**
  Twelve ticks, twelve numerals, two `<line>`s and a pin, so the picture is
  still there with scripting off. The hour hand carries the minutes
  (`hour * 30 + minute * 0.5`), or half past would point straight at the hour.
- **The fields are a 12-hour clock and everything downstream is 24-hour.**
  The reading shown first is the 12-hour one, because that is what the fields
  say and what a speaker would say: Pikotika has no am/pm, so the part of the
  day goes in front. The 24-hour reading follows it as the other way to say
  the same moment, with a play button of its own.
- **Where the parts of the day begin and end is stated once**, in
  `numbers.js:daypart`, and nothing outside it depends on the seams:
  `metseyan` is the noon hour, `suryan` runs 5 to 11, `tunyan` 13 to 20, and
  `nemyan` the rest. `check_numbers` verifies that a 12-hour reading opens with
  one of the four and that the rest of it is what `pikotika.py` reads the
  12-hour digits as -- everything but *which* part, which is an editorial call
  and has no Python twin to check against.
- **It plays through the number reader's clip set**, chained the same way and
  for the same reason: there is no clip for a whole time. `CLOCK_GLOSSES` in
  `build.py` adds `ora` and the four parts of the day to `number_forms`, so
  `gen_audio` renders them in `NUMBER_VOICE` with the digits.
- The reading is a numeral, so **Han keeps the digits**: `readClock` returns
  `下日 3:45`, never a spelled-out 刻. That is `pikotika.numeral_word` in
  JavaScript, and `check_numbers` compares the two.

## The name adapter (`web/js/adapt.js`)

**The first implementation of name adaptation anywhere in the repo** (written
2026-08-19). `pikotika.py` does not adapt names; it looks them up in
`names.tsv`. The rules were only prose in `DETAILS.md` §"Proper Nouns and Loan
Words" until the `/topics/names/` converter needed to run them -- and that
section has since been migrated into the page and deleted, so the page and this
module are now the only statement of them.

- **Two paths in.** `adaptPhones()` takes ARPAbet and is the real one --
  adaptation follows sound, and `names.tsv` now records the pronunciation each
  form came from. `adaptName()` takes spelling, because spelling is all a
  visitor can type; it is the fallback for a name nobody has recorded, and the
  page labels it as such. The gap between them is exactly English orthography:
  *meter* by letters is "meter", which Pikotika reads *may-tair*; by sound it
  is **mitar**.
- **A recorded adaptation beats the rules.** `names.tsv` is what speakers have
  agreed on, and it is already in `lexicon.json` keyed by the English it came
  from, so the converter looks there first and says when it did — showing the
  rules-only form in parentheses, which is more interesting than hiding it.
- **`build.py:check_adapter` re-derives every row of `names.tsv` from its own
  `phones` column**, under node. The adapter is the one piece of the language living only in
  JavaScript, so it has no Python twin to check against; `names.tsv` is better
  ground truth anyway, being authored rather than derived. 30 of 38 rows fall
  out of the rules. The other 8 are listed in `ADAPTER_EXCEPTIONS` with a
  reason each, so a change that breaks a name the adapter used to get right
  still fails the build -- and one that *fixes* an exception fails too, asking
  for it to be removed from the list.
- The check skips with a note when node is missing, so a contributor without it
  can still build.
- **`AA` is the one phone Pikotika hears two ways**, and the spelling breaks
  the tie. It is the vowel of *father*, which is `a`'s target, and also the
  vowel of *lot* -- and `o` is defined as *go* "or the o in long", the same
  sound for most English speakers. Both readings are correct, so *Tom* and
  *Bob* keep their `o` while *Marta* and *Carla* keep their `a`. Letters are
  matched to phones by position, counting vowels in each, so *Tomas* (OW-AA
  against o-a) gets it right; where the counts disagree, the tie-break is
  skipped.
- **A syllabification bug found by *English***: the coda is the consonant
  sitting against the *preceding* vowel, and `fixMedial` was keeping the last
  legal one instead of the first. *inkris* came out **inukuris** rather than
  **inkuris** -- `n` is a legal coda and `k` is not, so `k` is what needs a
  vowel.
- **The exceptions are all sound, not spelling** (*English*, *Joe*,
  *Strout*, *Eve*). It was eight until 2026-08-19, when the other four went
  away rather than being tolerated: the loans lost the extra `-u` they had
  been carrying (**metoru** → **meter**, **ritoru** → **riter**, **kuramu** →
  **kuram**), and *Petr*, whose adaptation disagreed with `DETAILS.md`'s own
  helper-vowel rule, was replaced by *Peter*, which needs no adaptation at
  all. An exception list is worth having precisely because it makes that kind
  of residue visible enough to argue with.
- **`gen_names.py` pours common given names into `names.tsv`**, adapted from
  their CMUdict pronunciation by the same `adapt.js` the site runs. CMUdict is
  the pronunciations and nothing else -- it does not say which of its 135,166
  entries are names, and *sandwich* and *smith* look alike to it -- so the name
  list is NLTK's names corpus, intersected with it: 4,873 names, which collapse
  to **3,342 forms** because Pikotika draws fewer distinctions than English.
  Sources are cached in gitignored `private/names-src/`; the script is run by
  hand, not by the build, and `check_adapter` re-derives every poured row from
  its own phones exactly as it does a curated one.
- **Poured names are searchable but not browsable.** Each carries `bulk: 1` in
  `lexicon.json`, and the Vocab browse list skips them: listed, three thousand
  names would bury every other kind of word in a page whose empty state is
  meant to be read down. Search and permalinks reach them normally, so
  `/vocab/#Eran` opens *Aaron; Aron; Ellen; Helen*. The browse list still shows
  617 entries, as it did before the pour.
- **A curated row outranks a poured one wherever they collide**, in two places
  that both had to learn it: `pikotika.Tables` keeps the first row for each
  form (curated rows are written first), and `gen_lexicon.name_entries` yields
  curated names before poured ones. Without either, the poured *Mitar*
  (Michal, Mitchell) displaced the loan **mitar** 'meter' and took its audio
  with it, and *Tom* became Dom/Thom/Tome. The extra English names still
  resolve: typing *Dom* finds **Tom**.
- `adapt.js` is a second script tag (`adapt_version`), not part of `site.js`,
  so node can `require` it. It is dependency-free and defines
  `window.pikotikaAdapt` in the browser. The Tools converter will want the same
  module.
- One trap, already sprung: `''.indexOf(anything)` is `0`, so a naive
  `VOWELS.indexOf(c) >= 0` reports **true** at the end of a word. That made
  *Mary* come out as **Maruyu**. `isVowel` and `isCoda` test the length first.

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

**`pikotika` now runs the whole project, not only the audio** (2026-08-20).
It was missing `fonttools` (which `build.py:check_fonts` and `gen_han_font.py`
need) and the Python brotli binding (which writing a woff2 needs), so the two
halves of the build lived in different interpreters and each failed loudly in
the other's — `ModuleNotFoundError: fontTools` from the audio env, `kokoro_onnx`
from base. Fixed by installing them there:

    micromamba install -n pikotika -c conda-forge fonttools=4.51.0 brotli-python

Two things that cost time: conda-forge's **`brotli`** is the C library and the
Python binding is the separate **`brotli-python`**, so installing the obvious
name leaves the import still failing; and `fonttools` is pinned to base's
4.51.0 rather than taken latest, since the font output depends on it (see The
Han font above).

Verified before switching over: every module compiles under 3.12, and a site
built under `pikotika` is **byte-identical** to one built under base's 3.8.8 —
diffed whole, `docs/` against `docs/`. The base environment still works and is
not going anywhere, but nothing requires it now.

This retires the reason `build.py` imports `fontTools` *inside* `check_fonts`
rather than at the top: that was so `gen_audio` could `import build` from an
environment without it. Harmless to keep, and worth keeping — it is one less
thing that has to be true about a contributor's environment — but it is no
longer load-bearing here.

| file | what |
|---|---|
| `phonemes.py` | Pikotika → IPA. The one description of how the language sounds. |
| `gen_audio.py` | renders clips, builds the sprites |
| `private/audio-cache/` | WAVs keyed by voice and utterance; gitignored |
| `web/audio/words/*.m4a` + `words.json` | one file per word |
| `web/audio/numbers/*.m4a` + `numbers.json` | the number reader's 31 words, one voice |
| `web/audio/sentences/*.m4a` + `sentences.json` | one file per sentence |

`phonemes.py` was lifted out of the `private/speak.py` prototype, which now
imports it. Do not let a second copy of the phoneme tables come back — Kokoro
drops symbols outside its vocabulary *silently*, so a divergence between the
tool and the build would surface as a missing sound and no error.
`check_symbols()` guards the vocabulary itself.

**Voices.** `af_heart` and `bm_george`, chosen by ear over the full set
(`af_nicole` is unusable). Word tiles alternate between them so the learner is
not tuned to one speaker; dialogs and stories will pick by character instead,
which is why `assign_voices()` is a function rather than a constant.

**`af_heart` replaced `af_sky` on 2026-08-20, everywhere at once.** `af_sky`
puts a consonantal onset in front of some vowel-initial words — **ora** came
out "dora" — which is fatal on `/topics/time/`, where `ora` is every clock
time on the page. Confirmed by ear in `private/speak.py` as a property of the
voice, not of one clip.

The reason it could not be fixed in `NUMBER_VOICE` alone, which is the change
that first suggests itself: **the artifact belongs to the voice, and `ora` was
on `af_sky` in the word set too**, along with half the sentence clips that say
a time. Swapping only the reader would have put a clean **ora** in the clock
and a "dora" in the word chip directly above it. `NUMBER_VOICE` is a separate
constant so a *chained* reading has one speaker throughout, not so its casting
can differ; keep it whichever of `WORD_VOICES` is the female voice.

The swap itself reassigns nothing. `assign_voices` decides by tuple position,
not by voice name, so every word on `af_sky` became `af_heart` and the 50/50
split and the male voice's half were untouched.

**Changing a voice does not re-encode anything on its own, and the failure is
silent.** A clip's filename hashes the *utterance text*, not the audio, so the
new rendering wants the file that is already there — and `build_files` skips
an `.m4a` that exists. Run naked, the swap rewrote the three JSON indexes to
say `af_heart`, with `af_heart`'s durations, over 552 `.m4a` files that were
still `af_sky`. Nothing errors, nothing is missing, and `check_audio` is happy,
because it compares the index against what the site *wants* and the index is
correct; what is wrong is the bytes underneath it. It was caught by `ffprobe`
disagreeing with the index: `aku` indexed at 0.528 s, 0.708 s on disk, file
dated two days earlier.

So the recipe is **delete, then render**: remove the `.m4a` for every clip the
index assigns to the changed voice, then run `gen_audio` again. The second run
is cheap — the WAV cache is keyed by voice and utterance and was filled by the
first one, so it is an ffmpeg pass, not Kokoro inference. Verify by mtime and
byte total rather than by exit code (words fell 4.15 MB → 3.87 MB), and spot
check a clip of each voice: the untouched half must still be the old files.

This is the same trap as the edited-utterance one below, and the same trap the
digits fix sprang. **`private/audio-cache/` is keyed by voice, so it does not
protect you here** — it was a clean miss, rendered correctly, and the stale
half is downstream of it in the encode.

**It used to happen on ordinary corpus additions too**, which is what got the
voice assignment changed. See below.

**So verify by content, not by exit code.** `private/check_clips.py` compares
each index entry's duration against `ffprobe` on the file it names; a stale
clip disagrees, because it is a different performance of the same words.
`--fix` deletes what it finds, and `gen_audio.py` then re-renders exactly
those. Run it after any change to the voices — `check_audio` will not tell
you, since it only asks whether the index covers what the site wants, and that
was `ok` throughout every failure of this kind.

A durable fix for the remaining case would be to **put the voice in the clip's
filename hash**: a reassignment becomes a new name, the old file a real orphan,
and `check_audio`'s existing orphan reporting catches it with no new machinery.
Not done — the cost is renaming ~1,000 committed files, and with the
assignment now stable (below) the only thing left that can trigger it is a
deliberate voice change, which is rare and which you already know you are
doing.

**The voice assignment is a plain hash, not an exact split** (changed
2026-08-20). `assign_voices` hashes the utterance and takes it mod the number
of voices, so a key's voice depends on nothing but the key.

It used to sort the keys by hash and cut the list at the median, to guarantee
an exact 50/50 — hash parity had been rejected for coming out 54/46 over 613
words. The flaw is that **the cut moves**. Adding one corpus row shifts the
median by half a slot and reassigns whatever sits beside it, and a reassigned
clip goes stale by the route above: it already has an `.m4a`, so the new voice
reaches the index and never the disk. Adding the party sentence took sentences
from 416 to 417 and silently left six clips speaking their old voice —
`Tarsarve.`, `Panomo ri tika a tis.` and four others, none of them touched by
the edit that caused it. It had been happening on every corpus addition since
the pipeline was built.

So the docstring's old stability claim read exactly backwards: "adding five
coinages moves 0–2 words to the other voice" was offered as the *cheap* case,
and it is cheap only if those 0–2 files actually get re-encoded, which they did
not.

An approximate share is worth much more than an exact one, and the
approximation is not even bad — measured at the changeover, **312/305** over
the words and **211/210** over the sentences. The 54/46 that motivated the
median cut was a smaller sample read as a trend. The change also generalizes:
a third or fourth example voice is now just a longer `WORD_VOICES`.

The changeover itself moved 499 clips, so `web/audio/{words,sentences}/` was
emptied and rendered from scratch rather than patched — with the assignment
changing under them, a delete-what-is-stale pass would have had to be right
about all 499. `numbers/` was left alone: it is `NUMBER_VOICE` throughout and
never goes through `assign_voices`.

**Files, not sprites, for everything the site plays.** `GAME_DESIGN.md`
specifies sprites throughout; that is right for a lesson, which plays many clips
from a known set and would otherwise make forty fetches. It is wrong for
anything played one at a time: measured, fetching and decoding the 613-word
sprite put **6 to 14 seconds** in front of the first tap, against **7–44 ms**
for a single file. `build_sprite()` is kept, unused, for the course.

Sentences come from `corpus.tsv` plus `build.page_sentences()` — every
multi-word `.pk` string on the site, since an example on a page is not
necessarily a corpus line. `build.py` keeps its `fontTools` import inside
`check_fonts` so that `gen_audio` can `import build` from an environment
without fontTools — which `pikotika` no longer is (see Environment above), so
this is now belt and braces rather than a requirement.

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

**Editing an utterance is the case that bites**, not adding one. Clips are
keyed by exact text, so a corrected line leaves its old clip behind and arrives
with none; the check found one already shipped that way. `gen_audio` does not
delete the orphan, so a clip named in the warning as no longer used has to be
removed by hand.

**Person names get no clip** (decided 2026-08-19). `names.tsv` is meant to
grow to thousands of them, and each would cost ~7 KB of generated audio for a
word whose pronunciation is entirely regular and spelled out in front of the
reader. Place names and loans keep theirs, being vocabulary rather than
labels; `build.py:wants_audio` discriminates on the `People and society`
category, which is already there and already means this.

**So the play button is added only when there is something to play.**
`addWordPlayer()` waits for the clip index and inserts the button if the form
is in it -- inserted at the front, since the rest of the row is built
synchronously while it waits. Tapping **Aras** gets a popover with no button;
**Rispan** and **mitar** get one.

That work turned up a bug of its own: the popover asked for
`entry.form.toLowerCase()`, but `words.json` is keyed by the display form, so
**every name's audio had always been a silent no-op** -- invisible until now
because every other form is already lowercase.

**The check covers words as well as sentences**, and that half earned itself
immediately: `gen_audio.word_items` was building its own lexicon *without* the
forms that appear only in page prose, so **monivaso** -- written on the names
page, in no table -- had no clip and nobody knew. `build.audio_words()` is now
the definition for both, as `audio_sentences()` already was.

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

## Twemoji

Many of the icons used on the site (for example, on the topic cards) are Twemoji, sourced from: https://twemoji-cheatsheet.vercel.app/


## Not built yet

The header audio toggle, and slow ("turtle") variants — Kokoro takes a speed
parameter, so those are a second generation pass rather than `playbackRate`,
which pitch-shifts. Vocab search is built; the grammar pages and the Tools
converter are still placeholders, as are fourteen of the seventeen topics.
The Tools "number and date reader" `WEBSITE_DESIGN.md` asks for can reuse
`numbers.js` as it stands, including its `readClock`; what is still missing
there is dates -- years, months and weekdays -- which want `/topics/dates/`
written first.
