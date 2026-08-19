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
        .then(function (data) { lexicon = data && data.words; return lexicon; })
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
    loadLexicon().then(function (words) {
      if (openFor !== anchor) return;
      fill(words && words[form], form);
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

  scanChips();
  addSentencePlayers();

  /* Pages that build their own markup -- Vocab results, the Tools converter --
     add .pk elements after this ran, so they need a way to chip them. */
  window.pikotika = window.pikotika || {};
  window.pikotika.scanChips = scanChips;
  window.pikotika.addSentencePlayers = addSentencePlayers;
})();
