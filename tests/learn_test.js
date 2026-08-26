/* Tests for the course deck's queue -- web/js/learn.js.
 *
 *     node tests/learn_test.js              run them
 *     node tests/learn_test.js --deck path  also walk every deck in a
 *                                           lessons.json and check it clears
 *
 * The queue is the part of the course that has rules in it, and the part a
 * browser cannot be asked about here: everything else in learn.js is markup
 * and localStorage.  So `Deck` is written free of the DOM and checked from
 * node on every build.
 *
 * What the rules are:
 *   - a card clears at two right answers in a row
 *   - a wrong answer sends it back to zero, not back one
 *   - a cleared card never returns
 *   - the bar counts cleared cards, so wrong answers do not advance it
 */

'use strict';

var path = require('path');
var learn = require(path.join(__dirname, '..', 'web', 'js', 'learn.js'));

var failures = 0;

function check(name, got, want) {
  var ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) {
    failures++;
    console.log('FAIL  ' + name);
    console.log('      got  ' + JSON.stringify(got));
    console.log('      want ' + JSON.stringify(want));
  }
  return ok;
}

function cards(n) {
  var out = [];
  for (var i = 0; i < n; i++) out.push({ k: 'say', form: 'w' + i, en: 'w' + i });
  return out;
}

function forms(deck) {
  return deck.queue.map(function (e) { return e.card.form; });
}

/* --- clearing ------------------------------------------------------------ */

var d = new learn.Deck(cards(1));
check('one card starts uncleared', [d.total, d.cleared, d.done()], [1, 0, false]);
d.answer(true);
check('one right is not enough', [d.cleared, d.done()], [0, false]);
d.answer(true);
check('two right clears it', [d.cleared, d.done()], [1, true]);
check('a cleared deck has no current card', d.current(), null);

/* A miss resets the count rather than decrementing it: the card has to be
   answered twice running, and "running" is the whole point. */
d = new learn.Deck(cards(1));
d.answer(true);
d.answer(false);
check('a miss resets to zero', [d.cleared, d.queue[0].hits], [0, 0]);
d.answer(true);
check('...so one right after a miss still is not enough', d.cleared, 0);
d.answer(true);
check('...and two is', d.cleared, 1);

/* --- where a card goes back ---------------------------------------------- */

d = new learn.Deck(cards(10));
check('the deck starts in order', forms(d)[0], 'w0');
d.answer(true);
check('a right answer goes back five', forms(d)[5], 'w0');
d = new learn.Deck(cards(10));
d.answer(false);
check('a wrong answer comes back sooner', forms(d)[2], 'w0');

/* A gap longer than the queue means the front, and that is right: with two
   cards left there is nowhere else to put one. */
d = new learn.Deck(cards(2));
d.answer(true);
check('a short queue keeps every card', forms(d).length, 2);

/* --- direction ------------------------------------------------------------
   A card is one item asked from either side: it opens asking for production
   and flips every time it is dealt, and clearing still takes two right
   answers -- so a cleared card has been had both ways. */

d = new learn.Deck(cards(1));
check('a card opens asking for production', d.present().dir, learn.EN_TO_PK);
check('...then flips', d.present().dir, learn.PK_TO_EN);
check('...and back', d.present().dir, learn.EN_TO_PK);
check('direction() agrees with the next deal', d.direction(), learn.PK_TO_EN);

/* Dealing is what flips it, not grading: a card graded without being dealt
   would otherwise come back the same way round. */
d = new learn.Deck(cards(2));
var first = d.present();
d.answer(true);
d.present();                  /* the other card */
d.answer(true);
check('a card comes back the other way round', d.present().dir, learn.PK_TO_EN);

check('an empty deck has no direction', new learn.Deck([]).direction(), null);
check('...and deals nothing', new learn.Deck([]).present(), null);

/* --- the bar ------------------------------------------------------------- */

d = new learn.Deck(cards(4));
check('an empty deck reads zero', d.progress(), 0);
for (var i = 0; i < 8; i++) d.answer(false);
check('missing does not advance the bar', d.progress(), 0);
/* Four cards, every answer right: the first four answers put each card
   through once and clear nothing, and the next two clear two. */
d = new learn.Deck(cards(4));
for (var j = 0; j < 4; j++) d.answer(true);
check('one pass through clears nothing', d.cleared, 0);
d.answer(true); d.answer(true);
check('two cards cleared is half', d.progress(), 0.5);

/* --- every deck terminates ----------------------------------------------- */

function clears(deckCards, right) {
  /* `right` is how often the learner gets one right, as one in N.  Even a
     learner who misses most of them has to finish: a deck that could loop is
     a deck nobody can put down. */
  var deck = new learn.Deck(deckCards);
  var seed = 1, steps = 0;
  while (!deck.done()) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    deck.answer(seed % right === 0);
    if (++steps > 100000) return null;
  }
  return steps;
}

var everyOther = clears(cards(20), 2);
check('a 20-card deck clears at one right in two', everyOther !== null, true);
var mostlyWrong = clears(cards(20), 5);
check('...and at one right in five', mostlyWrong !== null, true);
if (everyOther !== null && mostlyWrong !== null &&
    !(mostlyWrong > everyOther)) {
  failures++;
  console.log('FAIL  missing more should take more answers, not fewer');
}

/* --- the real decks ------------------------------------------------------ */

var argv = process.argv.slice(2);
var at = argv.indexOf('--deck');
if (at >= 0 && argv[at + 1]) {
  var data = JSON.parse(require('fs').readFileSync(argv[at + 1], 'utf8'));
  var worst = 0, empty = [];
  data.lessons.forEach(function (lesson) {
    if (!lesson.cards.length) { empty.push(lesson.id); return; }
    lesson.cards.forEach(function (card) {
      if (!card.k || !card.form) {
        failures++;
        console.log('FAIL  ' + lesson.id + ': a card with no kind or no form');
      }
      /* Every card is asked from both sides now, so both sides have to be
         there -- a card with no English is one that cannot be flipped. */
      if (!card.en) {
        failures++;
        console.log('FAIL  ' + lesson.id + ': a card with no English');
      }
      /* The third line shows on both directions, so it has to be there too --
         and a root whose mnemonic cell was empty would show a blank line
         rather than fail anywhere else. */
      if (!card.hint) {
        failures++;
        console.log('FAIL  ' + lesson.id + ': ' + card.form + ' has no hint');
      }
      if (card.k !== 'word' && card.k !== 'sent') {
        failures++;
        console.log('FAIL  ' + lesson.id + ': unknown card kind ' + card.k);
      }
    });
    var steps = clears(lesson.cards, 3);
    if (steps === null) {
      failures++;
      console.log('FAIL  ' + lesson.id + ' does not clear');
    } else if (steps > worst) {
      worst = steps;
    }
  });
  if (empty.length) {
    failures++;
    console.log('FAIL  lessons with an empty deck: ' + empty.join(', '));
  }
  console.log(data.lessons.length + ' decks, all clearing; worst is ' +
              worst + ' answers at one right in three');
}

if (failures) {
  console.log(failures + ' failure(s)');
  process.exit(1);
}
console.log('deck queue: all checks passed');
