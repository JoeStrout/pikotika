/* A sitting at the deck, driven without a browser — web/js/learn.js.
 *
 *     node tests/deck_dom_test.js
 *
 * tests/learn_test.js covers the queue, which is pure.  This covers the
 * wiring around it: that starting shows a card, that turning one over shows
 * the answer and not before, that grading advances, that finishing marks the
 * lesson done, and that running the deck a second time does not grade every
 * card twice.  Those are the bugs that live in the part of learn.js a browser
 * would otherwise be the only witness to.
 *
 * The DOM here is a shim of about a hundred lines, not jsdom: the site takes
 * no npm dependencies, and the alternative to a shim is no test at all.  Be
 * clear about what that buys.  It proves the *wiring* — which handler fires,
 * what gets shown and hidden, what is written to storage.  It proves nothing
 * about rendering, layout, focus behavior, or the audio unlock, all of which
 * still want a real browser and a person.
 */

'use strict';

var path = require('path');

/* --- the shim ------------------------------------------------------------ */

function Node(tag) {
  this.tagName = (tag || 'div').toUpperCase();
  this.children = [];
  this.parentNode = null;
  this.className = '';
  this.hidden = false;
  this.style = {};
  this.dataset = {};
  this.attrs = {};
  this._text = '';
  this.listeners = {};
  var self = this;
  this.classList = {
    add: function (c) {
      var have = self.className.split(/\s+/).filter(Boolean);
      if (have.indexOf(c) < 0) have.push(c);
      self.className = have.join(' ');
    },
    contains: function (c) {
      return self.className.split(/\s+/).indexOf(c) >= 0;
    }
  };
}

Object.defineProperty(Node.prototype, 'textContent', {
  get: function () {
    if (!this.children.length) return this._text;
    return this.children.map(function (c) { return c.textContent; }).join('');
  },
  set: function (value) {
    this.children = [];
    this._text = String(value);
  }
});

Node.prototype.appendChild = function (child) {
  /* A fragment splices its children in and vanishes, as the real one does. */
  if (child.isFragment) {
    var self = this;
    child.children.forEach(function (c) { self.appendChild(c); });
    return child;
  }
  child.parentNode = this;
  this.children.push(child);
  return child;
};
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Node.prototype.getAttribute = function (k) {
  return k === 'href' && this.href !== undefined ? this.href : this.attrs[k];
};
Node.prototype.addEventListener = function (name, fn) {
  (this.listeners[name] = this.listeners[name] || []).push(fn);
};
Node.prototype.click = function () {
  (this.listeners.click || []).forEach(function (fn) { fn({}); });
};
Node.prototype.focus = function () {};

Node.prototype.walk = function (fn) {
  fn(this);
  this.children.forEach(function (c) { c.walk(fn); });
};
function matches(node, sel) {
  if (sel.charAt(0) === '.') return node.classList.contains(sel.slice(1));
  return node.tagName === sel.toUpperCase();
}
Node.prototype.querySelectorAll = function (sel) {
  var out = [];
  this.children.forEach(function (c) {
    c.walk(function (n) { if (matches(n, sel)) out.push(n); });
  });
  return out;
};
Node.prototype.querySelector = function (sel) {
  return this.querySelectorAll(sel)[0] || null;
};

var store = {};
global.localStorage = {
  getItem: function (k) { return k in store ? store[k] : null; },
  setItem: function (k, v) { store[k] = String(v); }
};

var root = new Node('body');
global.document = {
  readyState: 'complete',
  body: root,
  createElement: function (tag) { return new Node(tag); },
  createTextNode: function (text) {
    var node = new Node('#text');
    node.textContent = text;
    return node;
  },
  createDocumentFragment: function () {
    var node = new Node('#fragment');
    node.isFragment = true;
    return node;
  },
  querySelector: function (sel) { return root.querySelector(sel); },
  querySelectorAll: function (sel) { return root.querySelectorAll(sel); },
  addEventListener: function (name, fn) { root.addEventListener(name, fn); }
};
global.window = { pikotika: {} };

var spoken = [];
global.window.pikotika.playWord = function (form, kind) {
  spoken.push(kind + ':' + form);
};

var learn = require(path.join(__dirname, '..', 'web', 'js', 'learn.js'));

/* --- helpers ------------------------------------------------------------- */

var failures = 0;
function check(name, got, want) {
  if (JSON.stringify(got) !== JSON.stringify(want)) {
    failures++;
    console.log('FAIL  ' + name);
    console.log('      got  ' + JSON.stringify(got));
    console.log('      want ' + JSON.stringify(want));
  }
}
function press(key) {
  var prevented = false;
  (root.listeners.keydown || []).forEach(function (fn) {
    fn({ key: key, target: root, preventDefault: function () { prevented = true; } });
  });
  return prevented;
}

