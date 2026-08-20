/* Pikotika — reading a written number out as words.
 *
 * The rules are pikotika.org/topics/numbers/, the page this runs on:
 * positional, largest scale first, with the multiplier left off a leading
 * scale word (11 is `tekas wun`, not
 * `wun tekas wun`; 100 is just `katon`).  A thousands or millions group is set
 * off from the rest by a comma.  The decimal point is `parte` and the digits
 * after it are read one at a time; a fraction takes `in` between numerator and
 * denominator, `inkaton` when the denominator is 100; an ordinal appends
 * `orten` to the last word of the reading.
 *
 * This is a port of pikotika.py's counting_words / decimal_words, and a port
 * is a second implementation, so build.py:check_numbers runs both over the
 * same inputs on every build and fails on any disagreement.
 *
 * Loaded in the browser as window.pikotikaNumbers; required by that check
 * under node.  Keep it dependency-free so both can use it.
 */
(function (exports) {
  'use strict';

  /* form, gloss, and the character -- the digits 2-9 *are* their characters,
     so they stay digits in Han; `one` and `no` have characters of their own. */
  var DIGITS = [
    ['nem', 'no', '无'],
    ['wun', 'one', '一'],
    ['pits', 'two', '2'],
    ['tets', 'three', '3'],
    ['wats', 'four', '4'],
    ['kins', 'five', '5'],
    ['siks', 'six', '6'],
    ['sens', 'seven', '7'],
    ['ots', 'eight', '8'],
    ['noks', 'nine', '9']
  ];

  /* value, form, gloss, character, and whether a group of this size is set off
     with a comma.  Hundreds and tens are not: 12345 reads
     `tekas pits kiru, tets katon wats tekas kins`. */
  var SCALES = [
    [1000000n, 'miron', 'million', '兆', true],
    [1000n, 'kiru', 'thousand', '千', true],
    [100n, 'katon', 'hundred', '百', false],
    [10n, 'tekas', 'ten', '十', false]
  ];

  var POINT = { f: 'parte', g: 'part', h: '分', a: ['parte'] };
  var OVER = { f: 'in', g: 'in', h: '内', a: ['in'] };
  var PERCENT = { f: 'inkaton', g: 'in-hundred', h: '内百', a: ['inkaton'] };
  var ORDINAL = { f: 'orten', g: 'sequence', h: '序', a: ['orten'] };

  var COMMA = { sep: ',' };

  /* Nothing about the reading breaks down at any size -- a million millions is
     `miron miron` -- but a number this long is a typo far more often than it is
     a question, and the reading of one is unreadable either way. */
  var MAX_DIGITS = 24;

  /* `a` is what to *play*: one clip per root, since the clips are per word
     and a compound like `sensorten` was never rendered as one.  For every
     token but a compounded ordinal that is just the form itself. */
  function token(triple) {
    return { f: triple[0], g: triple[1], h: triple[2], a: [triple[0]] };
  }

  /* An integer as the several words it is read as: 35 -> tets tekas kins. */
  function counting(n) {
    if (n < 10n) return [token(DIGITS[Number(n)])];
    var scale = null;
    for (var i = 0; i < SCALES.length; i++) {
      if (n >= SCALES[i][0]) { scale = SCALES[i]; break; }
    }
    var count = n / scale[0];
    var rest = n % scale[0];
    var words = count > 1n ? counting(count) : [];
    words.push({ f: scale[1], g: scale[2], h: scale[3], a: [scale[1]] });
    if (rest) {
      if (scale[4]) words.push(COMMA);
      words = words.concat(counting(rest));
    }
    return words;
  }

  /* The digits after the point are read one at a time: 1.25 is
     `wun parte pits kins`, never `wun parte pits tekas kins`. */
  function decimal(whole, frac) {
    var words = counting(whole);
    words.push(POINT);
    for (var i = 0; i < frac.length; i++) {
      words.push(token(DIGITS[Number(frac[i])]));
    }
    return words;
  }

  /* --- rendering ---------------------------------------------------------- */

  var CLUSTERS = ['ts', 'ns', 'ks'];
  var VOWELS = 'aeiou';

  /* A root ending in -ts -ns -ks takes a linking `e` before a consonant.
     `orten` begins with a vowel, so nothing here needs one today; the rule is
     written out anyway rather than left as an assumption about one suffix. */
  function joinForms(prev, next) {
    var needs = false;
    for (var i = 0; i < CLUSTERS.length; i++) {
      if (prev.slice(-2) === CLUSTERS[i]) needs = true;
    }
    if (needs && VOWELS.indexOf(next.charAt(0)) < 0) return prev + 'e' + next;
    return prev + next;
  }

  /* Compound the suffix onto the last word of the reading: 21st is
     `pits tekas wunorten`, one word of it a compound. */
  function suffix(words, part) {
    var last = words[words.length - 1];
    var form = joinForms(last.f, part.f);
    words[words.length - 1] = {
      f: form,
      g: last.g + '-' + part.g,
      h: last.h + part.h,
      /* One clip if the compound is a standing word, two if it is not.  It is
         one word either way; the difference is only whether anyone has
         recorded it, and `tets orten` played as two clips sounds like two
         words -- each with its own stress and its own final fall. */
      a: ORDINAL_CLIPS[form] ? [form] : last.a.concat(part.a)
    };
    return words;
  }

  /* The ordinals recorded in compounds.tsv, which are the ones with a clip of
     their own.  A reading always ends in a digit or a scale word, so this
     covers every ordinal there is: 1st through 10th, plus 100th, 1000th and
     1000000th.  `nem` is left out -- there is no zeroth.

     Derived from the tables above rather than listed, and checked against
     compounds.tsv by build.py:check_numbers, so an entry recorded on one side
     and not the other fails the build: a form claimed here with no clip would
     simply be silent. */
  var ORDINAL_CLIPS = (function () {
    var out = {};
    for (var i = 1; i < DIGITS.length; i++) {
      out[joinForms(DIGITS[i][0], ORDINAL.f)] = 1;
    }
    SCALES.forEach(function (s) { out[joinForms(s[1], ORDINAL.f)] = 1; });
    return out;
  })();

  function latin(words) {
    return join(words, function (w) { return w.f; });
  }

  function gloss(words) {
    return join(words, function (w) { return w.g; });
  }

  function han(words) {
    return join(words, function (w) { return w.h; });
  }

  /* The comma hangs on the word before it, as punctuation does everywhere. */
  function join(words, pick) {
    var out = '';
    for (var i = 0; i < words.length; i++) {
      if (words[i].sep) { out += words[i].sep; continue; }
      if (out) out += ' ';
      out += pick(words[i]);
    }
    return out;
  }

  /* --- reading an input --------------------------------------------------- */

  var INTEGER = /^\d+$/;
  var DECIMAL = /^(\d+)\.(\d+)$/;
  var FRACTION = /^(\d+)\/(\d+)$/;
  var PERCENTAGE = /^(\d+(?:\.\d+)?)%$/;
  var ORDINAL_IN = /^(\d+)(?:st|nd|rd|th)$/i;

  function tooLong(digits) {
    return digits.replace(/\D/g, '').length > MAX_DIGITS;
  }

  function readPlain(text) {
    var m;
    if (INTEGER.test(text)) return counting(BigInt(text));
    if ((m = DECIMAL.exec(text))) return decimal(BigInt(m[1]), m[2]);
    return null;
  }

  /* One number, in any of the shapes a reader might type it.  Returns
     { ok, kind, words, latin, gloss, spelled, han, note }.

     `latin` is how the number is *said*, which is the whole job here.  How it
     is *written* is not this module's business -- a number is written in
     digits, `3/4` with a slash and `50%` with a percent sign, exactly as the
     reader typed it.  `spelled` is the reading written out as words, which
     nobody writes but which is the form pikotika.py can parse, so it is the
     bridge build.py:check_numbers compares the two implementations through. */
  function read(input) {
    /* A thousands separator or a stray space is how people write numbers, not
       something to refuse; `3 / 4` and `50 %` come in the same way. */
    var text = String(input == null ? '' : input).replace(/[\s,]/g, '');
    if (!text) return { ok: false };

    if (text.charAt(0) === '-' || text.charAt(0) === '−') {
      return { ok: false, error: 'Pikotika has no settled way to say a ' +
               'negative number yet — only positive ones, for now.' };
    }
    if (tooLong(text)) {
      return { ok: false, error: 'That is more than ' + MAX_DIGITS +
               ' digits. The reading works at any size, but past this it is ' +
               'no longer something anyone would say.' };
    }

    var m, words;

    if ((m = ORDINAL_IN.exec(text))) {
      words = suffix(counting(BigInt(m[1])), ORDINAL);
      return {
        ok: true, kind: 'ordinal', words: words,
        latin: latin(words), gloss: gloss(words),
        spelled: latin(words), han: han(words),
        note: 'An ordinal is the number with ' + ORDINAL.f +
              ' (‘sequence’) on the end, so it is written out in ' +
              'words rather than digits.'
      };
    }

    if ((m = PERCENTAGE.exec(text))) {
      words = readPlain(m[1]);
      words.push(PERCENT);
      return {
        ok: true, kind: 'percent', words: words,
        latin: latin(words), gloss: gloss(words),
        spelled: m[1] + ' ' + PERCENT.f, han: m[1] + ' ' + PERCENT.h,
        note: PERCENT.f + ' is ‘in a hundred’ — a percentage is ' +
              'a fraction with the denominator already agreed on.'
      };
    }

    if ((m = FRACTION.exec(text))) {
      if (m[2] === '100') return read(m[1] + '%');
      words = counting(BigInt(m[1])).concat([OVER], counting(BigInt(m[2])));
      return {
        ok: true, kind: 'fraction', words: words,
        latin: latin(words), gloss: gloss(words),
        spelled: m[1] + ' ' + OVER.f + ' ' + m[2],
        han: m[1] + ' ' + OVER.h + ' ' + m[2],
        note: 'The slash is read as ' + OVER.f + ' — three in four.'
      };
    }

    words = readPlain(text);
    if (!words) {
      return { ok: false, error: 'Try a number: 42, 1.25, 3/4, 50%, or 7th.' };
    }
    return {
      ok: true, kind: text.indexOf('.') >= 0 ? 'decimal' : 'integer',
      words: words, latin: latin(words), gloss: gloss(words),
      spelled: text, han: text,
      note: text.indexOf('.') >= 0
        ? 'The point is ' + POINT.f + ', and the digits after it are read one ' +
          'at a time.'
        : ''
    };
  }

  /* Every form the reader can ever say -- what gen_audio renders a clip for.
     Derived rather than listed, so a change to the tables above cannot leave
     a word of a reading silent. */
  function vocabulary() {
    var forms = [];
    DIGITS.forEach(function (d) { forms.push(d[0]); });
    SCALES.forEach(function (s) { forms.push(s[1]); });
    [POINT, OVER, PERCENT, ORDINAL].forEach(function (t) { forms.push(t.f); });
    Object.keys(ORDINAL_CLIPS).forEach(function (f) { forms.push(f); });
    return forms.sort();
  }

  exports.read = read;
  exports.counting = counting;
  exports.vocabulary = vocabulary;
  exports.MAX_DIGITS = MAX_DIGITS;
})(typeof module !== 'undefined' && module.exports
   ? module.exports
   : (window.pikotikaNumbers = {}));
