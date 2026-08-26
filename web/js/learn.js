/* The course: the flashcard deck, and the marks on the course map.

   Loaded on /learn/ and on every lesson page.  The lesson content itself is
   in the HTML -- new words, meanings, the page to go read -- so this file is
   only the drill and the progress marks, and the page is complete without it.

   Why a self-graded card and not a checked one (decided 2026-08-26).  The
   value of a flashcard is that it is *fast*: prompt, spacebar, did I get it,
   next -- a few seconds each, and a deck clears in a couple of minutes.  As
   soon as the learner has to drag tiles into place, a card costs half a
   minute and the deck becomes a chore.  Worse, a tile bank hands back the
   recall the card was there to drive: picking `pomo` out of six tiles is
   recognition wearing production's clothes.  So the card asks for the answer
   out loud, unaided, and then shows it.  Nobody is marking, and nobody needs
   to be -- a learner drilling alone has no reason to cheat.

   The queue is Leitner, confined to the sitting: a card leaves when it has
   been got right twice running, and a miss sends it back to zero.  There is
   no cross-session scheduler on purpose (GAME_DESIGN.md): a visitor who comes
   back in a month should meet a lesson, not a debt.

   `Deck` is deliberately free of the DOM so tests/learn_test.js can run it
   under node -- the scheduling is the part with rules in it, and the part a
   browser cannot check for us. */