/* --- a sitting ----------------------------------------------------------- */

var lesson = {
  id: '9.9',
  level: 9,
  cards: [
    { k: 'word', en: 'water', form: 'aku', han: '水',
      hint: '*aqu*a, *aqu*atic' },
    { k: 'word', en: 'good', form: 'pona', han: '好', hint: 'a *bona* fide good one' },
    { k: 'sent', en: 'The water is good.', form: 'Aku ri pona.',
      han: '水 ⊢ 好.', hint: 'water RI good' }
  ]
};

var mount = new Node('div');
mount.classList.add('lesson-deck');
mount.dataset.lesson = lesson.id;
root.appendChild(mount);
learn.runDeck(mount, lesson);

var deckBox = mount.querySelector('.deck');
check('the deck is hidden until it is started', deckBox.hidden, true);
check('nothing is marked done before it is run', store['pk-learn-done'], undefined);

mount.querySelector('.deck-start').click();
check('starting shows the deck', deckBox.hidden, false);

var prompt = mount.querySelector('.deck-prompt');
var answer = mount.querySelector('.deck-answer');
check('the answer starts hidden', answer.hidden, true);
check('there is a prompt on the first card', prompt.textContent.length > 0, true);

/* A card that has not been turned over cannot be graded: the whole method is
   answer first, look second, and a stray keypress must not skip that. */
var before = prompt.textContent;
press('x');
check('x does nothing before the card is turned over',
      mount.querySelector('.deck-prompt').textContent, before);

press(' ');
check('space turns the card over', mount.querySelector('.deck-answer').hidden, false);
check('turning it over speaks it', spoken.length > 0, true);

press('ArrowRight');
check('an arrow grades it and deals the next',
      mount.querySelector('.deck-answer').hidden, true);

/* The arrows grade, and only once the card has been turned over.  Only one
   deck exists on the page at this point, so a press reaches exactly one. */
var stillHere = mount.querySelector('.deck-prompt').textContent;
press('ArrowRight');
check('an arrow does nothing before the card is turned over',
      mount.querySelector('.deck-prompt').textContent, stillHere);
press(' ');
check('space turned it over', mount.querySelector('.deck-answer').hidden, false);
press('ArrowLeft');
check('left grades it a miss and deals the next',
      mount.querySelector('.deck-answer').hidden, true);
press(' ');
press('ArrowRight');
check('right grades it a hit and deals the next',
      mount.querySelector('.deck-answer').hidden, true);

/* --- the flip ------------------------------------------------------------
   A card is one item asked from either side, so the *same* card must come
   back the other way round.  Miss the front card twice: it goes back two
   each time, so with three cards it is the one dealt again after the other
   two, and it should be asking for English by then. */

var solo = { id: '9.7', level: 9, cards: [lesson.cards[0]] };
var soloMount = new Node('div');
soloMount.classList.add('lesson-deck');
root.appendChild(soloMount);
learn.runDeck(soloMount, solo);
soloMount.querySelector('.deck-start').click();
check('a card opens asking for production',
      soloMount.querySelector('.deck-kind').textContent, 'Say it in Pikotika');
check('...with the English on the front',
      soloMount.querySelector('.deck-prompt').textContent, 'water');
soloMount.querySelector('.deck-reveal').click();
soloMount.querySelector('.deck-miss').click();
check('the same card comes back the other way round',
      soloMount.querySelector('.deck-kind').textContent, 'What does this mean?');
check('...with the Pikotika on the front',
      soloMount.querySelector('.deck-prompt').textContent, 'aku');
soloMount.querySelector('.deck-reveal').click();
soloMount.querySelector('.deck-miss').click();
check('and flips back again',
      soloMount.querySelector('.deck-kind').textContent, 'Say it in Pikotika');

/* Clearing still takes two right answers, so a cleared card has been had in
   both directions -- which is the whole reason the flip costs no extra card. */
soloMount.querySelector('.deck-reveal').click();
soloMount.querySelector('.deck-hit').click();
check('one right answer does not clear it',
      soloMount.querySelector('.deck-end').hidden, true);
soloMount.querySelector('.deck-reveal').click();
soloMount.querySelector('.deck-hit').click();
check('two does', soloMount.querySelector('.deck-end').hidden, false);

/* --- the third line ------------------------------------------------------
   A root's mnemonic, shown on *both* directions: the cards are the only place
   on the site a learner meets them.  It used to be the root's gloss, which on
   a Pikotika -> English card was the English already on the line above. */

var hintMount = new Node('div');
hintMount.classList.add('lesson-deck');
root.appendChild(hintMount);
learn.runDeck(hintMount, { id: '9.5', level: 9, cards: [lesson.cards[0]] });
hintMount.querySelector('.deck-start').click();
hintMount.querySelector('.deck-reveal').click();
check('the mnemonic shows on an English -> Pikotika card',
      hintMount.querySelector('.deck-hint').textContent, 'aqua, aquatic');
