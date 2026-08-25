/* Tests for web/js/syntax.js — the sentence bracketer.
 *
 *     node tests/syntax_test.js            run them
 *     node tests/syntax_test.js --corpus   also bracket every corpus sentence
 *     node tests/syntax_test.js --show 'Eko ri vite a nino.'   bracket one
 *
 * Every case is written as its bracket string, which is the whole point of
 * having one: a tree is hard to eyeball and a string is not.
 *
 *   word          a leaf
 *   (a b)         a branch, no name
 *   ri(a b)       a branch named for the particle that joins its two slots
 *   ri(_ b)       ...with the first slot empty -- a sentence with no subject
 *
 * So the expected value reads as the grouping it asserts.
 *
 * The examples are lifted from web/pages/grammar/*.html and corpus.tsv rather
 * than invented, so a case that fails is a disagreement with the spec rather
 * than with my idea of it.
 */

'use strict';

var path = require('path');
var syntax = require(path.join(__dirname, '..', 'web', 'js', 'syntax.js'));

var CASES = [

  // -- the basic frame (grammar/structure/) ---------------------------------
  ['Eko ri vite a nino.', 'ri(Eko a(vite nino))'],
  ['Eko ri ire.', 'ri(Eko ire)'],
  ['Nino ri vori a aku.', 'ri(Nino a(vori aku))'],
  ['Moto ri vin.', 'ri(Moto vin)'],
  // A two-word subject is exactly what ri is for.
  ['Eko vemapari ri vake a pona komi.',
   'ri((Eko vemapari) a(vake (pona komi)))'],

  // -- no subject at all (grammar/nosubject/) -------------------------------
  // A bare ri opens a sentence with no subject at all, which the empty first
  // slot is what records -- ri(_ ruva) is not ri(ruva).
  ['Ri ruva.', 'Ri(_ ruva)'],
  ['Ri sista!', 'Ri(_ sista)'],
  ['Sista!', 'Sista'],
  ['Ri marumkosa.', 'Ri(_ marumkosa)'],
  ['Ri nem marumkosa.', 'Ri(_ (nem marumkosa))'],
  ['Ri perti a eko irevaso.', 'Ri(_ a(perti (eko irevaso)))'],
  // A command has no ri and no subject; there is still an object.
  ['Pam komi.', '(Pam komi)'],
  ['Pam tonar a tis ver eko.', '(a((Pam tonar) tis) (ver eko))'],

  // -- a compound is one node, never broken ---------------------------------
  ['Eko ri tene a kasepeste.', 'ri(Eko a(tene kasepeste))'],
  ['Ekomen ri eksire.', 'ri(Ekomen eksire)'],

  // -- modifiers group to the right (grammar/modifier-order/) ---------------
  ['tu nova opus', '(tu (nova opus))'],
  ['Eko ri vori a nontis meka rus rotun.',
   'ri(Eko a(vori (nontis (meka (rus rotun)))))'],
  ['Eko ri vite a piko akupeste.', 'ri(Eko a(vite (piko akupeste)))'],
  ['Ekomen ri ire ver eko viropari kase.',
   'ri(Ekomen (ire (ver (eko (viropari kase)))))'],

  // A degree word takes only the word after it, not the phrase.
  ['Tisomo ri mas konten omo.', 'ri(Tisomo ((mas konten) omo))'],
  ['surmesur piko turan', '((surmesur piko) turan)'],
  ['eko mas anyomeka samparivema', '(eko ((mas anyomeka) samparivema))'],

  // Parallel modifiers are joined, not stacked.
  ['Eko ri tene a nero kum anka pitur.',
   'ri(Eko a(tene (nero kum (anka pitur))))'],

  // -- te forces the left grouping (grammar/te/) ----------------------------
  ['meka aku peste', '(meka (aku peste))'],
  ['meka aku te peste', 'te((meka aku) peste)'],
  ['Tis ri verte arpoaku komparroko.',
   'ri(Tis (verte (arpoaku komparroko)))'],
  ['Tis ri verte arpoaku te komparroko.',
   'ri(Tis te((verte arpoaku) komparroko))'],
  // te-groups combine leftward: the owner of a green-tea shop.
  ['Tisomo ri verte arpoaku te komparroko te teneomo.',
   'ri(Tisomo te(te((verte arpoaku) komparroko) teneomo))'],
  ['Tisomo ri piko komparmen te teneomo.',
   'ri(Tisomo te((piko komparmen) teneomo))'],

  // -- a subordinate clause is a whole sentence after a (grammar/subordinate/)
  ['Eko ri vori a tu ri veni.', 'ri(Eko a(vori ri(tu veni)))'],
  ['Ri tika a tempo ri moni.', 'Ri(_ a(tika ri(tempo moni)))'],
  ['Eko ri pensa a tis senseyan ri nonsorin.',
   'ri(Eko a(pensa ri((tis senseyan) nonsorin)))'],
  // Chained clauses nest rightward: want [try [eat [meat]]].
  ['Eko ri vori a tentar a komi a karne.',
   'ri(Eko a(vori a(tentar a(komi karne))))'],

  // -- relative clauses (grammar/relative/) ---------------------------------
  ['Omo ri komi rite peste.', 'rite(ri(Omo komi) peste)'],
  ['Omo ri komi te peste.', 'ri(Omo te(komi peste))'],
  ['Eko ri sape a tu ri sarve rite vema.',
   'ri(Eko a(sape rite(ri(tu sarve) vema)))'],

  // -- aspect closes the description, after the object (grammar/aspect/) ----
  ['Eko ri komi vin.', 'ri(Eko (komi vin))'],
  ['Eko ri vite a kanis vin.', 'ri(Eko (a(vite kanis) vin))'],
  ['Eko ri komi sista.', 'ri(Eko (komi sista))'],
  // Before a, the same word is the main verb instead.
  ['Pam sista a karo.', 'a((Pam sista) karo)'],
  ['Eko ri in tisroko sista.', 'ri(Eko ((in tisroko) sista))'],

  // -- prepositional phrases sit at the end (grammar/prepositions/) ---------
  ['Eko ri ire ver kase.', 'ri(Eko (ire (ver kase)))'],
  ['Eko ri vite a akupeste in aku.',
   'ri(Eko (a(vite akupeste) (in aku)))'],
  ['Eko ri in tisroko.', 'ri(Eko (in tisroko))'],
  ['Tis ri por tu.', 'ri(Tis (por tu))'],
  // kum inside a phrase joins rather than opening a second phrase.
  ['Karoroko ri mets komparroko kum ronkaaku.',
   'ri(Karoroko (mets (komparroko kum ronkaaku)))'],
  ['Eko ri komi kum tu.', 'ri(Eko (komi (kum tu)))'],

  // -- kum joining subjects, not opening a phrase (grammar/joining/) --------
  ['Nino kum eko ri komivori.', 'ri((Nino kum eko) komivori)'],

  // -- a framing phrase in front (grammar/structure/, grammar/aspect/) ------
  ['Yanyer, eko ri vite a kanis.', '(Yanyer ri(eko a(vite kanis)))'],

  // -- conditions are two sentences (grammar/conditions/) -------------------
  ['Pos tu ri veni, tisrason ekomen ri konten.',
   '((Pos ri(tu veni)) (tisrason ri(ekomen konten)))'],
  ['Nonves eko ri tene a moni, tisrason eko ri kompar a tis.',
   '((Nonves ri(eko a(tene moni))) (tisrason ri(eko a(kompar tis))))'],

  // -- questions rearrange nothing (grammar/questions/) ---------------------
  ['Panyu ri kerroko?', 'ri(Panyu kerroko)'],
  ['Tu ri ire ver kerroko?', 'ri(Tu (ire (ver kerroko)))'],
  ['Tu nova opus ri ker?', 'ri((Tu (nova opus)) ker)'],
  ['Tu ri sape a Karra in kermoto?',
   'ri(Tu (a(sape Karra) (in kermoto)))'],

  // -- a name follows its category word (grammar/modifiers/) ----------------
  ['Eko ri ire ver sitas Rispan.',
   'ri(Eko (ire (ver (sitas Rispan))))'],

  // -- mood words are ordinary modifiers (grammar/mood/) --------------------
  ['Eko ri kan ire.', 'ri(Eko (kan ire))'],
  ['Eko ri neses tika ver nontisomo.',
   'ri(Eko ((neses tika) (ver nontisomo)))'],
  ['Ekomen ri kan yer komi.', 'ri(Ekomen (kan (yer komi)))'],

  // -- negation is a modifier like any other (grammar/negation/) ------------
  ['Eko ri non komi a akupeste.', 'ri(Eko a((non komi) akupeste))'],
  ['Tis ri non tuke.', 'ri(Tis (non tuke))'],

  // -- comparison (grammar/comparison/) -------------------------------------
  ['Tis ri mas pona vons nontis.',
   'ri(Tis ((mas pona) (vons nontis)))'],
  ['Tis ri mas vetus vons pan.', 'ri(Tis ((mas vetus) (vons pan)))'],

  // -- because, and a tag on the end (grammar/joining/, grammar/questions/) --
  ['Eko ri ire ver kase, rason eko ri kansa.',
   '(ri(Eko (ire (ver kase))) (rason ri(eko kansa)))'],
  ['Tu ri vite a kanis, ker?', '(ri(Tu a(vite kanis)) ker)'],
  ['Ri reke a tis, ker?', '(Ri(_ a(reke tis)) ker)'],
  ['Eko ri neses tika ver nontisomo, kerrason?',
   '(ri(Eko ((neses tika) (ver nontisomo))) kerrason)'],
  ['Sets pam veni in 7 ora, kum ekomen ri kan yer komi.',
   '(Sets (((pam veni) (in (7 ora))) (kum ri(ekomen (kan (yer komi))))))'],

  // The one case subordinate/ warns about: after a comma, a joined clause is
  // swallowed into the open object clause, which is why that page says to end
  // the sentence and start a new one instead. The diagram shows the swallow.
  ['Eko ri vori a tu ri veni, kum eko ri vori a tisomo ri komi.',
   'ri(Eko a(vori (ri(tu veni) (kum ri(eko a(vori ri(tisomo komi)))))))'],
  ['Eko ri vori a tu ri veni; kum eko ri vori a tisomo ri komi.',
   'ri(Eko a(vori ri(tu veni))) | (kum ri(eko a(vori ri(tisomo komi))))'],

  // te and rite name the node that joins the modifier to its head, rather than
  // sitting beside them as a third child: they are the word that facilitates
  // the attachment, not something being attached. Written `te(mod head)`, which
  // is why `(x ri y)` and `te(x y)` read as the different shapes they are.
  ['Ri kompar a arpoaku rite komparroko ri vin.',
   'ri(rite(Ri(_ a(kompar arpoaku)) komparroko) vin)'],
  ['Tu ri tonar ver eko rite yave ri sur tapur.',
   'ri(rite(ri(Tu (tonar (ver eko))) yave) (sur tapur))'],
  ['Tu ri vake rite komi ri meka pona.',
   'ri(rite(ri(Tu vake) komi) (meka pona))'],

  // -- two sentences in one string ------------------------------------------
  ['Eko ri komi. Tu ri ire.', 'ri(Eko komi) | ri(Tu ire)']
];

