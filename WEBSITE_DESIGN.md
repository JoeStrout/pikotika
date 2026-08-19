# Website Design

Design notes for **pikotika.org** — the public home of the language. This document
records decisions and their reasons. Nothing here has been built yet.

The site has one job: turn a curious visitor into someone who can say something in
Pikotika. Everything else — the reference tables, the converter, the essay on why
this matters — is support for that. So the ordering principle throughout is
*shortest path from landing to first sentence*.

Companion documents: `GAME_DESIGN.md` (the course itself), `CURRICULUM.md` (what is
taught in what order), `DETAILS.md` (the internal spec the public pages are
written from, and progressively replaced by — see [Grammar](#grammar-grammar)).


## Constraints

- **Static files only.** HTML, CSS, JS, and generated JSON/audio. No PHP, no
  database, no server-side anything. This is what lets the site be hosted free
  and forever, mirrored, and archived by anyone.
- **No accounts, no logins, no tracking.** Inherited from `GAME_DESIGN.md`, and
  it applies site-wide, not just to the course.
- **Generated from the tables.** `roots.tsv`, `compounds.tsv`, `names.tsv`, and
  `corpus.tsv` are the source of every word the site displays. Nothing is
  hand-copied into HTML, ever — a site that can drift from the lexicon will.
- **Works offline once visited.** See [Installable and offline](#installable-and-offline).
- **Responsive, mobile-first.** The realistic use is someone doing a lesson on a
  phone on a train, and someone else reading the grammar on a laptop.


## Sections and navigation

Seven top-level sections, in this order, in a persistent nav bar:

| section | URL | what it is |
|---|---|---|
| **Overview** | `/` | the elevator pitch — what Pikotika is, in one screen, ending in a live example |
| **Vocab** | `/vocab/` | searchable roots and compounds |
| **Grammar** | `/grammar/` | one page per grammar point, with examples |
| **Topics** | `/topics/` | how to talk about a thing: colors, feelings, time and dates, food, travel |
| **Tools** | `/tools/` | the converter and anything else that runs in the browser |
| **Learn** | `/learn/` | the course, plus stories and SRS decks |
| **Why** | `/why/` | the argument for the project |

Overview is the site root, not a separate `/overview/` page. A visitor who types
the bare domain gets the pitch.

**Topics is its own tab, not a subsection of Grammar.** The two answer different
questions. Grammar answers *how does the language work* — someone arrives there
with a construction in mind. Topics answers *how do I talk about this* — someone
arrives with a situation in mind, and asking them to find "Colors" filed under
Grammar is asking them to first decide that color is a grammatical category, which
it isn't. Putting these behind Grammar buries the most immediately useful pages on
the site.

**Plan for a two-row nav on mobile.** Seven items with Games coming makes eight,
which no amount of label-shortening fits in one 360px row. So the mobile nav wraps
to two rows of four rather than collapsing to a hamburger. A hamburger hides the
site's shape behind a tap, and the shape *is* the pitch: someone who sees "Grammar"
next to "Learn" next to "Topics" understands in one second what kind of site this
is. Two rows of four costs about 80px of vertical space, which the sticky header
can reclaim by shrinking to one row on scroll. Desktop stays a single row with the
wordmark at the left.

**Games** gets the eighth slot when it exists. Until then the course lives at
`/learn/level/3/lesson/7` and anything game-shaped goes at `/learn/play/<name>/`,
so promoting it later is a redirect and one nav item — not a restructuring. The
thing to avoid is games directly under `/learn/<name>/`, where they would collide
with the course's own paths.

During a lesson the nav is replaced by minimal lesson chrome — progress bar, close
button, audio toggle — because a lesson wants the whole viewport. This is the one
exception to "nav on every page."


## Section detail

### Overview (`/`)

One screen of pitch, then progressive detail, essentially `QUICK_START.md`
restructured for the web. The arc:

1. **What it is**, in two sentences, with the name glossed (*piko-tika*, small talk).
2. **Four sentences you could say tomorrow** — the bathroom/wheat/wait/six-days
   set from `QUICK_START.md`, each with audio.
3. **Why it's small** — ~200 roots, the compound trick shown with three examples.
4. **Why it's regular** — `S RI V A O`, and the list of things that don't exist.
5. **A single call to action**: *Start Level 1* → `/learn/`.
6. **Community links** — subreddit and Discord, in the footer.

Every Pikotika form on this page is a **word chip** (see [Shared components]), so a
reader can tap any word to see its gloss and hear it before they have learned
anything. That interaction *is* the demonstration: the language is transparent, and
letting someone poke at it proves that faster than a paragraph claiming it.

# (`/vocab/`)

A single client-side search page over roots + compounds + names, not three pages.
One search box, one result list, a filter chip row (`roots` / `compounds` /
`names` / `loans`, plus the `category` values from `roots.tsv`).

The whole lexicon is roughly 600 entries and compresses to well under 100 KB of
JSON, so it ships as one file and searching is instant, offline, and needs no
index server. Search matches English gloss, gloss2, Latin form, Han character, and
the `covers` column — that last one matters, since a visitor looking for "rice"
should land on **riso** even though the gloss is *grain*.

A root's detail view shows: both glosses, Han character with stroke count, the
`covers` list, the mnemonic, the compounds that contain it, and corpus sentences
that use it. Those last two are the payoff of having the tables — a dictionary
entry that shows the word in real sentences, generated, with no editorial labor.

`/vocab/riso` is a permalink to a single entry, so grammar, topic, and lesson pages
can all link to words.

### Grammar (`/grammar/`)

An index page listing every grammar point, then one page per point — shorter than
`DETAILS.md`, more example-forward, each page ending in two or three sentences to
parse yourself with the answers behind a reveal.

Pages, roughly:

word order · modifiers · prepositional phrases · joining and explaining ·
comparison · questions and answers · time, aspect, and mood · conditions and
counterfactuals · modifier order · `TE` · subordinate clauses · indefinite
subjects · pronunciation and stress · the three notations

**`DETAILS.md` is migrated, not mirrored.** Two copies of the spec would drift, so
there will not be two copies. As each web page is written, its content is checked
against the corresponding `DETAILS.md` section for consistency, and then that
section is **deleted from `DETAILS.md`**. When the Grammar and Topics sections are
complete, what remains in `DETAILS.md` is only what we chose not to publish —
constraints on new root forms, notes for coiners, and similar internal matter —
and the file is renamed to reflect that. This makes the website authoritative for
the language as it is presented, and leaves the repo with exactly one home for
each fact.

Presentation is not constrained by how `DETAILS.md` happens to be organized. A web
page may split one `DETAILS.md` section into three, or merge three into one; the
consistency check is about claims, not about structure.

Examples on these pages are hand-written prose, but every *form* in them is
verified at build time by running it through `pikotika.py`, so a stale coinage
fails the build rather than shipping.

### Topics (`/topics/`)

Situation-shaped pages. Some are the reference tables that currently live in
`DETAILS.md`; the rest are phrasebook pages built from `corpus.tsv`, `IDIOMS.md`,
and `DIALOGS.md`.

From `DETAILS.md`: **numbers** · **telling time** · **dates and weekdays** ·
**seasons** · **colors** · **names and loanwords** · **pleasantries and filler**

New: **food and eating** · **weather** · **money and shopping** · **travel and
directions** · **health and the body** · **meeting people** · **feelings** ·
**family** · **lodging** · **small talk**

**Each topic page is a custom design, not a filtered list.** This is the section
where the site stops being a rendering of the repo and starts being a website. The
colors page gets a real color diagram, not a table of seven swatches. The feelings
page gets an emotion chart or a run of emotive emoji, because feelings are the one
domain where a picture beats a gloss outright. Time and dates gets calendars —
possibly a live one, showing the current month with Pikotika weekday names, which
is a genuinely useful thing that exists nowhere else and costs about thirty lines
of JavaScript. Numbers gets an interactive reader: type any number, hear it.

The corpus sentences are **supporting material on these pages, not their
substance** — the worked examples under the custom content, showing the vocabulary
in use with audio and word chips. So a topic having only a handful of tagged
sentences is not a problem to solve; the colors page would be mostly diagram even
if the corpus had eighty color sentences.

This also means the topic pages are the most expensive per page on the site and the
most worth the money. They are what someone links to, screenshots, and remembers.

### The `topic` column

`corpus.tsv` carries a **`topic` column**, semicolon-separated, so one sentence can
support several pages. All 375 rows are tagged; 59 are deliberately blank, being
pure grammar demonstrations (*I could have gone*, *the animal the person ate*) with
no situation attached. Those still serve Grammar; they just have no topic home.

Seventeen slugs, one per page:

| slug | rows | slug | rows |
|---|---|---|---|
| `food` | 76 | `numbers` | 18 |
| `smalltalk` | 57 | `time` | 16 |
| `travel` | 42 | `meeting` | 15 |
| `pleasantries` | 41 | `health` | 12 |
| `family` | 40 | `names` | 10 |
| `feelings` | 26 | `colors` | 7 |
| `money` | 24 | `weather` | 5 |
| `dates` | 21 | `seasons` | 3 |
| `lodging` | 20 | | |

Four of these were not in the first list and were added because content had nowhere
to go: **`lodging`** (the whole hotel dialog), **`family`** (the bedtime dialog plus
the relation vocabulary that recurs everywhere), **`feelings`**, and
**`smalltalk`** — which, given what the language is named for, should probably have
been there from the start.

A new corpus row without a topic is not an error; the build reports the count of
untagged rows rather than failing.

Topic pages link into Grammar wherever a construction shows up (the time page links
to aspect; the shopping page links to comparison), and Grammar pages link back out
to Topics for worked examples. Neither section repeats the other.

### Tools (`/tools/`)

Browser versions of what the repo's scripts do:

- **Converter** — the `pikotika.py` core: paste English, gloss, Latin, or Han; get
  the other three. The flagship tool.
- **Name adapter** — type a name, watch the two-pass adaptation run, with each
  substitution shown. Delightful, and it is the single most common thing a
  newcomer wants to do with a conlang: see their own name in it.
- **Number and date reader** — type `2026-08-09` or `15:45`, get the spoken form.
  Small, self-contained, and it covers a part of the language people otherwise skip.
- **Han ↔ Latin toggle** on any pasted text.

**The porting decision.** `pikotika.py` is ~1000 lines and cannot run in the
browser without Pyodide, which costs several megabytes and breaks the offline
story. So the conversion core gets **ported to JavaScript** — the algorithms are
small (lexicon lookup, compound splitting, the linking-`e` rule, name adaptation,
number reading); it is the lexicon that is large, and that ships as data either
way.

A port is a second implementation, and second implementations drift. The guard is
a **build-time conformance test**: run every row of `corpus.tsv`, every compound,
and every root through both implementations in all four notations, and fail the
build on any disagreement. That is a few thousand comparisons of already-authored
material, costs nothing, and makes the JS port trustworthy in the only way that
matters.

### Learn (`/learn/`)

Everything in `GAME_DESIGN.md` — the course, its map screen, the six task types,
the story lessons, the audio sprites. Not restated here. What the *site* adds
around it:

- `/learn/` is a landing page: a "Start" button, the level map, and a short
  honest statement of the time commitment (~50 lessons, 5–8 minutes each).
- **Stories** (`/learn/stories/`) — the `DIALOGS.md` conversations as readable,
  playable pages with audio and tap-for-gloss, separate from the gated story
  lessons inside the course. These are for someone who wants to read, not drill.
- **SRS decks** (`/learn/decks/`) — `make_srs.py` output offered as downloadable
  Anki/CSV decks, and the printable root cards (`root_cards.svg`) as a PDF. These
  are files to hand over, not an app to build.
- `/learn/play/` reserved, empty for now.

### Why (`/why/`)

The essay. Long-form prose, one page, no generated content — why a ~200-root
auxiliary language is worth building in 2026, what it is for, what it is not
trying to replace. This is the page that gets linked when someone posts the site
somewhere, so it should be the best-written thing on the site.

Also the natural home for the project's shape: the CC BY license, the repo link,
how to contribute a coinage, who made it, and the community links.

### Community

A **subreddit** and a **Discord**, linked from both Overview and Why — in the
Overview footer, and as a proper closing section on Why, where someone who has just
read the argument is at their most likely to join.

Both links live in one place in the build config and are injected, so adding a
third venue later does not mean editing pages. A language with no visible speakers
is a hard sell, so these are worth having live before the site is announced
anywhere, even if they are quiet at first.


## Shared components

Three components carry most of the site's identity. Building them once, well, is
most of the design work.

**The word chip.** Any Pikotika word anywhere on the site — in a grammar example,
in the pitch, in a story — is tappable, and marked with a **dotted underline**, the
convention Duolingo has already taught most of our visitors to read as "tap this."
Tapping shows a small popover: the gloss pair, the Han character, the literal parse
if it is a compound, a speaker button, and a link to `/vocab/<form>`. Generated
from the same JSON the Vocab search uses, so it works on every page including
offline.

The underline is subtle — one-pixel dots at 40% of the text color — and suppressed
where every word on a line would carry one (the Latin line of an example block sets
it once at the block level, not on each word).

**The example block.** The four-line unit the docs already use: English, gloss,
Latin, Han. On the web it becomes one block with a notation toggle, remembering
the reader's preference in `localStorage`. Most readers will turn Han off; the
ones who want it want it everywhere.

**The speaker button.** Plays the pre-generated clip for a word or sentence, using
the sprite-and-`AudioBuffer` scheme from `GAME_DESIGN.md`. Same machinery as the
course, used site-wide.


## Typography and Han

The house typographic conventions in `CLAUDE.md` are for Markdown; the web version
maps them to real styling rather than to bold and italic markup:

| role | web treatment |
|---|---|
| Pikotika (Latin notation) | the display face, medium weight, slightly larger than body |
| gloss notation | italic, muted color, hyphenated |
| English meaning | roman, single quotes |
| particles in gloss | small caps |
| letters as letters | monospace |

The point of the original convention — *don't italicize the object language, it
reads as harder* — carries over: Pikotika should look like the normal text of the
site, not like foreign matter quoted inside it.

### The Han subset font

Fewer than 200 distinct characters are used across the whole language, so a subset
built with `pyftsubset` is a few kilobytes rather than several megabytes. Ship it
self-hosted as WOFF2, with the character set derived from the `han` column at
build time.

**Base it on Noto Sans JP, not SC.** The `han` column uses Japanese shinjitai forms
throughout — 体, 黒, 緑, 楽, 真, 画, 国, 悪, 来, 与, 学, 会 are all the Japanese
simplifications, and the weekday characters were chosen to match Japanese and
Korean exactly. A Simplified Chinese face renders several of these differently or
lacks them, and the system CJK font on any given device is a coin flip. Pinning the
face is the only way the characters look the way they were designed.

(This corrects the earlier draft, which had the risk backwards — Japanese glyph
forms are what we want, not what we need to avoid.)

**Yes, the particles go in the same font.** ⊢ (U+22A2) and ⇒ (U+21D2) are the two
that need it; `>` for *TE* is plain ASCII and comes from the body face. Two ways to
do it, and the second is better:

1. Merge glyphs from a symbol face into the CJK subset with `fontTools.merge`. One
   file, but it means reconciling two fonts' units-per-em and vertical metrics, and
   the result is a font neither designer shipped.
2. **Ship two `@font-face` rules with `unicode-range`** — the CJK subset for the
   Han block, and a second tiny subset (from Noto Sans Symbols 2 or the body face,
   whichever draws a better turnstile) for exactly `U+22A2, U+21D2`. The browser
   picks per codepoint, both files are tiny, and each font keeps its own metrics.

The visual match matters more than the file count: ⊢ and ⇒ sit inline with Han
characters in running text, so the two subsets need their weights and optical sizes
compared side by side before either is committed. Get this wrong and Han text looks
like it has two typefaces fighting, which is exactly the impression the notation
can least afford.

**Assert coverage at build time.** Walk the `han` column plus the two particle
codepoints, and fail the build if any codepoint has no glyph in its assigned face.
A missing character ships as a tofu box on the one page that uses it, and nobody
notices for months.

**Dark mode** from the start, via CSS custom properties and `prefers-color-scheme`.
Cheap if done at the beginning, tedious later. The wordmark already exists in both
variants (`web/images/Title_Light.png`, `Title_Dark.png`, 822×225), swapped with a
`<picture>` element rather than CSS background images so it stays a real `<img>`
with alt text.


## Icons

One master drawing of 小言 on a yellow gradient ground, exported at these sizes.
The wordmark's ghosted 小言 already establishes the motif, so the icon is a crop of
the identity rather than a separate mark. **All of these now exist in
`web/images/`.**

| file | size | purpose |
|---|---|---|
| `icon.svg` | vector | modern favicon; scales everywhere |
| `favicon-32.png` | 32×32 | fallback favicon for older browsers |
| `apple-touch-icon.png` | 180×180 | iOS home screen — **must not be transparent** (see below) |
| `icon-192.png` | 192×192 | manifest, Android home screen |
| `icon-512.png` | 512×512 | manifest, splash screen generation |
| `icon-maskable-512.png` | 512×512 | Android adaptive icons — see below |
| `og-image.png` | 1200×630 | link previews on Reddit, Discord, Mastodon, iMessage |

**The maskable variant is a different drawing, not a resize.** Android crops icons
to a platform-chosen shape (circle, squircle, rounded square), so all meaningful
content must sit inside the centered circle of 80% diameter — 410px of a 512px
canvas — with the ground color bleeding to all four edges. A normal icon fed into
that slot gets its edges shaved.

### The link preview image

**What it is.** When anyone pastes `pikotika.org` into Reddit, Discord, Slack,
Mastodon, iMessage, WhatsApp, or a Google result, the receiving app fetches the page
and reads its `<meta>` tags to build a preview card. `og:image` is the picture on
that card. Every one of those platforms is a place we expect the site to be shared,
and on most of them the image occupies more visual space than the title and
description combined. It is the site's first impression far more often than the
site itself is.

**The tags that go with it**, in every page's `<head>`:

```html
<meta property="og:title"       content="Pikotika">
<meta property="og:description" content="…">
<meta property="og:image"       content="https://pikotika.org/og-image.png">
<meta property="og:url"         content="https://pikotika.org/">
<meta property="og:type"        content="website">
<meta name="twitter:card"       content="summary_large_image">
```

That last line matters more than it looks: without it, X and a few clients that
follow its conventions render the small square thumbnail card instead of the wide
one, and the wide image gets center-cropped to a square — the exact failure the
wordmark was chosen to avoid.

**Per-page images later, not now.** `og:title` and `og:description` should be
per-page from the start (the build has the data, and a shared grammar page whose
card says "Pikotika" tells a reader nothing). A per-page *image* — the root's Han
character on the card for `/vocab/riso`, say — is a nice touch that can be
generated later from the same build script, since each is just a glyph composited
on the standard background. Not phase 1.

**Caching.** Every platform caches the fetched card aggressively and by URL, so a
corrected image at the same path may keep showing the old version for days or
longer. If it changes materially, change the filename (`og-image-2.png`) rather
than waiting for a cache to expire. Facebook and LinkedIn both offer debugger tools
that force a re-fetch; Discord and Slack largely do not.


## Installable and offline

Support "Add to Home Screen" properly — it is a nice-to-have that is unusually
cheap here, because the site is already static files and already small.

What it takes:

- **`manifest.json`** — name, short name, `display: standalone`, theme and
  background colors, and the icon set above. iOS additionally wants an
  `apple-touch-icon` link tag and `apple-mobile-web-app-*` meta tags; iOS reads the
  manifest for installs now, but the meta tags are what older iOS honors and they
  cost four lines.
- **A service worker** that precaches the app shell (HTML, CSS, JS, lexicon JSON,
  both subset fonts) on install, and caches lesson audio lazily as lessons are
  visited. The whole course's audio is under 10 MB per `GAME_DESIGN.md`, so
  precaching everything is also viable — but lazy is friendlier to someone on
  mobile data who only wanted to look up a word.
- **Cache versioning** keyed to the build hash, so a new deploy actually reaches
  people rather than serving a year-old shell forever. This is the failure mode
  that bites static PWAs, and the fix is to decide the invalidation scheme before
  writing the first service worker, not after.

Two caveats worth knowing up front. iOS evicts service-worker caches after roughly
seven weeks without a visit, so offline is best-effort, not a guarantee — an
installed site can come back empty, which the app shell must survive gracefully.
And iOS keeps installed-PWA storage separate from Safari's, so lesson progress in
the installed app does not carry over from the browser. Since progress is only a
lesson pointer, and the pointer is also the URL, this is a small loss.

Nothing above requires a build framework. A ~150-line service worker and a manifest
are the whole of it.


## Build and deploy

**One Python build script**, in the spirit of `gen_tables.py`: read the TSVs, write
`site/`. No npm, no bundler, no framework. The site is a few dozen pages, a handful
of JS modules, and one big JSON file; the tooling should not outweigh it.

```
build.py
  ├─ lexicon.json          from roots.tsv + compounds.tsv + names.tsv
  ├─ corpus.json           from corpus.tsv, indexed by the topic column
  ├─ lessons/*.json        from CURRICULUM.md + the lesson plan table
  ├─ audio sprites         from web/audio/, generated by speak.py batch mode
  ├─ fonts/han-subset.woff2 + fonts/particles.woff2
  ├─ pages                 templates + hand-written grammar/topic/why prose
  └─ checks                pikotika.py vs the JS port; example forms; font coverage
```

Source layout keeps the site in the repo, so the tables and the site that renders
them stay in one commit:

```
web/            source: templates, CSS, JS, prose, images/, audio/
site/           build output, git-ignored
build.py        the generator
```

`web/audio/` holds the generated `.m4a` clips and is **committed**, not ignored.
Kokoro is too heavy to run in CI, the clips are deterministic outputs of authored
material, and the whole set is under 10 MB — which git handles fine at this scale
and which makes a checkout a complete, buildable site.

### Hosting: point the DNS at GitHub Pages

**To the end user the two are indistinguishable** — same `pikotika.org` in the
address bar, same HTTPS padlock, no third-party branding, no redirect. The choice
is entirely about how deploys work for you.

Recommend **GitHub Pages**, for three reasons: the repo is already public at
`JoeStrout/pikotika`, so it is free; deploying becomes a `git push`, with a GitHub
Action running `build.py` and publishing `site/`, which means no build step you can
forget; and the site's provenance stays visible next to the tables it is generated
from. Custom-domain HTTPS is automatic.

DNS stays at DreamHost — you add four `A` records for the apex pointing at GitHub's
Pages addresses (`185.199.108–111.153`, worth confirming against GitHub's current
docs at setup time), optionally the four matching `AAAA` records, plus a `CNAME`
for `www`. Nothing about the registration moves.

What you give up is `.htaccess`: no custom headers, no arbitrary redirect rules.
Neither matters here. Clean URLs come from the `/path/index.html` layout the build
already produces, and GitHub Pages' ten-minute asset caching is, if anything,
better for a service worker than the year-long `max-age` a hand-tuned static host
usually gets set to.

DreamHost shared hosting remains a perfectly good fallback — it is a static site;
`rsync site/ ...` would work fine — and switching either direction later is a DNS
change and a propagation wait. Do not host on both at once.


## Roadmap

The sections are not equally expensive, and the cheap ones are the ones that make
the domain worth having today.

1. **Skeleton, Overview, and Why**, with audio on the Overview examples. Real site
   at the domain: responsive, dark mode, two-row mobile nav, wordmark, community
   links, other sections stubbed. Half the prose already exists in `QUICK_START.md`.
2. **Audio pipeline**, pulled forward from its old position to serve phase 1. Voice
   audition first, then `speak.py` batch mode over roots, compounds, and corpus.
   Independent of everything else, so it can run in parallel from day one.
3. **Vocab.** The build script, `lexicon.json`, the search page, the word chip.
   This is the piece that makes the site *useful* rather than merely informative,
   and everything downstream reuses it.
4. **Topics.** Cheaper than Grammar and more immediately useful: the reference
   pages are near-verbatim migrations, and the phrasebook pages are mostly a
   corpus query once the `topic` column exists.
5. **Grammar.** Prose work, mostly, with a `DETAILS.md` section deleted per page
   shipped. Depends on the word chip and example block.
6. **Tools.** The JS port and the conformance test. Self-contained; can slip.
7. **Learn.** The largest by far, and the one with real open questions still in
   `GAME_DESIGN.md`. Its audio dependency is already satisfied by phase 2.
8. **PWA polish.** Manifest, service worker, icon set. Deliberately last: it caches
   whatever exists, so caching a half-built site early only creates confusion.

Phase 2's early start is the one scheduling constraint worth respecting. Everything
visible depends on it eventually, and voice selection is a taste judgment that
cannot be rushed at the end.


## Open questions

- **Does `food` want to be two pages?** 76 rows is a lot, and *eating out* and
  *food and drink words* are different errands. A design question for whoever draws
  that page, not a data question.
- **What `DETAILS.md` becomes** once the migration empties it — a renamed
  `COINING.md` for the internal constraints, or folded into `CLAUDE.md`?
- **Do stories live in Learn or become their own thing?** They are currently under
  `/learn/stories/`, but they are the most shareable content on the site and
  arguably belong somewhere a non-learner would find them.
- **Localization shape.** English-only for now, agreed. The only thing to get right
  today is that `lexicon.json` keys glosses by language code rather than assuming
  English, so adding a second L1 later is data rather than surgery.