check('...and the answer is not the English that was on the prompt',
      hintMount.querySelector('.deck-answer').textContent.indexOf('water'), -1);
hintMount.querySelector('.deck-miss').click();
hintMount.querySelector('.deck-reveal').click();
check('the mnemonic shows the other way round too',
      hintMount.querySelector('.deck-hint').textContent, 'aqua, aquatic');
check('...and the answer is the English', 
      hintMount.querySelector('.deck-en').textContent, 'water');
/* site.js turns the *asterisks* into <em>; with no site.js loaded, learn.js
   strips them rather than printing them. */
check('no stray asterisks reach the card',
      hintMount.querySelector('.deck-hint').textContent.indexOf('*'), -1);

/* --- the arrow keys ------------------------------------------------------ */

var keyMount = new Node('div');
keyMount.classList.add('lesson-deck');
root.appendChild(keyMount);
learn.runDeck(keyMount, { id: '9.6', level: 9, cards: [lesson.cards[0]] });
keyMount.querySelector('.deck-start').click();
check('the reveal button reads plainly',
      keyMount.querySelector('.deck-reveal').textContent, 'Show answer');
check('...and names its key as a hover tag',
      [keyMount.querySelector('.deck-reveal').getAttribute('title'),
       keyMount.querySelector('.deck-reveal').getAttribute('aria-keyshortcuts')],
      ['Spacebar', 'Space']);
check('the miss button names its key',
      [keyMount.querySelector('.deck-miss').textContent,
       keyMount.querySelector('.deck-miss').getAttribute('title')],
      ['✗  Missed', 'Left arrow']);
check('the hit button names its key',
      [keyMount.querySelector('.deck-hit').textContent,
       keyMount.querySelector('.deck-hit').getAttribute('title')],
      ['✓  Got it', 'Right arrow']);

/* Space reveals and nothing else.  Doubling it is easy to do by accident, and
   when space also meant "got it" that silently cleared a card unlooked-at. */
keyMount.querySelector('.deck-reveal').click();
var shown = keyMount.querySelector('.deck-answer').textContent;
press(' ');
press(' ');
check('a doubled space does not grade the card',
      [keyMount.querySelector('.deck-answer').hidden,
       keyMount.querySelector('.deck-answer').textContent], [false, shown]);

/* --- clearing the deck --------------------------------------------------- */

for (var i = 0; i < 40 && mount.querySelector('.deck-end').hidden; i++) {
  press(' ');
  press('ArrowRight');
}
check('the deck finishes', mount.querySelector('.deck-end').hidden, false);
check('the deck body is put away', mount.querySelector('.deck-body').hidden, true);
check('finishing marks the lesson done',
      JSON.parse(store['pk-learn-done'])['9.9'], 1);

/* --- a second run -------------------------------------------------------- */

/* Running it again used to rebuild the deck, which stacked a second keydown
   handler on the document -- so one press graded two cards.  The finished
   screen is a sibling now, and nothing is rebuilt. */
var handlersBefore = (root.listeners.keydown || []).length;
mount.querySelector('.deck-again').click();
check('running it again does not add another key handler',
      (root.listeners.keydown || []).length, handlersBefore);
check('running it again brings the deck back', mount.querySelector('.deck-body').hidden, false);
check('...with every card back in it',
      mount.querySelector('.deck-count').textContent, '0 of 3 cleared');

/* --- the course map ------------------------------------------------------ */

var map = new Node('div');
map.classList.add('course-map');
root.appendChild(map);
[['9.9', true], ['9.8', false]].forEach(function (pair) {
  var li = new Node('li');
  li.classList.add('course-lesson');
  li.dataset.lesson = pair[0];
  var a = new Node('a');
  a.href = '/learn/9/' + pair[0].split('.')[1] + '/';
  li.appendChild(a);
  map.appendChild(li);
});
var resume = new Node('p');
resume.classList.add('learn-resume');
resume.hidden = true;
resume.appendChild(new Node('a'));
root.appendChild(resume);

learn.initMap();
check('a finished lesson is marked on the map',
      map.querySelectorAll('.course-lesson')[0].classList.contains('is-done'), true);
check('an unfinished one is not',
      map.querySelectorAll('.course-lesson')[1].classList.contains('is-done'), false);
check('the resume button points at the first unfinished lesson',
      resume.querySelector('a').href, '/learn/9/8/');
check('...and says Continue once something is done',
      resume.querySelector('a').textContent, 'Continue');
check('the resume button is revealed', resume.hidden, false);

if (failures) {
  console.log(failures + ' failure(s)');
  process.exit(1);
}
console.log('deck wiring: all checks passed (shimmed DOM; rendering still wants a browser)');