/* -- edge cases that should not throw or silently mangle ------------------- */

var EDGE = [
  ['', false],
  ['   ', false],
  ['.', false],
  ['ri', true],
  ['Si.', true],
  ['Non vite.', true],
  ['Eko ri ire ver kase in tisroko kum tu vin.', true],
  ['Pam tonar a tu ri tene rite kosa ver eko, kum eko ri kita a nontis parte.',
   true]
];

/* -- runner ---------------------------------------------------------------- */

function bracketOf(text) {
  var result = syntax.parse(text);
  if (!result.ok) return 'ERROR: ' + result.error;
  return result.sentences.map(syntax.bracket).join(' | ');
}

function run() {
  var failed = 0;
  CASES.forEach(function (pair) {
    var got = bracketOf(pair[0]);
    if (got !== pair[1]) {
      failed++;
      console.log('FAIL  ' + JSON.stringify(pair[0]));
      console.log('  want  ' + pair[1]);
      console.log('  got   ' + got);
    }
  });

  EDGE.forEach(function (pair) {
    var result;
    try {
      result = syntax.parse(pair[0]);
    } catch (e) {
      failed++;
      console.log('FAIL  ' + JSON.stringify(pair[0]) + ' threw ' + e.message);
      return;
    }
    if (result.ok !== pair[1]) {
      failed++;
      console.log('FAIL  ' + JSON.stringify(pair[0]) + ' -> ok=' + result.ok +
                  ', wanted ok=' + pair[1] +
                  (result.error ? ' (' + result.error + ')' : ''));
    }
  });

  var total = CASES.length + EDGE.length;
  console.log((failed ? failed + ' of ' + total + ' failed'
                      : total + ' cases pass'));
  return failed;
}

