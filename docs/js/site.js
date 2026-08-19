/* Pikotika — site behavior.  Deliberately tiny; nothing here is required for
   the page to be readable, only for it to be comfortable. */

(function () {
  'use strict';

  /* --- theme toggle ------------------------------------------------------
     Three states, not two: "light", "dark", and unset (follow the system).
     The toggle flips to whichever is the opposite of what is showing now, so
     the first tap always visibly changes something. */

  var root = document.documentElement;
  var button = document.getElementById('theme-toggle');
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  function currentlyDark() {
    var set = root.dataset.theme;
    if (set === 'dark') return true;
    if (set === 'light') return false;
    return media.matches;
  }

  if (button) {
    button.addEventListener('click', function () {
      var next = currentlyDark() ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem('pk-theme', next); } catch (e) {}
      syncWordmark();
    });
  }

  /* The wordmark is a <picture> whose <source> swaps on prefers-color-scheme,
     so that it is still right with JavaScript off.  But a matching <source>
     outranks the <img> src, which would override an explicit toggle -- so once
     we are running, drop the <source> and drive the <img> ourselves. */

  var picture = document.querySelector('.wordmark picture');
  if (picture) {
    var sources = picture.querySelectorAll('source');
    for (var i = 0; i < sources.length; i++) sources[i].remove();
  }

  function syncWordmark() {
    var img = document.querySelector('.wordmark img');
    if (!img) return;
    img.src = currentlyDark() ? '/images/Title_Dark.png'
                              : '/images/Title_Light.png';
  }

  media.addEventListener('change', syncWordmark);
  syncWordmark();

  /* --- collapsing header on mobile --------------------------------------
     Scrolling down hides the wordmark row and leaves the nav; scrolling back
     to the top restores it.  A dead band keeps it from flickering. */

  var lastY = window.scrollY;
  var ticking = false;

  function onScroll() {
    var y = window.scrollY;
    if (Math.abs(y - lastY) > 6) {
      document.body.classList.toggle('scrolled', y > 72 && y > lastY);
      lastY = y;
    }
    if (y <= 8) document.body.classList.remove('scrolled');
    ticking = false;
  }

  window.addEventListener('scroll', function () {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(onScroll);
    }
  }, { passive: true });

  /* --- word chips --------------------------------------------------------
     Every Pikotika word on the site is tappable.  The wrapping happens here,
     at page load, rather than in the build: pages keep plain prose, and the
     markup stays something a person can read and edit.  What the build does
     instead is *check* the forms (see check_forms in build.py), so a word that
     could never open a popover fails the build rather than shipping as a dead
     chip.

     The lexicon is not needed to split words -- Pikotika is whitespace
     delimited -- so nothing is fetched until the first tap. */

  var PUNCT = '.,;:?!—…()[]"“”';
  var lexicon = null;
  var lexiconWanted = null;

  function loadLexicon() {
    if (!lexiconWanted) {
      lexiconWanted = fetch('/data/lexicon.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) { lexicon = data; return lexicon; })
        .catch(function () { return null; });
    }
    return lexiconWanted;
  }

  /* Split "Panyu ri kerroko?" into words and the punctuation between them,
     keeping every character so the sentence still reads and copies correctly. */
  function tokenize(text) {
    var tokens = [];
    var word = '';
    function flush() { if (word) { tokens.push({ word: word }); word = ''; } }
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (/\s/.test(ch) || PUNCT.indexOf(ch) >= 0) {
        flush();
        if (tokens.length && tokens[tokens.length - 1].gap !== undefined) {
          tokens[tokens.length - 1].gap += ch;
        } else {
          tokens.push({ gap: ch });
        }
      } else {
        word += ch;
      }
    }
    flush();
    return tokens;
  }

  function chipify(root) {
    if (root.dataset.chipped) return;
    /* data-check="off" marks a .pk that is not running Pikotika -- a word-order
       schema, say.  The build skips checking it; we skip chipping it, or it
       becomes a row of buttons that can never open anything. */
    if (root.dataset.check === 'off') return;
    root.dataset.chipped = '1';

    /* A whole sentence broken into eight buttons is announced as eight
       controls, which is not what it is.  The container keeps the sentence as
       one readable string, and the buttons are reached deliberately. */
    if (!root.getAttribute('aria-label')) {
      root.setAttribute('aria-label', root.textContent.trim());
    }

    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);

    texts.forEach(function (node) {
      var tokens = tokenize(node.nodeValue);
      if (!tokens.some(function (t) { return t.word; })) return;
      var frag = document.createDocumentFragment();
      tokens.forEach(function (t) {
        if (t.gap !== undefined) {
          frag.appendChild(document.createTextNode(t.gap));
          return;
        }
        /* A span, not a <button>.  Mousedown on a real button starts a button
           press rather than a text selection, so a sentence made of buttons
           cannot be dragged across and copied -- you get the spaces and the
           punctuation and none of the words.  A span with role=button selects
           like the text it is, at the cost of wiring up the keyboard, which
           activate() below does. */
        var chip = document.createElement('span');
        chip.className = 'w';
        chip.setAttribute('role', 'button');
        chip.tabIndex = 0;
        chip.textContent = t.word;
        chip.dataset.w = t.word.toLowerCase();
        frag.appendChild(chip);
      });
      node.parentNode.replaceChild(frag, node);
    });
  }

  function scanChips(scope) {
    var spans = (scope || document).querySelectorAll('.pk');
    for (var i = 0; i < spans.length; i++) chipify(spans[i]);
  }

  /* --- audio -------------------------------------------------------------
     One .m4a per utterance, fetched on demand and kept once decoded, in two
     sets: `words` for chips and `sentences` for example blocks.

     Not a sprite.  A sprite is right for a lesson, which plays many clips from
     a known set; the site plays one at a time, and pulling the whole corpus
     down to hear one word put six to fourteen seconds in front of the first
     tap, against 7-44 ms for a single file.

     Web Audio rather than <audio>: new Audio(url).play() has audible startup
     delay and gets flaky when tapped quickly. */

  var PLAY_GLYPH = '\u25B6';

  var audio = { ctx: null, index: {}, wanted: {}, buffers: {} };

  function loadIndex(kind) {
    if (!audio.wanted[kind]) {
      audio.wanted[kind] = fetch('/audio/' + kind + '.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (map) {
          audio.index[kind] = map && map.clips;
          return audio.index[kind];
        })
        .catch(function () { return null; });
    }
    return audio.wanted[kind];
  }

  function clipBuffer(kind, key) {
    var cached = audio.buffers[kind + ' ' + key];
    if (cached) return Promise.resolve(cached);
    return loadIndex(kind).then(function (index) {
      var clip = index && index[key];
      if (!clip) return null;
      return fetch('/audio/' + clip[0])
        .then(function (r) { return r.ok ? r.arrayBuffer() : null; })
        .then(function (bytes) {
          return bytes ? audio.ctx.decodeAudioData(bytes) : null;
        })
        .then(function (buffer) {
          if (buffer) audio.buffers[kind + ' ' + key] = buffer;
          return buffer;
        });
    }).catch(function () { return null; });
  }

  function play(kind, key, button) {
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    /* Created and resumed inside the click, which is the user gesture browsers
       require before any audio starts -- iOS wants it inside, not merely
       after. */
    if (!audio.ctx) audio.ctx = new Ctx();
    if (audio.ctx.state === 'suspended') audio.ctx.resume();

    button.classList.add('loading');
    clipBuffer(kind, key).then(function (buffer) {
      button.classList.remove('loading');
      if (!buffer) { button.disabled = true; return; }
      var source = audio.ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(audio.ctx.destination);
      source.start();
    });
  }

  /* --- sentence play buttons ---------------------------------------------
     A whole example, spoken as one utterance -- generated in a single Kokoro
     pass, not stitched from the word clips, which would come out as a robotic
     list with audible joins.

     The button sits beside the line rather than inside it: inside, it would be
     swept into the sentence's own aria-label and into anything copied. */

  function addSentencePlayers() {
    var lines = document.querySelectorAll('.example .pk');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.dataset.player) continue;
      var key = line.textContent.trim();
      if (key.split(/\s+/).length < 2) continue;
      line.dataset.player = '1';

      var row = document.createElement('div');
      row.className = 'example-line';
      line.parentNode.insertBefore(row, line);
      row.appendChild(line);

      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'example-speak';
      button.setAttribute('aria-label', 'Play the sentence');
      button.textContent = PLAY_GLYPH;
      (function (k, b) {
        b.addEventListener('click', function () { play('sentences', k, b); });
      })(key, button);
      row.appendChild(button);
    }
  }

  /* --- the popover ------------------------------------------------------- */

  var popover = null;
  var openFor = null;

  function closePopover() {
    if (popover) popover.hidden = true;
    if (openFor) openFor.setAttribute('aria-expanded', 'false');
    openFor = null;
  }

  function ensurePopover() {
    if (popover) return popover;
    popover = document.createElement('div');
    popover.className = 'wordpop';
    popover.hidden = true;
    popover.setAttribute('role', 'dialog');
    popover.tabIndex = -1;
    document.body.appendChild(popover);
    return popover;
  }

  /* Mnemonics are written with *asterisks* around the letters that echo the
     Pikotika form.  Build the <em>s as nodes -- the text is data, and this is
     not a place to hand a string to innerHTML. */
  function appendEmphasis(el, text) {
    text.split('*').forEach(function (chunk, i) {
      if (!chunk) return;
      if (i % 2) {
        var em = document.createElement('em');
        em.textContent = chunk;
        el.appendChild(em);
      } else {
        el.appendChild(document.createTextNode(chunk));
      }
    });
  }

  function fill(entry, form) {
    var el = ensurePopover();
    el.textContent = '';
    if (!entry) {
      /* The build checks every form, so this is a page that got ahead of its
         lexicon -- say so plainly rather than showing an empty box. */
      var none = document.createElement('p');
      none.className = 'wordpop-none';
      none.textContent = 'No entry for “' + form + '”.';
      el.appendChild(none);
      return;
    }

    var head = document.createElement('div');
    head.className = 'wordpop-head';
    var word = document.createElement('span');
    word.className = 'wordpop-form pk';
    word.textContent = entry.form;
    head.appendChild(word);
    if (entry.han) {
      var han = document.createElement('span');
      han.className = 'wordpop-han han';
      han.textContent = entry.han;
      head.appendChild(han);
    }
    el.appendChild(head);

    var en = document.createElement('p');
    en.className = 'wordpop-en';
    en.textContent = entry.en;
    el.appendChild(en);

    if (entry.parts) {
      /* The literal parse, with every root tappable in place: a compound is
         the one place a learner most wants to step sideways into its pieces. */
      var parse = document.createElement('p');
      parse.className = 'wordpop-parse';
      entry.parts.forEach(function (p, i) {
        if (i) parse.appendChild(document.createTextNode(' + '));
        var part = document.createElement('span');
        part.className = 'wordpop-part pk';
        /* Already a control; keep scanChips from chipping it into another. */
        part.dataset.check = 'off';
        part.setAttribute('role', 'button');
        part.tabIndex = 0;
        part.dataset.w = p.form.toLowerCase();
        part.textContent = p.form;
        parse.appendChild(part);
        var g = document.createElement('span');
        g.className = 'wordpop-partgloss gloss';
        g.textContent = ' (' + p.gloss + ')';
        parse.appendChild(g);
      });
      el.appendChild(parse);
    } else if (entry.mnemonic) {
      var hint = document.createElement('p');
      hint.className = 'wordpop-mnemonic';
      appendEmphasis(hint, entry.mnemonic);
      el.appendChild(hint);
    }

    var foot = document.createElement('div');
    foot.className = 'wordpop-foot';

    var speak = document.createElement('button');
    speak.type = 'button';
    speak.className = 'wordpop-speak';
    speak.setAttribute('aria-label', 'Play ' + entry.form);
    speak.textContent = PLAY_GLYPH;
    speak.addEventListener('click', function () {
      play('words', entry.form.toLowerCase(), speak);
    });
    foot.appendChild(speak);

    if (entry.level) {
      var level = document.createElement('span');
      level.className = 'wordpop-level';
      level.textContent = 'Level ' + entry.level;
      foot.appendChild(level);
    }

    var link = document.createElement('a');
    link.className = 'wordpop-link';
    link.href = '/vocab/#' + encodeURIComponent(entry.form.toLowerCase());
    link.textContent = 'Full entry';
    foot.appendChild(link);

    el.appendChild(foot);
  }

  function place(button) {
    var el = ensurePopover();
    el.hidden = false;
    /* Measure after it is visible and laid out, then keep it on screen. */
    var rect = button.getBoundingClientRect();
    var box = el.getBoundingClientRect();
    var margin = 8;
    var left = rect.left + rect.width / 2 - box.width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - box.width - margin));
    var top = rect.bottom + margin;
    if (top + box.height > window.innerHeight - margin && rect.top > box.height) {
      top = rect.top - box.height - margin;
    }
    el.style.left = (left + window.scrollX) + 'px';
    el.style.top = (top + window.scrollY) + 'px';
  }

  /* Show `form` in the popover anchored at `anchor`.  Stepping from a compound
     into one of its roots keeps the anchor -- the box stays where the reader is
     already looking, and the chip that opened it stays the one marked open. */
  function showFor(form, anchor) {
    loadLexicon().then(function (data) {
      if (openFor !== anchor) return;
      fill(data && data.words && data.words[form], form);
      place(anchor);
    });
  }

  function openChip(button) {
    if (openFor === button) { closePopover(); return; }
    closePopover();
    openFor = button;
    button.setAttribute('aria-expanded', 'true');
    showFor(button.dataset.w, button);
  }

  document.addEventListener('click', function (event) {
    var chip = event.target.closest && event.target.closest('.pk .w');
    if (chip) {
      /* A click that ends a drag-selection is a selection, not a tap. */
      var selection = window.getSelection();
      if (selection && !selection.isCollapsed &&
          selection.toString().trim().length > 1) return;
      event.preventDefault();
      openChip(chip);
      return;
    }
    var part = event.target.closest && event.target.closest('.wordpop-part');
    if (part && openFor) {
      /* fill() rebuilds the box, so the element just activated is about to stop
         existing; park focus on the popover so the keyboard stays inside it. */
      event.preventDefault();
      showFor(part.dataset.w, openFor);
      popover.focus();
      return;
    }
    if (popover && !popover.hidden && !event.target.closest('.wordpop')) {
      closePopover();
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closePopover(); return; }
    /* role="button" buys the semantics but not the behavior: a span is not
       activated by the keyboard unless we do it. */
    if (event.key === 'Enter' || event.key === ' ') {
      var chip = event.target.closest && event.target.closest('.pk .w');
      if (chip) {
        event.preventDefault();
        openChip(chip);
        return;
      }
      var part = event.target.closest && event.target.closest('.wordpop-part');
      if (part && openFor) {
        event.preventDefault();
        showFor(part.dataset.w, openFor);
        popover.focus();
      }
    }
  });

  window.addEventListener('resize', closePopover);


  /* --- Vocab (/vocab/) ----------------------------------------------------
     The whole section is one page over one JSON file.  613 entries is small
     enough that filtering them on every keystroke is free, so there is no
     index, no server, and no pagination -- and the page keeps working offline
     once the lexicon is cached.

     Entries expand in place rather than navigating: the permalink /vocab/#riso
     opens one, and opening one writes the hash back, so a link into a word and
     a click on a word end up in the same state. */

  var KINDS = [
    ['all', 'All', null],
    /* A particle is a root you cannot compound; it belongs with the roots and
       nobody looking for one thinks of it as a separate kind. */
    ['root', 'Roots', ['root', 'particle']],
    /* "phrase" is a compound a page wrote in running speech rather than one
       standing in compounds.tsv; the reader has no use for that distinction. */
    ['compound', 'Compounds', ['compound', 'phrase']],
    ['name', 'Names', ['name']],
    ['loan', 'Loans', ['loan']]
  ];

  var KIND_LABEL = {
    root: 'root', particle: 'particle', compound: 'compound',
    phrase: 'compound', name: 'name', loan: 'loan'
  };

  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function initVocab() {
    var page = document.getElementById('vocab');
    if (!page) return;

    var input = document.getElementById('vocab-q');
    var kindRow = document.getElementById('vocab-kinds');
    var catRow = document.getElementById('vocab-cats');
    var countEl = document.getElementById('vocab-count');
    var results = document.getElementById('vocab-results');
    var controls = page.querySelector('.vocab-controls');

    /* The controls stick under the site header, whose height is two rows on a
       narrow screen and one on a wide one.  Measuring beats hard-coding it in
       two media queries that would then have to be kept in step. */
    function stick() {
      var header = document.getElementById('site-header');
      if (header && controls) controls.style.top = header.offsetHeight + 'px';
    }
    stick();
    window.addEventListener('resize', stick);

    var data = null;
    var kind = 'all';
    var category = '';
    var query = '';
    var open = '';

    /* -- matching -------------------------------------------------------- */

    /* A score, or 0 for no match.  The ranking is the useful part: someone who
       types "riso" wants the word riso first, and someone who types "rice"
       wants riso too -- it is in the root's `covers` list even though the gloss
       is *grain*, which is exactly the case the design brief calls out. */
    function score(entry, q) {
      var form = entry.form.toLowerCase();
      if (form === q) return 100;
      if (entry.han && entry.han.indexOf(q) >= 0) return 95;
      if (form.indexOf(q) === 0) return 85;

      var word = new RegExp('(^|[^a-z0-9])' + escapeRe(q));
      var best = 0;
      var fields = [entry.en, entry.gloss, entry.gloss2, entry.covers];
      for (var i = 0; i < fields.length; i++) {
        var text = (fields[i] || '').toLowerCase();
        if (!text) continue;
        if (text === q) best = Math.max(best, 90);
        else if (word.test(text)) best = Math.max(best, 70);
      }
      /* English matches only at a word boundary: *price* contains *rice*, and
         a search for rice that turns up **moni** is worse than no result.  The
         Latin form is the opposite case -- compounds are written solid, so
         "riso" has to find **yororiso** by plain substring. */
      if (!best && form.indexOf(q) >= 0) best = 30;
      return best;
    }

    function inKind(entry) {
      var want = null;
      for (var i = 0; i < KINDS.length; i++) {
        if (KINDS[i][0] === kind) want = KINDS[i][2];
      }
      if (!want) return true;
      return want.indexOf(entry.kind) >= 0;
    }

    function inCategory(entry) {
      if (!category) return true;
      return entry.cat === category;
    }

    function all() {
      var out = [];
      for (var form in data.words) out.push(data.words[form]);
      out.sort(function (a, b) {
        return a.form.toLowerCase() < b.form.toLowerCase() ? -1 : 1;
      });
      return out;
    }

    /* -- the two list shapes --------------------------------------------- */

    function searched(q) {
      var hits = [];
      var list = all();
      for (var i = 0; i < list.length; i++) {
        if (!inKind(list[i]) || !inCategory(list[i])) continue;
        var s = score(list[i], q);
        if (s) hits.push([s, list[i]]);
      }
      hits.sort(function (a, b) {
        if (a[0] !== b[0]) return b[0] - a[0];
        return a[1].form.toLowerCase() < b[1].form.toLowerCase() ? -1 : 1;
      });
      return hits.map(function (h) { return h[1]; });
    }

    /* With nothing typed the page is a table of contents rather than a wall:
       roots under their `category` headings in table order, then the other
       kinds under their own.  A dictionary you can read down is worth more on
       arrival than an empty box. */
    function browsed() {
      var list = all();
      var groups = [];
      var index = {};

      function group(title) {
        if (!index[title]) {
          index[title] = { title: title, items: [] };
          groups.push(index[title]);
        }
        return index[title];
      }

      var cats = data.categories || [];
      for (var c = 0; c < cats.length; c++) {
        if (kind === 'all' || kind === 'root') {
          if (!category || category === cats[c]) group(cats[c]);
        }
      }

      for (var i = 0; i < list.length; i++) {
        var entry = list[i];
        if (!inKind(entry) || !inCategory(entry)) continue;
        var isRoot = entry.kind === 'root' || entry.kind === 'particle';
        if (isRoot) group(entry.cat || 'Uncategorized').items.push(entry);
        else if (category) continue;
        else group(KIND_LABEL[entry.kind] === 'compound' ? 'Compounds' :
                   entry.kind === 'loan' ? 'Loans' : 'Names').items.push(entry);
      }

      return groups.filter(function (g) { return g.items.length; });
    }

    /* -- rendering -------------------------------------------------------- */

    function relatedChip(form, label) {
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'vocab-rel pk';
      /* Already a control, and scanChips runs over this panel; opt it out or
         the word inside gets chipped into a button within a button. */
      chip.dataset.check = 'off';
      chip.textContent = label || form;
      chip.addEventListener('click', function () { go(form); });
      return chip;
    }

    function detail(entry) {
      var box = document.createElement('div');
      box.className = 'vocab-detail';

      /* The row above already carries form, Han and English; repeating them
         here made the open entry read as the same line twice.  What the detail
         opens with instead is what the row could not fit. */
      var head = document.createElement('div');
      head.className = 'vocab-dhead';
      var speak = document.createElement('button');
      speak.type = 'button';
      speak.className = 'wordpop-speak';
      speak.setAttribute('aria-label', 'Play ' + entry.form);
      speak.textContent = PLAY_GLYPH;
      speak.addEventListener('click', function () {
        play('words', entry.form.toLowerCase(), speak);
      });
      head.appendChild(speak);

      var meta = [];
      if (entry.strokes) meta.push(entry.strokes + ' strokes');
      if (entry.cat) meta.push(entry.cat);
      if (entry.level) meta.push('Level ' + entry.level);
      meta.push(KIND_LABEL[entry.kind] || entry.kind);
      var metaEl = document.createElement('span');
      metaEl.className = 'vocab-dmeta';
      metaEl.textContent = meta.join(' · ');
      head.appendChild(metaEl);
      box.appendChild(head);

      if (entry.parts) {
        var parse = document.createElement('p');
        parse.className = 'vocab-parse';
        entry.parts.forEach(function (p, i) {
          if (i) parse.appendChild(document.createTextNode(' + '));
          parse.appendChild(relatedChip(p.form));
          var g = document.createElement('span');
          g.className = 'gloss';
          g.textContent = ' (' + p.gloss + ')';
          parse.appendChild(g);
        });
        box.appendChild(parse);
      }

      if (entry.covers) {
        box.appendChild(field('Covers', entry.covers));
      }
      if (entry.mnemonic) {
        /* Labelled and set like Covers above it -- in the popover the mnemonic
           is the only aside and needs no label, but here it is one line among
           several and an unlabelled one reads as a stray sentence. */
        var hint = document.createElement('p');
        hint.className = 'vocab-dfield';
        var label = document.createElement('span');
        label.className = 'vocab-dlabel';
        label.textContent = 'Mnemonic: ';
        hint.appendChild(label);
        appendEmphasis(hint, entry.mnemonic);
        box.appendChild(hint);
      }

      if (entry['in'] && entry['in'].length) {
        var used = document.createElement('div');
        used.className = 'vocab-section';
        used.appendChild(heading('Used in ' + entry['in'].length +
                                 (entry['in'].length === 1 ? ' compound'
                                                           : ' compounds')));
        var row = document.createElement('p');
        row.className = 'vocab-rels';
        entry['in'].forEach(function (form, i) {
          if (i) row.appendChild(document.createTextNode(' '));
          row.appendChild(relatedChip(form));
        });
        used.appendChild(row);
        box.appendChild(used);
      }

      if (entry.ex && entry.ex.length) {
        box.appendChild(sentences(entry.ex));
      }

      var link = document.createElement('p');
      link.className = 'vocab-dlink';
      var a = document.createElement('a');
      a.href = '/vocab/#' + encodeURIComponent(entry.form.toLowerCase());
      a.textContent = 'Permalink';
      link.appendChild(a);
      box.appendChild(link);

      return box;
    }

    /* **ri** is in 279 corpus sentences and **eko** in 133.  Printing them all
       turns the commonest words -- the ones a beginner opens first -- into the
       longest pages on the site, so the list opens at a readable length and
       says plainly how much more there is. */
    var SENTENCES_SHOWN = 8;

    function example(line) {
      /* .example is the markup the rest of the site uses, so chipping and the
         sentence play button both come for free. */
      var ex = document.createElement('div');
      ex.className = 'example';
      var english = document.createElement('p');
      english.className = 'en';
      english.textContent = line[1];
      ex.appendChild(english);
      var pk = document.createElement('span');
      pk.className = 'pk';
      pk.textContent = line[0];
      ex.appendChild(pk);
      return ex;
    }

    function sentences(indexes) {
      var section = document.createElement('div');
      section.className = 'vocab-section';
      section.appendChild(heading(
        indexes.length === 1 ? 'In 1 sentence'
                             : 'In ' + indexes.length + ' sentences'));

      var shown = 0;
      function add(upTo) {
        for (; shown < upTo && shown < indexes.length; shown++) {
          var line = data.sentences[indexes[shown]];
          if (line) section.insertBefore(example(line), rest);
        }
      }

      var rest = document.createElement('p');
      rest.className = 'vocab-more';
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'vocab-morebtn';
      button.textContent = 'Show the other ' +
        (indexes.length - SENTENCES_SHOWN) + '';
      button.addEventListener('click', function () {
        add(indexes.length);
        rest.remove();
        scanChips(section);
        addSentencePlayers();
      });
      rest.appendChild(button);
      section.appendChild(rest);

      add(SENTENCES_SHOWN);
      if (indexes.length <= SENTENCES_SHOWN) rest.remove();
      return section;
    }

    function heading(text) {
      var h = document.createElement('h3');
      h.className = 'vocab-dh';
      h.textContent = text;
      return h;
    }

    function field(label, value) {
      var p = document.createElement('p');
      p.className = 'vocab-dfield';
      var b = document.createElement('span');
      b.className = 'vocab-dlabel';
      b.textContent = label + ': ';
      p.appendChild(b);
      p.appendChild(document.createTextNode(value));
      return p;
    }

    function rowFor(entry) {
      var li = document.createElement('li');
      li.className = 'vocab-row';
      li.id = 'v-' + entry.form.toLowerCase();

      var head = document.createElement('button');
      head.type = 'button';
      head.className = 'vocab-head';
      head.setAttribute('aria-expanded', 'false');

      var form = document.createElement('span');
      form.className = 'vocab-form pk';
      form.textContent = entry.form;
      head.appendChild(form);

      var han = document.createElement('span');
      han.className = 'vocab-han han';
      han.textContent = entry.han || '';
      head.appendChild(han);

      var en = document.createElement('span');
      en.className = 'vocab-en';
      en.textContent = entry.en;
      head.appendChild(en);

      head.addEventListener('click', function () {
        /* Expanding a row does not rewrite the hash -- the hash is the search,
           and opening one of its results is not a different search.  The entry's
           own Permalink is what links to it opened. */
        open = open === entry.form.toLowerCase() ? '' : entry.form.toLowerCase();
        render();
      });
      li.appendChild(head);

      if (open === entry.form.toLowerCase()) {
        li.classList.add('is-open');
        head.setAttribute('aria-expanded', 'true');
        var box = detail(entry);
        li.appendChild(box);
        /* chipify works on a detached node; addSentencePlayers queries the
           document, so it has to wait until render() has appended the list. */
        scanChips(box);
      }
      return li;
    }

    function render() {
      results.textContent = '';
      if (!data) { countEl.textContent = 'Loading the lexicon…'; return; }

      var groups = query ? [{ title: '', items: searched(query) }] : browsed();
      var total = 0;
      groups.forEach(function (g) { total += g.items.length; });

      countEl.textContent = total === 0
        ? (query ? 'Nothing matches “' + query + '”.' : 'Nothing in this filter.')
        : total + (total === 1 ? ' entry' : ' entries');

      groups.forEach(function (g) {
        var section = document.createElement('section');
        section.className = 'vocab-group';
        if (g.title) {
          var h = document.createElement('h2');
          h.className = 'vocab-gh';
          h.textContent = g.title;
          section.appendChild(h);
        }
        var list = document.createElement('ul');
        list.className = 'vocab-list';
        g.items.forEach(function (entry) { list.appendChild(rowFor(entry)); });
        section.appendChild(list);
        results.appendChild(section);
      });
      addSentencePlayers();
    }

    /* -- state ------------------------------------------------------------ */

    /* **The hash is the search box.**  `/vocab/#riso` is the search for riso,
       and typing a search writes itself back, so a link and a search can never
       describe two different pages.  Showing the whole lexicon and merely
       scrolling to the linked word was more confusing than searching for it.

       A hash that names a word exactly also opens that word, which is what
       makes a permalink land on the entry rather than beside it. */
    function setHash(text) {
      var next = text ? '#' + encodeURIComponent(text) : '';
      if ((location.hash || '') === next) return;
      /* replaceState, not a push: a reader stepping through six compounds
         should not have to press Back six times.  It also does not fire
         hashchange, so writing the hash cannot loop back into reading it. */
      history.replaceState(null, '', location.pathname + next);
    }

    function fromHash() {
      var raw = location.hash.replace(/^#/, '');
      if (!raw) return '';
      try { return decodeURIComponent(raw); }
      catch (e) { return raw; }
    }

    /* The query can no longer hide the open word -- it is the open word -- but
       a kind or category chip still can. */
    function reveal(form) {
      if (!data || !data.words[form]) return;
      if (document.getElementById('v-' + form)) return;
      kind = 'all';
      category = '';
      drawChips();
      render();
    }

    function show(scroll) {
      render();
      if (!open) return;
      reveal(open);
      var el = document.getElementById('v-' + open);
      /* Not smooth: an entry can be far down the browse list, and animating
         that is a long blank ride.  Aligned to the top rather than centered,
         since an open entry can be taller than the viewport and its head is the
         part you came for -- offset by the two sticky bars, which is why the
         margin is measured here. */
      if (el && scroll) {
        var header = document.getElementById('site-header');
        el.style.scrollMarginTop = ((header ? header.offsetHeight : 0) +
                                    (controls ? controls.offsetHeight : 0) +
                                    8) + 'px';
        el.scrollIntoView({ block: 'start' });
      }
    }

    /* Read the URL into the page: the one path used on load, on hashchange, and
       after a related word is tapped. */
    function fromUrl(scroll) {
      var raw = fromHash();
      input.value = raw;
      query = raw.trim().toLowerCase();
      open = (data && data.words[query]) ? query : '';
      show(scroll);
    }

    /* Tapping a root inside a compound, or a compound in "used in", searches
       for it -- the same state its permalink would produce. */
    function go(form) {
      setHash(form || '');
      fromUrl(true);
    }

    /* -- the chip rows ---------------------------------------------------- */

    function chips(row, items, current, onPick) {
      row.textContent = '';
      items.forEach(function (item) {
        var chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'vocab-chip';
        chip.textContent = item[1];
        chip.setAttribute('aria-pressed', item[0] === current ? 'true' : 'false');
        chip.addEventListener('click', function () { onPick(item[0]); });
        row.appendChild(chip);
      });
    }

    function drawChips() {
      chips(kindRow, KINDS.map(function (k) { return [k[0], k[1]]; }), kind,
            function (value) {
              kind = value;
              if (kind !== 'all' && kind !== 'root') category = '';
              drawChips();
              render();
            });

      /* Categories are a property of roots, so the row is only up when roots
         are in scope at all. */
      var cats = [['', 'All categories']].concat(
        (data && data.categories || []).map(function (c) { return [c, c]; }));
      var showCats = data && (kind === 'all' || kind === 'root');
      catRow.hidden = !showCats;
      if (showCats) {
        chips(catRow, cats, category, function (value) {
          category = value;
          drawChips();
          render();
        });
      }
    }

    input.addEventListener('input', function () {
      query = input.value.trim().toLowerCase();
      /* Typing is not arriving: do not pop an entry open under the cursor just
         because what you have typed so far happens to spell a word. */
      open = '';
      setHash(input.value.trim());
      render();
    });

    window.addEventListener('hashchange', function () { fromUrl(true); });

    drawChips();
    countEl.textContent = 'Loading the lexicon…';

    loadLexicon().then(function (payload) {
      if (!payload || !payload.words) {
        countEl.textContent = 'The lexicon did not load.';
        return;
      }
      data = payload;
      drawChips();
      /* The row does not exist until the fetch lands, by which time the browser
         has already restored its own scroll position -- which is the top, since
         the page it restored was empty.  Take the wheel. */
      if (fromHash()) { try { history.scrollRestoration = 'manual'; } catch (e) {} }
      fromUrl(true);
    });
  }

  scanChips();
  addSentencePlayers();
  initVocab();

  /* Pages that build their own markup -- Vocab results, the Tools converter --
     add .pk elements after this ran, so they need a way to chip them. */
  window.pikotika = window.pikotika || {};
  window.pikotika.scanChips = scanChips;
  window.pikotika.addSentencePlayers = addSentencePlayers;
})();
