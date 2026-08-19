/* Adapting a foreign name or word to Pikotika phonology.
 *
 * The rules are DETAILS.md, "Proper Nouns and Loan Words": first swap the
 * sounds we do not have, then fix the syllables that are still illegal.  This
 * is the first implementation of them anywhere -- pikotika.py does not adapt
 * names, it only looks them up in names.tsv.
 *
 * It works from *spelling*, because spelling is what a visitor can type.  A
 * real adaptation works from sound, which is why a handful of the standing
 * adaptations in names.tsv cannot be derived here (Eve -> Ivu goes by the
 * English vowel, not by the letters).  Where a name is recorded, the record
 * wins; the page says so.
 *
 * Loaded in the browser as window.pikotikaAdapt, and required by
 * build.py:check_adapter under node, which runs it over every row of
 * names.tsv.  Keep it dependency-free so both can use it.
 */
(function (exports) {
  'use strict';

  var VOWELS = 'aeiou';
  /* Codas Pikotika licenses: one of these four, or the three clusters, and the
     clusters only at the end of a word. */
  var CODA = 'nmsr';
  var FINAL_CLUSTERS = ['ns', 'ts', 'ks'];

  /* The length test matters: ''.indexOf on any string is 0, so without it the
     end of a word reads as a vowel. */
  function isVowel(c) { return !!c && c.length === 1 && VOWELS.indexOf(c) >= 0; }
  function isCoda(c) { return !!c && c.length === 1 && CODA.indexOf(c) >= 0; }

  /* "Use u, except after t, where o sounds more natural."  (Strout ends
     -to, Marek ends -ku.) */
  function helperVowel(after) { return after === 't' ? 'o' : 'u'; }

  /* --- pass one: the sounds ---------------------------------------------- */

  var DIGRAPHS = {
    sh: 's', ch: 't', th: 't', ph: 'v', qu: 'ku', ck: 'k', ng: 'n', wh: 'w'
  };

  var LETTERS = {
    b: 'p', d: 't', g: 'k', l: 'r', f: 'v', z: 's', j: 'y', q: 'k', x: 'ks',
    h: ''   /* h, and any silent letter, simply drops */
  };

  function sounds(word) {
    var out = '';
    var steps = [];
    var i = 0;
    while (i < word.length) {
      var pair = word.substr(i, 2);
      var c = word[i];

      if (DIGRAPHS.hasOwnProperty(pair)) {
        if (DIGRAPHS[pair] !== pair) steps.push(pair + ' → ' + DIGRAPHS[pair]);
        out += DIGRAPHS[pair];
        i += 2;
        continue;
      }
      /* A doubled consonant is one sound: penicillin -> penisirin, not
         ...irrin. */
      if (c === word[i + 1] && !isVowel(c)) {
        i += 1;
        steps.push(c + c + ' → ' + c);
        continue;
      }
      /* Silent final e: Alice -> aris, Eve -> ev.  The only silent letter we
         can find from spelling alone. */
      if (c === 'e' && i === word.length - 1 && i > 1 && !isVowel(word[i - 1])) {
        steps.push('silent e drops');
        i += 1;
        continue;
      }
      if (c === 'c') {
        var soft = 'eiy'.indexOf(word[i + 1]) >= 0;
        out += soft ? 's' : 'k';
        steps.push('c → ' + (soft ? 's' : 'k'));
        i += 1;
        continue;
      }
      /* y is a consonant before a vowel (Jan -> Yan) and a vowel otherwise
         (Mary -> Mari). */
      if (c === 'y' && !isVowel(word[i + 1] || '')) {
        out += 'i';
        if (i > 0) steps.push('y → i');
        i += 1;
        continue;
      }
      if (LETTERS.hasOwnProperty(c)) {
        if (LETTERS[c] === '') steps.push(c + ' drops');
        else steps.push(c + ' → ' + LETTERS[c]);
        out += LETTERS[c];
        i += 1;
        continue;
      }
      out += c;
      i += 1;
    }
    return { text: out, steps: steps };
  }

  /* --- pass two: the syllables -------------------------------------------- */

  /* Split into alternating vowel and consonant runs, so each consonant run can
     be judged on where it sits: at the start it is all onset, at the end all
     coda, and in between it is a coda and an onset back to back. */
  function runs(text) {
    var out = [];
    for (var i = 0; i < text.length; i++) {
      var kind = isVowel(text[i]) ? 'v' : 'c';
      if (out.length && out[out.length - 1].kind === kind) out[out.length - 1].text += text[i];
      else out.push({ kind: kind, text: text[i] });
    }
    return out;
  }

  function breakOnset(cluster) {
    /* Every consonant but the last gets a vowel of its own; the last one is
       the onset of the syllable that follows.  st- -> suto-, str- -> sutor-. */
    var out = '';
    for (var i = 0; i < cluster.length - 1; i++) {
      out += cluster[i] + helperVowel(cluster[i]);
    }
    return out + cluster[cluster.length - 1];
  }

  function fixFinal(cluster) {
    if (cluster.length === 1) {
      /* A bare final stop is not licensed (Marek -> Mareku), and neither is
         anything outside n m s r (Eve -> Ivu). */
      if (isCoda(cluster)) return cluster;
      return cluster + helperVowel(cluster);
    }
    if (cluster.length === 2 && FINAL_CLUSTERS.indexOf(cluster) >= 0) return cluster;
    /* Break the run open from the left and re-judge what is left at the end:
       Nils -> nirs -> nirus. */
    return cluster[0] + helperVowel(cluster[0]) + fixFinal(cluster.slice(1));
  }

  function fixMedial(cluster) {
    /* The last consonant is the onset of the syllable that follows.  Of what is
       left, only the one sitting right against the preceding vowel can be a
       coda, and only if it is one of n m s r; everything else needs a vowel of
       its own.  Inserting one creates a new syllable, so the consonant after it
       is a coda candidate again:

         inkris -> in.ku.ris   (n is a legal coda, k is not)
         akna   -> a.ku.na     (k cannot be a coda, so it takes a vowel) */
    var onset = cluster[cluster.length - 1];
    var rest = cluster.slice(0, -1);
    var out = '';
    var canCoda = true;
    for (var i = 0; i < rest.length; i++) {
      if (canCoda && isCoda(rest[i])) {
        out += rest[i];
        canCoda = false;
      } else {
        out += rest[i] + helperVowel(rest[i]);
        canCoda = true;
      }
    }
    return out + onset;
  }

  function syllables(text) {
    var parts = runs(text);
    var out = '';
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (part.kind === 'v') { out += part.text; continue; }
      if (i === 0) out += breakOnset(part.text);
      else if (i === parts.length - 1) out += fixFinal(part.text);
      else out += fixMedial(part.text);
    }
    /* A word with no vowel at all still needs one to carry a syllable. */
    if (!/[aeiou]/.test(out) && out) out += 'u';
    return out;
  }

  /* --- from sound --------------------------------------------------------
     The right input is pronunciation, not spelling: English *meter* is /mitər/,
     which is mitar, and no letter rule reaches that.  ARPAbet is what CMUdict
     gives, so that is what this takes; build-time tooling feeds it in and the
     result is recorded in names.tsv.

     The vowel map is the pronunciation table in DETAILS.md read backwards --
     Pikotika `e` is the vowel of *they*, so English EY lands there and IY lands
     on `i`, which is where *meter* and *Peter* get their first vowel. */

  var PHONE_VOWELS = {
    AA: 'a',   /* father  */  AE: 'a',   /* cat     */
    AH: 'a',   /* cup, and the schwa */
    AO: 'o',   /* thought */  AW: 'au',  /* mouth   */
    AY: 'ai',  /* price   */  EH: 'e',   /* dress   */
    ER: 'ar',  /* nurse -- the vowel plus its r, which Pikotika writes out */
    EY: 'e',   /* face    */  IH: 'i',   /* kit     */
    IY: 'i',   /* fleece  */  OW: 'o',   /* goat    */
    OY: 'oi',  /* choice  */  UH: 'u',   /* foot    */
    UW: 'u'    /* goose   */
  };

  var PHONE_CONSONANTS = {
    B: 'p', CH: 't', D: 't', DH: 't', F: 'v', G: 'k', HH: '', JH: 'y',
    K: 'k', L: 'r', M: 'm', N: 'n', NG: 'n', P: 'p', R: 'r', S: 's',
    SH: 's', T: 't', TH: 't', V: 'v', W: 'w', Y: 'y', Z: 's', ZH: 'y'
  };

  /* AA is the one phone Pikotika hears two ways.  It is the vowel of *father*,
     which is `a`'s target -- but it is also the vowel of *lot*, and `o` is
     defined as the vowel of *go* "or the o in long", which for most English
     speakers is that same sound.  Both readings are correct, so the spelling
     breaks the tie: Tom and Bob keep their o, Marta and Carla keep their a.

     The letters are matched to the phones by position, counting vowels in each
     -- Tomas is OW-AA against o-a, so its AA is the one spelled a.  Where the
     counts disagree (silent letters, mostly) the tie-break is skipped and AA
     falls back to `a`. */
  function vowelLetters(spelling) {
    return String(spelling || '').toLowerCase().replace(/[^aeiouy]/g, '');
  }

  /* phones: ARPAbet, stress digits allowed ("M IY1 T ER0").  spelling is
     optional and only ever breaks the AA tie. */
  function adaptPhones(phones, spelling) {
    var list = String(phones).trim().toUpperCase().split(/\s+/).filter(Boolean);
    var phoneVowels = list.filter(function (p) {
      return PHONE_VOWELS.hasOwnProperty(p.replace(/[0-9]/g, ''));
    });
    var letters = vowelLetters(spelling);
    var aligned = letters.length === phoneVowels.length ? letters : null;

    var out = '';
    var seen = 0;
    for (var i = 0; i < list.length; i++) {
      var phone = list[i].replace(/[0-9]/g, '');
      if (PHONE_VOWELS.hasOwnProperty(phone)) {
        if (phone === 'AA' && aligned && aligned[seen] === 'o') out += 'o';
        else out += PHONE_VOWELS[phone];
        seen += 1;
      } else if (PHONE_CONSONANTS.hasOwnProperty(phone)) {
        out += PHONE_CONSONANTS[phone];
      }
    }
    return { sounds: out, form: syllables(out) };
  }

  /* --- the whole job ------------------------------------------------------ */

  function adaptWord(word) {
    var capital = word[0] === word[0].toUpperCase() && word[0] !== word[0].toLowerCase();
    var clean = word.toLowerCase().replace(/[^a-z]/g, '');
    if (!clean) return { form: '', steps: [] };
    var first = sounds(clean);
    var form = syllables(first.text);
    var steps = first.steps.slice();
    if (form !== first.text) steps.push('syllables: ' + first.text + ' → ' + form);
    if (capital) form = form[0].toUpperCase() + form.slice(1);
    return { form: form, steps: steps };
  }

  function adaptName(text) {
    var words = String(text).trim().split(/\s+/).filter(Boolean);
    var forms = [], steps = [];
    for (var i = 0; i < words.length; i++) {
      var one = adaptWord(words[i]);
      if (!one.form) continue;
      forms.push(one.form);
      steps = steps.concat(one.steps);
    }
    /* Each substitution is worth showing once, in the order it first applies. */
    var seen = {}, unique = [];
    for (var j = 0; j < steps.length; j++) {
      if (!seen[steps[j]]) { seen[steps[j]] = 1; unique.push(steps[j]); }
    }
    return { form: forms.join(' '), steps: unique };
  }

  exports.adaptName = adaptName;
  exports.adaptPhones = adaptPhones;
})(typeof module !== 'undefined' && module.exports
   ? module.exports
   : (window.pikotikaAdapt = {}));
