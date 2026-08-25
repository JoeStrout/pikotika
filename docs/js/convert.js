/* Pikotika — converting between English, gloss, Latin, and Han.
 *
 * A port of pikotika.py's parse/render core: tokenize the query, work out which
 * of the four notations it is written in, and write the other three back out.
 * It drives the converter on pikotika.org/tools/.
 *
 * Only the *algorithms* are ported.  The tables come out of `pikotika.Tables`
 * as web/data/convert.json (see gen_convert.py), built by the same code that
 * builds them for the command line, so nothing here can disagree with the
 * language about what a root is — only about what to do with it.  That is what
 * build.py:check_convert measures, running both implementations over every
 * corpus sentence, every compound, every root and every name.
 *
 * Loaded in the browser as window.pikotikaConvert; required by that check under
 * node.  Keep it dependency-free so both can use it.
 *
 *     var t = pikotikaConvert.tables(payload);   // the parsed convert.json
 *     pikotikaConvert.lookup('Ri ama a tu.', t);
 */
(function (exports) {
  'use strict';

  /* --- constants, all of them pikotika.py's -------------------------------- */

  var PARTICLES = ['RI', 'A', 'TE', 'RI-TE'];

  /* The corpora write numerals as digits ("2-go-paper") as well as spelled out,
     so a digit is accepted as an alias for its numeral root. */
  var DIGITS = {
    '0': 'no', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
    '10': 'ten', '100': 'hundred', '1000': 'thousand', '1000000': 'million'
  };

  /* Positional, largest scale first, with the multiplier left off a leading
     scale word; a thousands or millions group is set off by a comma. */
  var SCALES = [[1000000, 'million', true], [1000, 'thousand', true],
                [100, 'hundred', false], [10, 'ten', false]];

  var PUNCT = ',.:;?!' + '、。：；？！';
  var SENTENCE_END = '.?!' + '。？！';

  var DECIMAL_POINT = 'part';
  var CLOCK_MARK = 'hour';
  var FRACTION_MARK = 'in';
  var PERCENT_WORD = ['in', 'hundred'];
  var PERCENT_DENOMINATOR = 100;

  /* Free-standing `one` is counting and renders as the digit; bound `one` is
     not.  `no` gets no such rule — its free-standing uses are "none". */
  var DIGIT_WHEN_FREE = { one: '1' };
  var FREE_DIGIT_TO_GLOSS = { '1': 'one' };

  var CLUSTERS = ['ts', 'ns', 'ks'];
  var VOWELS = 'aeiou';
  var LINK = 'e';

  /* --- small predicates ---------------------------------------------------- */

  function isDigits(s) { return /^[0-9]+$/.test(s); }
  function isPunctChar(c) { return PUNCT.indexOf(c) >= 0; }
  function isAscii(c) { return c.charCodeAt(0) < 128; }
  function isLatinLetter(c) { return /[A-Za-z]/.test(c); }

  function isPunctText(s) {
    if (!s) return false;
    for (var i = 0; i < s.length; i++) if (!isPunctChar(s[i])) return false;
    return true;
  }

  function endsSentence(token) {
    for (var i = 0; i < token.length; i++) {
      if (SENTENCE_END.indexOf(token[i]) >= 0) return true;
    }
    return false;
  }

  /* A word is an array of glosses, a string of punctuation, or a numeral. */
  function name(english) { return { t: 'NAME', v: english }; }
  function num(text) { return { t: 'NUM', v: text }; }
  function numeral(text, reading) {
    return { t: 'NUMERAL', text: text, reading: reading };
  }
  function isName(g) { return !!g && g.t === 'NAME'; }
  function isNum(g) { return !!g && g.t === 'NUM'; }
  function isNumeral(w) { return !!w && w.t === 'NUMERAL'; }
  function isToken(g) { return typeof g !== 'string'; }
  function isPunct(w) { return typeof w === 'string'; }
  function literal(g) { return g.v; }

  /* --- the tables ---------------------------------------------------------- */

  /* Everything below reads these; nothing below builds them.  `payload` is
     web/data/convert.json, which gen_convert.py dumps out of pikotika.Tables. */
  function tables(payload) {
    var t = {
      roots: payload.roots,
      covers: payload.covers,
      compounds: payload.compounds,
      compoundEn: payload.compoundEn,
      alias2gloss: {},
      form2gloss: {},
      han2gloss: {},
      multiHan: [],
      names: {},        // English name, lowercased -> form
      nameForms: {},    // form, exactly as written -> its canonical English
      form2name: {},    // form, lowercased -> its canonical English
      nameEnglish: {},  // form -> every English name it answers to
      corpus: payload.corpus || []
    };

    Object.keys(t.roots).forEach(function (gloss) {
      var row = t.roots[gloss];
      t.form2gloss[row.form] = gloss;
      if (row.han) t.han2gloss[row.han] = gloss;
      if (row.gloss2) t.alias2gloss[row.gloss2] = gloss;
    });
    t.multiHan = Object.keys(t.han2gloss).filter(function (h) {
      return h.length > 1;
    }).sort(function (a, b) { return b.length - a.length; });

    /* names.tsv in file order, and the two directions disagree about which row
       wins: English -> form takes the last, while every form-keyed map keeps
       the first, so a curated Tom outranks the poured Dom/Thom/Tome. */
    (payload.names || []).forEach(function (row) {
      var form = row[0], english = row[1];
      english.split(';').forEach(function (one) {
        one = one.trim().toLowerCase();
        if (one) t.names[one] = form;
      });
      if (Object.prototype.hasOwnProperty.call(t.nameForms, form)) return;
      var canonical = english.split(';')[0].trim();
      t.nameForms[form] = canonical;
      t.nameEnglish[form] = english;
      /* Keyed lowercase, and *not* first-wins: two rows whose forms differ only
         in case are two rows here, so the last one written takes the key.  That
         is what pikotika.py does, and the converter has to agree with it. */
      t.form2name[form.toLowerCase()] = canonical;
    });
    return t;
  }

  function has(map, key) {
    return Object.prototype.hasOwnProperty.call(map, key);
  }

  function isParticle(t, gloss) {
    return typeof gloss === 'string' && has(t.roots, gloss) &&
      !!t.roots[gloss].particle;
  }

  /* Either of a root's two glosses names it; nothing downstream sees the
     alias, since this resolves to the primary gloss. */
  function rootGloss(t, key) {
    if (has(t.roots, key) && !isParticle(t, key)) return key;
    return has(t.alias2gloss, key) ? t.alias2gloss[key] : null;
  }

  function formOf(t, gloss) { return t.roots[gloss].form; }
  function hanOf(t, gloss) { return t.roots[gloss].han; }
  function levelOf(t, gloss) {
    return (has(t.roots, gloss) && t.roots[gloss].level) || '';
  }

  /* The English name a token spells, in either notation; null if neither. */
  function nameOf(t, token) {
    var form = t.names[token.toLowerCase()];
    if (form !== undefined) return t.form2name[form.toLowerCase()];
    var direct = t.form2name[token.toLowerCase()];
    return direct === undefined ? null : direct;
  }

  /* --- numerals ------------------------------------------------------------ */

  /* An integer as the several words it is read as: 35 -> [three] [ten] [five]. */
  function counting(n) {
    if (n < 10n) return [[DIGITS[String(n)]]];
    var scale = null;
    for (var i = 0; i < SCALES.length; i++) {
      if (n >= BigInt(SCALES[i][0])) { scale = SCALES[i]; break; }
    }
    var value = BigInt(scale[0]);
    var count = n / value, rest = n % value;
    var words = (count > 1n ? counting(count) : []).concat([[scale[1]]]);
    if (rest) {
      words = words.concat(scale[2] ? [','] : []).concat(counting(rest));
    }
    return words;
  }

  function decimalWords(word) {
    var at = word.indexOf('.');
    if (at < 0) return null;
    var whole = word.slice(0, at), frac = word.slice(at + 1);
    if (!isDigits(whole) || !isDigits(frac)) return null;
    var words = counting(BigInt(whole)).concat([[DECIMAL_POINT]]);
    for (var i = 0; i < frac.length; i++) words.push([DIGITS[frac[i]]]);
    return words;
  }

  function clockWords(word) {
    var at = word.indexOf(':');
    if (at < 0) return null;
    var hour = word.slice(0, at), minute = word.slice(at + 1);
    if (!isDigits(hour) || !isDigits(minute)) return null;
    if (hour.length < 1 || hour.length > 2) return null;
    if (minute.length !== 2 || Number(minute) > 59) return null;
    return counting(BigInt(hour)).concat([[CLOCK_MARK]])
      .concat(Number(minute) ? counting(BigInt(minute)) : []);
  }

  function fractionWords(word) {
    var at = word.indexOf('/');
    if (at < 0) return null;
    var top = word.slice(0, at), bottom = word.slice(at + 1);
    if (!isDigits(top) || !isDigits(bottom)) return null;
    if (Number(bottom) === PERCENT_DENOMINATOR) {
      return counting(BigInt(top)).concat([PERCENT_WORD.slice()]);
    }
    return counting(BigInt(top)).concat([[FRACTION_MARK]])
      .concat(counting(BigInt(bottom)));
  }

  function percentWords(word) {
    if (word.slice(-1) !== '%') return null;
    var body = word.slice(0, -1);
    var amount = isDigits(body) ? counting(BigInt(body)) : decimalWords(body);
    return amount ? amount.concat([PERCENT_WORD.slice()]) : null;
  }

  /* The several words a written numeral is read as, or null if it is not one.
     Free-standing numerals only: a digit bound inside a compound stays a digit,
     because a compound is one word and a reading is several. */
  function numeralWords(word) {
    if (isDigits(word)) return counting(BigInt(word));
    return decimalWords(word) || clockWords(word) ||
      fractionWords(word) || percentWords(word);
  }

  function expandNumerals(words) {
    var out = [];
    words.forEach(function (w) {
      if (isNumeral(w)) out.push.apply(out, w.reading);
      else out.push(w);
    });
    return out;
  }

  /* --- tokenizing and joining ---------------------------------------------- */

  /* Ordinary writing attaches punctuation ("a kanis, ker?"), so it is peeled
     off the ends of each whitespace-delimited word.  Only off the ends: a
     decimal point belongs to its number, not to the sentence. */
  function tokenize(text) {
    var out = [];
    text.split(/\s+/).forEach(function (word) {
      if (!word) return;
      var lead = 0, tail = word.length;
      while (lead < tail && isPunctChar(word[lead])) lead++;
      while (tail > lead && isPunctChar(word[tail - 1])) tail--;
      [word.slice(0, lead), word.slice(lead, tail), word.slice(tail)]
        .forEach(function (chunk) { if (chunk) out.push(chunk); });
    });
    return out;
  }

  function joinWords(parts) {
    var out = '';
    parts.forEach(function (part) {
      if (out && !isPunctText(part)) out += ' ';
      out += part;
    });
    return out;
  }

  /* Roots ending in a cluster carry it across a join before a vowel, and need a
     linking `e` before a consonant: `tets` + `kurva` -> **tetsekurva**. */
  function links(prev, next) {
    var ends = CLUSTERS.some(function (c) { return prev.slice(-c.length) === c; });
    return ends && /[A-Za-z]/.test(prev.slice(-1)) &&
      /[A-Za-z]/.test(next.slice(0, 1)) && VOWELS.indexOf(next[0]) < 0;
  }

  function joinLatin(pieces) {
    var out = '';
    pieces.forEach(function (piece) {
      if (out && links(out, piece)) out += LINK;
      out += piece;
    });
    return out;
  }

  /* --- parsing ------------------------------------------------------------- */

  /* Every notation is tried on every query, so most failures are uninteresting.
     Keeping the attempt that got furthest picks out the notation the user was
     actually writing in, and so the token they actually got wrong. */
  function blame(fail, words, token, why) {
    if (fail && (fail.words === undefined || fail.words < words.length)) {
      fail.words = words.length;
      fail.token = token;
      fail.why = why || null;
    }
  }

  /* Split a solid Latin word into root forms.  `raw` is the word as written,
     same length as `form`, so a name's capitalization still counts inside a
     compound. */
  function segment(form, t, raw) {
    if (raw === undefined) raw = form;
    var n = form.length;
    var best = new Array(n + 1);
    for (var k = 0; k <= n; k++) best[k] = null;
    best[0] = [];

    function prior(j, piece) {
      if (best[j] !== null) return best[j];
      /* form[j-1] is an `e` belonging to neither root. */
      if (j && form[j - 1] === LINK && best[j - 1] && best[j - 1].length) {
        var prev = best[j - 1][best[j - 1].length - 1];
        if (!isToken(prev) && links(formOf(t, prev), piece)) return best[j - 1];
      }
      return null;
    }

    for (var i = 1; i <= n; i++) {
      for (var j = 0; j < i; j++) {
        var piece = form.slice(j, i);
        var head = prior(j, piece);
        if (head === null) continue;
        var gloss = t.form2gloss[piece];
        if (gloss !== undefined && !isParticle(t, gloss)) {
          best[i] = head.concat([gloss]);
          break;
        }
        /* A name inside a compound is only recoverable because the reader knows
           the name, so names are part of the segmentation lexicon. */
        var rawPiece = raw.slice(j, i);
        if (has(t.nameForms, rawPiece)) {
          best[i] = head.concat([name(t.nameForms[rawPiece])]);
          break;
        }
        /* A multi-digit number keeps its digits inline. */
        if (isDigits(piece) && !has(DIGITS, piece) &&
            (i === form.length || !isDigits(form[i]))) {
          best[i] = head.concat([num(piece)]);
          break;
        }
      }
    }
    return best[n];
  }

  /* Names are capitalized in every notation, so case alone separates Mira the
     name from **mira** 'surprise'.  The one place it cannot is the start of a
     sentence, where every word is capitalized: there the root wins, and the
     name is only the fallback for a token no roots can spell. */
  function nameWins(token, start, t) {
    if (!/^[A-Z]/.test(token)) return false;
    return !start || segment(token.toLowerCase(), t) === null;
  }

  /* One hyphenated gloss word as its list of glosses, or null. */
  function splitGlossWord(word, t, words, start, fail) {
    var parts = [];
    var pieces = word.split('-');
    for (var n = 0; n < pieces.length; n++) {
      var piece = pieces[n];
      if (isDigits(piece)) {
        parts.push(has(DIGITS, piece) ? DIGITS[piece] : num(piece));
        continue;
      }
      var gloss = rootGloss(t, piece);
      if (gloss !== null) { parts.push(gloss); continue; }
      /* "Joe" by its English spelling, "Yo" by its Pikotika form. */
      var english = nameOf(t, piece);
      if (english !== null && nameWins(piece, start && !n, t)) {
        parts.push(name(english));
        continue;
      }
      blame(fail, words, piece);   // the piece, not the whole compound
      return null;
    }
    return parts;
  }

  function parseGloss(text, t, fail) {
    var words = [];
    var start = true;
    var toks = tokenize(text);
    for (var i = 0; i < toks.length; i++) {
      var word = toks[i];
      if (isPunctText(word)) {
        words.push(word);
        if (endsSentence(word)) start = true;
        continue;
      }
      var reading = numeralWords(word);
      if (reading !== null) {
        words.push(numeral(word, reading));
        start = false;
        continue;
      }
      var upper = word.toUpperCase();
      if (PARTICLES.indexOf(upper) >= 0) {
        words.push([upper]);
        start = false;
        continue;
      }
      var parts = splitGlossWord(word, t, words, start, fail);
      if (parts === null) return null;
      words.push(parts);
      start = false;
    }
    return words.length ? words : null;
  }

  function parseLatin(text, t, fail) {
    var words = [];
    var start = true;
    var toks = tokenize(text);
    for (var i = 0; i < toks.length; i++) {
      var word = toks[i];
      if (isPunctText(word)) {
        words.push(word);
        if (endsSentence(word)) start = true;
        continue;
      }
      var reading = numeralWords(word);
      if (reading !== null) {
        words.push(numeral(word, reading));
        start = false;
        continue;
      }
      var low = word.toLowerCase();
      var gloss = t.form2gloss[low];
      if (gloss !== undefined && isParticle(t, gloss)) {
        words.push([gloss]);
        start = false;
        continue;
      }
      /* An outright win takes the name; otherwise the roots get first refusal
         and the name catches what they cannot spell. */
      var english = has(t.nameForms, word) ? t.nameForms[word] : null;
      var parts = null;
      if (english === null || start) parts = segment(low, t, word);
      if (parts === null && english !== null) parts = [name(english)];
      if (parts === null) {
        blame(fail, words, word);
        return null;
      }
      words.push(parts);
      start = false;
    }
    return words.length ? words : null;
  }

  function parseHan(text, t, fail) {
    var words = [];
    var toks = tokenize(text);
    for (var w = 0; w < toks.length; w++) {
      var word = toks[w];
      if (isPunctText(word)) { words.push(word); continue; }
      var reading = numeralWords(word);
      if (reading !== null) { words.push(numeral(word, reading)); continue; }
      /* No digit shortcut: the characters for two..nine *are* the digits, so
         the per-character lookup below is what resolves them. */
      var parts = [];
      var i = 0;
      while (i < word.length) {
        /* A run of two or more digits is a number with no root of its own. */
        var j = i;
        while (j < word.length && isDigits(word[j])) j++;
        if (j - i > 1) { parts.push(num(word.slice(i, j))); i = j; continue; }
        /* A run of Latin letters inside Han text is a name. */
        j = i;
        while (j < word.length && isAscii(word[j]) && isLatinLetter(word[j])) j++;
        if (j > i) {
          var raw = word.slice(i, j);
          var english = has(t.nameForms, raw) ? t.nameForms[raw]
            : t.form2name[raw.toLowerCase()];
          if (english === undefined || english === null) {
            blame(fail, words, raw);
            return null;
          }
          parts.push(name(english));
          i = j;
          continue;
        }
        /* A particle written as several characters (⊢> for RI-TE). */
        var multi = null;
        for (var m = 0; m < t.multiHan.length; m++) {
          if (word.slice(i, i + t.multiHan[m].length) === t.multiHan[m]) {
            multi = t.multiHan[m];
            break;
          }
        }
        if (multi) { parts.push(t.han2gloss[multi]); i += multi.length; continue; }
        var ch = word[i];
        var gloss = t.han2gloss[ch] || FREE_DIGIT_TO_GLOSS[ch];
        if (gloss === undefined || gloss === null) {
          blame(fail, words, ch);
          return null;
        }
        parts.push(gloss);
        i += 1;
      }
      /* A particle character stands alone as its own word. */
      if (parts.length === 1 && !isToken(parts[0]) && isParticle(t, parts[0])) {
        words.push(parts);
      } else {
        var stuck = null;
        for (var p = 0; p < parts.length; p++) {
          if (!isToken(parts[p]) && isParticle(t, parts[p])) {
            stuck = parts[p];
            break;
          }
        }
        if (stuck !== null) {
          blame(fail, words, hanOf(t, stuck),
                'a particle has to stand as its own word');
          return null;
        }
        words.push(parts);
      }
    }
    return words.length ? words : null;
  }

  function parseEnglish(text, t) {
    var key = text.trim().toLowerCase();
    if (has(t.compounds, key)) return parseGloss(t.compounds[key], t, null);
    var gloss = rootGloss(t, key) || rootGloss(t, key.split(/\s+/).join('_'));
    if (gloss !== null) return [[gloss]];
    if (has(t.covers, key)) return [[t.covers[key][0]]];
    if (has(t.names, key)) return [[name(t.form2name[t.names[key].toLowerCase()])]];
    return null;
  }

  function looksLikeHan(text, t) {
    var chars = text.split('').filter(function (c) { return !/\s/.test(c); });
    if (!chars.length) return false;
    /* Digits and names are written in Latin inside Han text, so an all-ASCII
       string satisfies the test below while being no such thing — it takes one
       actual character to make the notation Han. */
    if (!chars.some(function (c) { return !isAscii(c); })) return false;
    return chars.every(function (c) {
      return has(t.han2gloss, c) || isPunctChar(c) || has(FREE_DIGIT_TO_GLOSS, c) ||
        isDigits(c) || (isAscii(c) && isLatinLetter(c));
    });
  }

  /* Try each notation in turn; returns {words, notation}.  `fail` is an optional
     object; on failure it comes back holding the token that could not be
     resolved. */
  function parse(text, t, fail) {
    if (looksLikeHan(text, t)) {
      var han = parseHan(text, t, fail);
      if (han) return { words: han, notation: 'Han' };
    } else {
      /* One stray character keeps the whole query out of parseHan, and the
         other notations can only blame the word it sits in — so name it here. */
      var stray = null;
      for (var i = 0; i < text.length; i++) {
        var c = text[i];
        if (!isAscii(c) && !isPunctChar(c) && !has(t.han2gloss, c) &&
            !has(FREE_DIGIT_TO_GLOSS, c) && !/\s/.test(c)) {
          stray = c;
          break;
        }
      }
      if (stray) blame(fail, [], stray);
    }
    var tries = [[parseGloss, 'gloss'], [parseLatin, 'Latin'],
                 [parseEnglish, 'English']];
    for (var k = 0; k < tries.length; k++) {
      var words = tries[k][0](text, t, fail);
      if (words) return { words: words, notation: tries[k][1] };
    }
    return { words: null, notation: null };
  }

  /* --- rendering ----------------------------------------------------------- */

  function renderGloss(words, t) {
    var out = [];
    words.forEach(function (w) {
      if (isNumeral(w)) { out.push(renderGloss(w.reading, t)); return; }
      if (isPunct(w)) { out.push(w); return; }
      if (w.length === 1 && !isName(w[0]) && isParticle(t, w[0])) {
        out.push(w[0]);
        return;
      }
      out.push(w.map(function (g) {
        return isToken(g) ? literal(g) : g;
      }).join('-'));
    });
    return joinWords(out);
  }

  function renderLatin(words, t) {
    var out = [];
    words.forEach(function (w) {
      if (isNumeral(w)) { out.push(w.text); return; }  // `.` and `:` included
      if (isPunct(w)) { out.push(w); return; }
      out.push(joinLatin(w.map(function (g) {
        if (isName(g)) return t.names[g.v.toLowerCase()];
        if (isNum(g)) return literal(g);
        return formOf(t, g);
      })));
    });
    return joinWords(out);
  }

  function renderHan(words, t) {
    var out = [];
    words.forEach(function (w) {
      if (isNumeral(w)) { out.push(w.text); return; }
      if (isPunct(w)) { out.push(w); return; }
      if (w.length === 1 && !isToken(w[0]) && has(DIGIT_WHEN_FREE, w[0])) {
        out.push(DIGIT_WHEN_FREE[w[0]]);
        return;
      }
      /* Names have no character; they stay in Latin inside Han text. */
      out.push(w.map(function (g) {
        if (isName(g)) return t.names[g.v.toLowerCase()];
        if (isNum(g)) return literal(g);
        return hanOf(t, g);
      }).join(''));
    });
    return joinWords(out);
  }

  /* --- what else a query is worth saying ----------------------------------- */

  /* Exact English equivalents, when the whole query is one root or compound. */
  function englishMatch(words, t) {
    var real = expandNumerals(words).filter(function (w) { return !isPunct(w); });
    if (real.length !== 1) return [];
    var word = real[0];
    if (word.some(isToken)) {
      return word.filter(isName).map(literal);
    }
    var gloss = word.join('-');
    var hits = (t.compoundEn[gloss] || []).slice();
    if (word.length === 1 && has(t.roots, gloss)) {
      var root = t.roots[gloss];
      hits.push(root.en + '  (root: ' + root.covers + ')');
    }
    return hits;
  }

  /* Blank is later than any number: nothing can be said about when a learner
     meets an unleveled root, so treat that as the hardest case. */
  function harder(a, b) {
    if (!a) return !b ? false : true;
    if (!b) return false;
    return Number(a) > Number(b);
  }

  /* "<level> (gloss, ...)" for the hardest roots used, or null if no roots. */
  function maxLevel(words, t) {
    var glosses = [];
    expandNumerals(words).forEach(function (word) {
      if (isPunct(word)) return;
      word.forEach(function (gloss) {
        if (!isToken(gloss) && has(t.roots, gloss) && glosses.indexOf(gloss) < 0) {
          glosses.push(gloss);
        }
      });
    });
    if (!glosses.length) return null;
    var top = levelOf(t, glosses[0]);
    glosses.forEach(function (g) {
      if (harder(levelOf(t, g), top)) top = levelOf(t, g);
    });
    var at = glosses.filter(function (g) { return levelOf(t, g) === top; });
    return top + ' (' + at.join(', ') + ')';
  }

  /* Everything the converter shows for one query, or an error saying which
     token it died on. */
  function lookup(text, t) {
    var fail = {};
    var result = parse(text, t, fail);
    if (!result.words) {
      return {
        ok: false,
        token: fail.token || null,
        error: fail.token === undefined
          ? 'not in roots.tsv, compounds.tsv or names.tsv'
          : (fail.why || 'is not in roots.tsv, compounds.tsv or names.tsv')
      };
    }
    return {
      ok: true,
      notation: result.notation,
      gloss: renderGloss(result.words, t),
      latin: renderLatin(result.words, t),
      han: renderHan(result.words, t),
      english: englishMatch(result.words, t),
      level: maxLevel(result.words, t)
    };
  }

  exports.tables = tables;
  exports.parse = parse;
  exports.lookup = lookup;
  exports.renderGloss = renderGloss;
  exports.renderLatin = renderLatin;
  exports.renderHan = renderHan;
  exports.englishMatch = englishMatch;
  exports.maxLevel = maxLevel;
  exports.expandNumerals = expandNumerals;
})(typeof module !== 'undefined' && module.exports
   ? module.exports
   : (window.pikotikaConvert = {}));