/* Bracketing every corpus sentence is not an assertion -- there is no
   authored answer to compare against -- but it is the check that matters
   most: parse() refuses a sentence it cannot bracket without losing a word,
   so a clean run over 406 authored sentences says the rigid word order really
   does come apart mechanically. */
function corpus() {
  var fs = require('fs');
  var lines = fs.readFileSync(path.join(__dirname, '..', 'corpus.tsv'), 'utf8')
    .split('\n').filter(Boolean);
  var head = lines.shift().split('\t');
  var col = head.indexOf('latin');
  var bad = [], skipped = 0;
  lines.forEach(function (line) {
    var latin = line.split('\t')[col];
    if (!latin) return;
    if (!syntax.diagrammable(latin)) { skipped++; return; }
    var result = syntax.parse(latin);
    if (!result.ok) bad.push(latin + '  -- ' + result.error);
  });
  console.log('\ncorpus: ' + (lines.length - skipped) + ' sentences with ri, ' +
              skipped + ' without (commands and fragments, not diagrammed)');
  if (bad.length) {
    console.log(bad.length + ' could not be bracketed:');
    bad.slice(0, 20).forEach(function (b) { console.log('  ' + b); });
  } else {
    console.log('all bracketed with no word lost');
  }
  return bad.length;
}

var argv = process.argv.slice(2);
if (argv[0] === '--show') {
  console.log(bracketOf(argv.slice(1).join(' ')));
} else {
  var failures = run();
  if (argv.indexOf('--corpus') >= 0) failures += corpus();
  process.exit(failures ? 1 : 0);
}