(function () {
  'use strict';

  /* --- the queue ---------------------------------------------------------
     A card is done at HITS_TO_CLEAR correct answers in a row.  The gaps are
     how far back a card goes: far enough that the answer is not still on
     screen, near enough that it comes round again inside the sitting. */

  var HITS_TO_CLEAR = 2;
  var GAP_HIT = 5;            /* right, but not yet cleared */
  var GAP_MISS = 2;           /* wrong: comes back soon, and from zero */

  /* Which way round a card is asked.  A card is one item, not two, and it
     flips every time it is dealt (decided 2026-08-26): production and
     recognition are the same word seen from either side, and a deck twice as
     long to cover both would be a chore rather than a couple of minutes.
     Clearing still takes two right answers, so a card that clears has been
     had in both directions. */
  var EN_TO_PK = 'en2pk';
  var PK_TO_EN = 'pk2en';

  function Deck(cards) {
    this.total = cards.length;
    this.cleared = 0;
    this.queue = cards.map(function (card) {
      /* Every card opens asking for production -- the harder direction, and
         the one the learner has just read the answer to on the page above. */
      return { card: card, hits: 0, shown: 0 };
    });
  }

  Deck.prototype.current = function () {
    return this.queue.length ? this.queue[0].card : null;
  };

  /* The direction the front card will be asked in next. */
  Deck.prototype.direction = function () {
    if (!this.queue.length) return null;
    return this.queue[0].shown % 2 ? PK_TO_EN : EN_TO_PK;
  };

  /* Deal the front card: returns it with the direction to ask it in, and
     counts the showing so the next deal of the same card is the other way
     round.  Called once per card presented, which is what makes the flip
     alternate rather than depend on how the render happened to run. */
  Deck.prototype.present = function () {
    if (!this.queue.length) return null;
    var entry = this.queue[0];
    var dir = this.direction();
    entry.shown += 1;
    return { card: entry.card, dir: dir };
  };

  Deck.prototype.done = function () {
    return this.queue.length === 0;
  };

  /* Fraction cleared, for the bar.  Counting cleared cards rather than
     answers keeps the bar honest: answering wrong four times in a row should
     not look like progress. */
  Deck.prototype.progress = function () {
    return this.total ? this.cleared / this.total : 1;
  };

  Deck.prototype.answer = function (ok) {
    if (!this.queue.length) return null;
    var entry = this.queue.shift();
    entry.hits = ok ? entry.hits + 1 : 0;
    if (ok && entry.hits >= HITS_TO_CLEAR) {
      this.cleared += 1;
      return entry.card;
    }
    /* Past the end of a short queue means straight back to the front, which
       is right: with two cards left there is nowhere else to put it. */
    var gap = ok ? GAP_HIT : GAP_MISS;
    this.queue.splice(Math.min(gap, this.queue.length), 0, entry);
    return entry.card;
  };

  /* One export object, reached as `window.pikotikaLearn` in the browser and
     as the module in node.  `runDeck` is added to it at the bottom, once the
     DOM half has been defined, so tests/deck_dom_test.js can drive a whole
     sitting without a browser. */
  var api = { Deck: Deck, HITS_TO_CLEAR: HITS_TO_CLEAR,
              EN_TO_PK: EN_TO_PK, PK_TO_EN: PK_TO_EN };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.pikotikaLearn = api;
  if (typeof document === 'undefined') return;

  /* --- progress ----------------------------------------------------------
     The only thing that persists, and it is a courtesy rather than a
     mechanism: nothing is ever locked, so a cleared store costs the learner
     a row of checkmarks and nothing else. */

  var STORE = 'pk-learn-done';

  function loadDone() {
    var raw;
    try { raw = localStorage.getItem(STORE); } catch (e) { return {}; }
    if (!raw) return {};
    try {
      var parsed = JSON.parse(raw);
      return (parsed && typeof parsed === 'object') ? parsed : {};
    } catch (e) { return {}; }
  }

  function markDone(id) {
    var done = loadDone();
    done[id] = 1;
    try { localStorage.setItem(STORE, JSON.stringify(done)); } catch (e) {}
  }

  /* --- the course map ---------------------------------------------------- */

  function initMap() {
    var map = document.querySelector('.course-map');
    if (!map) return;
    var done = loadDone();
    var items = map.querySelectorAll('.course-lesson');
    var resumeTo = null;
    for (var i = 0; i < items.length; i++) {
      var id = items[i].dataset.lesson;
      if (done[id]) {
        items[i].classList.add('is-done');
      } else if (!resumeTo) {
        resumeTo = items[i].querySelector('a');
      }
    }
    var box = document.querySelector('.learn-resume');
    if (!box) return;
    var link = box.querySelector('a');
    var anyDone = Object.keys(done).length > 0;
    if (resumeTo) {
      link.href = resumeTo.getAttribute('href');
      link.textContent = anyDone ? 'Continue' : 'Start';
    } else {
      link.href = items.length ? items[0].querySelector('a').getAttribute('href') : '/learn/';
      link.textContent = 'Start again';
    }
    box.hidden = false;
  }

  /* --- the deck ---------------------------------------------------------- */

  /* What the card asks, by content type and direction. */
  var PROMPTS = {
    word: { en2pk: 'Say it in Pikotika', pk2en: 'What does this mean?' },
    sent: { en2pk: 'Say the whole sentence in Pikotika',
            pk2en: 'What does this sentence mean?' }
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  /* A button, and the key it answers to as a hover tag.

     The shortcuts are the whole reason the deck is fast, so they have to be
     discoverable -- but printed on the buttons they were three more things to
     read on a screen whose whole job is one prompt.  A tooltip is the right
     weight: there for whoever looks, gone otherwise.  `aria-keyshortcuts`
     carries the same fact to a screen reader, which cannot hover. */
  function withKey(button, label, key, shortcut) {
    button.textContent = label;
    button.setAttribute('title', key);
    button.setAttribute('aria-keyshortcuts', shortcut);
    return button;
  }

  function initDeck() {
    var mount = document.querySelector('.lesson-deck');
    if (!mount) return;
    var id = mount.dataset.lesson;
    var version = (window.pikotika && window.pikotika.dataVersion) || '';

    fetch('/data/lessons.json' + (version ? '?v=' + version : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var lesson = null;
        for (var i = 0; i < data.lessons.length; i++) {
          if (data.lessons[i].id === id) { lesson = data.lessons[i]; break; }
        }
        if (lesson) runDeck(mount, lesson);
      })
      .catch(function () { /* The words above are the lesson without us. */ });
  }

  function runDeck(mount, lesson) {
    var deck = null;
    var revealed = false;

    var start = el('button', 'button deck-start',
                   'Start — ' + lesson.cards.length + ' cards');
    mount.appendChild(start);

    var box = el('div', 'deck');
    box.hidden = true;
    mount.appendChild(box);

    /* The finished screen is a sibling that is shown, not markup that
       replaces the deck: rebuilding the deck would mean rebuilding its
       keyboard handler too, and a second run would then grade every card
       twice. */
    var body = el('div', 'deck-body');
    var endPanel = el('div', 'deck-end');
    endPanel.hidden = true;

    var bar = el('div', 'deck-bar');
    var fill = el('div', 'deck-fill');
    bar.appendChild(fill);
    var count = el('p', 'deck-count');

    var card = el('div', 'deck-card');
    var kind = el('p', 'deck-kind');
    var prompt = el('div', 'deck-prompt');
    var answer = el('div', 'deck-answer');
    answer.hidden = true;
    card.appendChild(kind);
    card.appendChild(prompt);
    card.appendChild(answer);

    var controls = el('div', 'deck-controls');
    var reveal = withKey(el('button', 'button deck-reveal'),
                         'Show answer', 'Spacebar', 'Space');
    var miss = withKey(el('button', 'deck-grade deck-miss'),
                       '\u2717  Missed', 'Left arrow', 'ArrowLeft');
    var hit = withKey(el('button', 'deck-grade deck-hit'),
                      '\u2713  Got it', 'Right arrow', 'ArrowRight');
    miss.hidden = hit.hidden = true;
    controls.appendChild(reveal);
    controls.appendChild(miss);
    controls.appendChild(hit);

    body.appendChild(bar);
    body.appendChild(count);
    body.appendChild(card);
    body.appendChild(controls);
    box.appendChild(body);
    box.appendChild(endPanel);

    var here = null;        /* the card as dealt: {card, dir} */

    function speak() {
      if (!window.pikotika || !window.pikotika.playWord || !here) return;
      window.pikotika.playWord(here.card.form,
                               here.card.k === 'sent' ? 'sentences' : 'words');
    }

    /* The card's third line: a root's mnemonic, a compound's parse, a
       sentence's gloss.  It shows on both directions, because the cards are
       the only place on the site a learner meets the mnemonics and a card is
       exactly when one is wanted.  The `*asterisks*` are read by site.js's
       own renderer rather than a second copy of it here. */
    function hintLine(card) {
      var line = el('p', 'deck-hint');
      if (window.pikotika && window.pikotika.appendEmphasis) {
        window.pikotika.appendEmphasis(line, card.hint);
      } else {
        line.textContent = card.hint.replace(/\*/g, '');
      }
      return line;
    }

    /* The Pikotika side of a card.  On the *answer* it is chipped, so a tap
       opens the entry; on the *prompt* it deliberately is not, because the
       chip's popover shows the gloss, which on that card is the answer. */
    function pikotikaSide(card, asAnswer) {
      var box = document.createDocumentFragment();
      box.appendChild(el('span', 'pk deck-word', card.form));
      if (asAnswer) box.appendChild(el('p', 'han deck-han', card.han));
      return box;
    }

    function draw() {
      here = deck.present();
      if (!here) return finish();
      var card = here.card;
      kind.textContent = (PROMPTS[card.k] || PROMPTS.word)[here.dir];
      prompt.textContent = '';
      answer.textContent = '';
      answer.hidden = true;
      revealed = false;
      reveal.hidden = false;
      miss.hidden = hit.hidden = true;

      if (here.dir === 'pk2en') {
        prompt.appendChild(pikotikaSide(card, false));
        answer.appendChild(el('p', 'deck-en', card.en));
      } else {
        prompt.appendChild(el('p', 'deck-en', card.en));
        answer.appendChild(pikotikaSide(card, true));
      }
      answer.appendChild(hintLine(card));

      var pct = Math.round(deck.progress() * 100);
      fill.style.width = pct + '%';
      count.textContent = deck.cleared + ' of ' + deck.total + ' cleared';
      reveal.focus();
    }

    function show() {
      if (revealed) return;
      revealed = true;
      answer.hidden = false;
      reveal.hidden = true;
      miss.hidden = hit.hidden = false;
      /* Chips on the answer, never on the prompt -- see draw(). */
      if (window.pikotika && window.pikotika.scanChips) {
        window.pikotika.scanChips(answer);
      }
      speak();
      hit.focus();
    }

    function grade(ok) {
      if (!revealed) return;
      deck.answer(ok);
      draw();
    }

    function finish() {
      markDone(lesson.id);
      body.hidden = true;
      endPanel.hidden = false;
      endPanel.textContent = '';
      endPanel.appendChild(el('p', 'deck-done',
                              'Deck cleared \u2014 ' + deck.total + ' cards.'));
      var again = el('button', 'button deck-again', 'Run it again');
      again.addEventListener('click', function () {
        deck = new Deck(lesson.cards);
        endPanel.hidden = true;
        body.hidden = false;
        draw();
      });
      endPanel.appendChild(again);
      /* The course's own prev/next strip is already on the page, so the way
         onward is a copy of that link rather than a second idea of where the
         next lesson is. */
      var next = document.querySelector('.grammar-next');
      if (next) {
        var link = el('a', 'button deck-next', 'Next lesson \u2192');
        link.href = next.getAttribute('href');
        endPanel.appendChild(link);
      }
    }

    start.addEventListener('click', function () {
      deck = new Deck(lesson.cards);
      start.hidden = true;
      box.hidden = false;
      /* The click that starts the deck is also the gesture that unlocks the
         AudioContext, which is why the deck has a start button at all. */
      draw();
    });

    reveal.addEventListener('click', show);
    hit.addEventListener('click', function () { grade(true); });
    miss.addEventListener('click', function () { grade(false); });

    document.addEventListener('keydown', function (event) {
      if (box.hidden || body.hidden || !deck || deck.done()) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      var tag = (event.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault();
        /* Space turns the card over and does nothing else.  It used to double
           as "got it", which made the deck one key -- and made a doubled
           space, which is an easy thing to do on a keyboard, silently claim a
           card the learner had not even looked at yet.  Grading is the arrows
           now, deliberately a different key from the one that reveals. */
        if (!revealed) show();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        if (revealed) grade(true);
      } else if (event.key === 'ArrowLeft' || event.key === 'x' ||
                 event.key === 'X') {
        event.preventDefault();
        if (revealed) grade(false);
      } else if (event.key === 'r' || event.key === 'R') {
        event.preventDefault();
        if (revealed) speak();
      }
    });
  }

  api.runDeck = runDeck;
  api.initMap = initMap;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initMap();
      initDeck();
    });
  } else {
    initMap();
    initDeck();
  }
})();
