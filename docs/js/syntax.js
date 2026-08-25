/* Pikotika — bracketing a sentence into its tree.
 *
 * Takes Latin notation and returns a tree: which words group with which, and
 * nothing else. Latin because that is what the converter already produces from
 * any of the four notations, and what a word chip looks a word up by.
 *
 * **Only the particles name a node.** A particle is the word that facilitates a
 * join, not a thing being joined, so it names the node it makes and its two
 * slots hold content: `ri(Eko a(vite nino))`. That leaves every leaf a content
 * word.
 *
 * **Nothing else is labeled.** Pikotika roots have no part of speech
 * (grammar/predicate/: the same root is a noun in one slot and a verb in
 * another), so a diagram that wrote "verb" over a node would be claiming
 * something the language does not say. The structure carries what matters.
 *
 * **A compound is one node.** Compounds are written solid in Latin, so they
 * arrive as a single token and stay one — a dictionary entry is not a phrase
 * built in running speech, and breaking **kasepeste** into *home* + *animal*
 * would diagram the etymology rather than the sentence.
 *
 * The grammar it implements is web/pages/grammar/*.html, and the rules that do
 * the work are:
 *
 *   - S RI V A O, rigidly, and **ri** is never dropped (structure/)
 *   - only one **ri** per clause, so a second one after **a** opens a
 *     subordinate clause (subordinate/)
 *   - an **a** clause runs to the end, so chained objects nest rightward
 *     (subordinate/)
 *   - modifiers group to the right by default (modifier-order/)
 *   - **te** reaches back to the last particle and forces the left grouping,
 *     and te-groups combine leftward (te/)
 *   - **rite** closes a relative clause that modifies the noun after it
 *     (relative/)
 *   - an aspect marker closes the whole description, after the object
 *     (aspect/)
 *   - a prepositional phrase sits at the end (prepositions/)
 *
 * Loaded in the browser as window.pikotikaSyntax; required by
 * tests/syntax_test.js under node. Dependency-free, so both can use it.
 *
 *     var t = pikotikaSyntax.parse('Eko ri vite a nino.');
 *     pikotikaSyntax.bracket(t.sentences[0]);   // ri(Eko a(vite nino))
 */
(function (exports) {
  'use strict';

  /* --- the closed classes --------------------------------------------------
     These are grammar, not vocabulary, so they are written out here rather
     than looked up: the set of particles and prepositions is fixed, and a
     parser that had to fetch the lexicon to find its own boundaries would be
     unusable offline and untestable on the command line. */

  /* The eleven of grammar/prepositions/. */
  var PREP = { 'in': 1, ver: 1, vons: 1, kum: 1, por: 1, sur: 1, tun: 1,
               nir: 1, eks: 1, mets: 1, topi: 1 };

  /* grammar/joining/: these work at any size, between two words or two
     clauses. **kum** is in both tables and the ambiguity is real — see the
     `kumPrep` note on predicate() below. */
  var JOIN = { kum: 1, sive: 1, sets: 1 };

  /* grammar/aspect/: apa, vin and sista close the description when they come
     last. Before **a** they are the main verb instead, which is why position
     rather than the word decides. */
  var ASPECT = { apa: 1, vin: 1, sista: 1 };

  /* grammar/modifier-order/: a degree word modifies the word directly after
     it, not the phrase — *mas konten omo* is a [more happy] person.
     **meka** and **piko** are deliberately NOT here. They are degree words
     too ('very', 'slightly'), but they are equally the ordinary adjectives
     'big' and 'small', and that page names *meka rus rotun* as "one real
     ambiguity" settled by context and stress — neither of which a parser has.
     Left out, they group to the right like any modifier, which is the reading
     that page's own example takes ('that big red ball'). */
  var DEGREE = { mas: 1, nonmas: 1, surmesur: 1 };

  /* grammar/conditions/: pos … tisrason, or nonves … tisrason. */
  var CONDITION = { pos: 1, nonves: 1 };
  var CONSEQUENCE = 'tisrason';

  /* Words that open a clause of their own after a comma. **rason** is the noun
     'reason' and also 'because' (joining/), and **tisrason** 'therefore' both
     closes a condition and heads a consequence. */
  var OPENER = { kum: 1, sive: 1, sets: 1, rason: 1, tisrason: 1,
                 pos: 1, nonves: 1 };

  var PUNCT = ',.:;?!' + '、。：；？！';

  /* --- the tree ------------------------------------------------------------
     A node is a leaf holding one word, or a branch holding children. That is
     the whole data structure; there are no labels and no node types. */

  function leaf(word) { return { w: word }; }

  /* A named branch: a particle is the name of the join it makes rather than a
     thing sitting beside the things it joins. All four work this way -- they
     are the words that *facilitate* an attachment, not anything being
     attached -- so a named node holds only content and answers to its
     particle: **ri** joins a subject to a predicate, **a** a verb to its
     object, **te** a modifier to its head, **rite** a clause to its noun.

     `at` is the child index the name is spoken before, which is 1 in the
     ordinary case and 0 where the first slot is empty: a sentence with no
     subject at all opens with a bare **ri** (grammar/nosubject/). */
  function named(name, children, at) {
    children = children.filter(Boolean);
    if (!children.length) return leaf(name);
    return { n: name, c: children, at: at === undefined ? 1 : at };
  }

  /* The two-slot case, where either slot may be empty. */
  function joinNode(name, first, second) {
    return named(name, [first, second], first ? 1 : 0);
  }

  function branch(children) {
    /* Empty children are dropped here rather than guarded at every call site:
       an adjacent pair of particles leaves a group with nothing in it, and a
       branch holding a null is what turns a bad parse into a crash. */
    children = children.filter(Boolean);
    if (!children.length) return null;
    /* A group of one is not a group -- that is what keeps ((x)) out. */
    if (children.length === 1) return children[0];
    return { c: children };
  }

  function isLeaf(node) { return !!node && node.w !== undefined; }

  /* The unambiguous string form the tests compare: a leaf is its word, a
     branch is its children in parentheses. */
  function bracket(node) {
    if (!node) return '';
    if (isLeaf(node)) return node.w;
    /* A named node is written `te(mod head)`, an unnamed one `(a b)`. Keeping
       them apart matters: **ri** and **a** are still ordinary children, so
       `(x ri y)` and `te(x y)` are different shapes and have to read as
       different strings. */
    if (!node.n) return '(' + node.c.map(bracket).join(' ') + ')';
    /* An empty first slot is written `_`, so `ri(_ ruva)` -- a sentence with no
       subject -- cannot be confused with `ri(ruva)`, which would be one with no
       predicate. The blank is a fact about the sentence, not a gap in the
       notation. */
    var parts = node.c.map(bracket);
    if (node.at === 0) parts.unshift('_');
    return node.n + '(' + parts.join(' ') + ')';
  }

  /* Every word in the tree, left to right — for checking that nothing was
     dropped or duplicated, which is the one invariant a bracketing must keep. */
  function words(node, into) {
    into = into || [];
    if (isLeaf(node)) { into.push(node.w); return into; }
    node.c.forEach(function (child, i) {
      /* The name is spoken where it sits in the sentence: *verte arpoaku*
         **te** *komparroko*, and **ri** in front when there is no subject. */
      if (node.n && i === node.at) into.push(node.n);
      words(child, into);
    });
    if (node.n && node.at >= node.c.length) into.push(node.n);
    return into;
  }

  /* --- lexing --------------------------------------------------------------
     Punctuation is peeled off the ends of each whitespace-delimited word, as
     pikotika.py does it, and does not enter the tree: a comma is a boundary
     signal, not a constituent. What survives is which token ended a sentence
     and which was followed by a comma, both of which the parse needs. */

  function lex(text) {
    var out = [];
    String(text).split(/\s+/).forEach(function (raw) {
      if (!raw) return;
      var lead = 0, tail = raw.length;
      while (lead < tail && PUNCT.indexOf(raw[lead]) >= 0) lead++;
      while (tail > lead && PUNCT.indexOf(raw[tail - 1]) >= 0) tail--;
      var word = raw.slice(lead, tail);
      if (!word) return;
      var after = raw.slice(tail);
      out.push({
        w: word,
        k: word.toLowerCase(),
        comma: after.indexOf(',') >= 0,
        end: /[.?!;。？！；]/.test(after),
        first: out.length === 0
      });
    });
    return out;
  }

  function split(tokens) {
    var out = [], run = [];
    tokens.forEach(function (tok) {
      run.push(tok);
      if (tok.end) { out.push(run); run = []; }
    });
    if (run.length) out.push(run);
    return out;
  }

  /* --- helpers over a token run -------------------------------------------- */

  /* A token is normally one word, but a reduced relative clause rides in the
     stream as a token carrying its finished subtree -- which is what lets the
     rest of the parser go on treating it as one opaque modifier. */
  function nodeOf(tok) { return tok.node || leaf(tok.w); }

  /* The index of the first token matching, or -1. Particles never nest inside
     one another at the same depth -- **te** and **rite** are reduced before
     anything scans for **ri** or **a** -- so a flat scan is enough. */
  function find(tokens, test, from) {
    for (var i = from || 0; i < tokens.length; i++) {
      if (test(tokens[i], i)) return i;
    }
    return -1;
  }

  function isName(tok, opts) {
    if (tok.node) return false;
    if (opts && opts.isName) return !!opts.isName(tok.w);
    /* Names are capitalized in every notation (grammar/writing/). At the start
       of a sentence every word is, so case says nothing there. */
    return !tok.first && /^[A-Z]/.test(tok.w);
  }

  /* --- phrases -------------------------------------------------------------
     A modifier phrase: no particles left in it except **te**, which has
     already been split out by phrase() below. */

  function run(tokens, opts) {
    if (!tokens.length) return null;
    if (tokens.length === 1) {
      /* A **rite** with nothing after it has no head to join to; the particle
         still has to appear, or the bracketing would lose a word. */
      return tokens[0].rel ? named(tokens[0].rel, [tokens[0].node])
                           : nodeOf(tokens[0]);
    }

    /* A joining word makes its two sides parallel rather than stacked
       (modifier-order/: *nero kum anka pitur*, two colors in one slot). It
       binds looser than anything else here, so it is taken first. */
    var join = find(tokens, function (t) { return JOIN[t.k]; });
    if (join > 0 && join < tokens.length - 1) {
      return branch([run(tokens.slice(0, join), opts), nodeOf(tokens[join]),
                     run(tokens.slice(join + 1), opts)]);
    }

    /* A proper noun follows its category word instead of preceding it
       (modifiers/: *omo Ar*, *sitas Rispan*), so it binds to the word on its
       left rather than reaching right like every other modifier. */
    for (var i = 1; i < tokens.length; i++) {
      if (isName(tokens[i], opts)) {
        var pair = branch([nodeOf(tokens[i - 1]), nodeOf(tokens[i])]);
        var rest = tokens.slice(0, i - 1);
        var tail = tokens.slice(i + 1);
        var head = tail.length ? branch([pair, run(tail, opts)]) : pair;
        return rest.length ? stackRight(rest, head, opts) : head;
      }
    }

    return stackRight(tokens.slice(0, -1), nodeOf(tokens[tokens.length - 1]),
                      opts);
  }

  /* Modifiers group to the right: the last one combines with the head first,
     and each earlier one scopes over everything after it. A degree word is the
     exception -- it takes only the word directly after it. */
  function stackRight(mods, head, opts) {
    for (var i = mods.length - 1; i >= 0; i--) {
      if (mods[i].rel) {
        head = named(mods[i].rel, [mods[i].node, head]);
      } else if (i > 0 && DEGREE[mods[i - 1].k]) {
        head = branch([branch([nodeOf(mods[i - 1]), nodeOf(mods[i])]), head]);
        i--;
      } else {
        head = branch([nodeOf(mods[i]), head]);
      }
    }
    return head;
  }

  /* A phrase, including any **te** in it. te-groups combine leftward: that is
     the whole job of the particle, and it is what makes
     *verte arpoaku te komparroko te teneomo* the owner of a green-tea shop
     rather than a shop-owner who is green tea. */
  function phrase(tokens, opts) {
    if (!tokens.length) return null;
    var groups = [], current = [], marks = [];
    tokens.forEach(function (tok) {
      if (tok.k === 'te') {
        groups.push(current);
        marks.push(tok);
        current = [];
      } else {
        current.push(tok);
      }
    });
    groups.push(current);
    if (groups.length === 1) return run(groups[0], opts);

    var node = run(groups[0], opts);
    for (var i = 1; i < groups.length; i++) {
      node = named(marks[i - 1].w, [node, run(groups[i], opts)]);
    }
    return node;
  }

  /* --- relative clauses ----------------------------------------------------
     **rite** closes a clause and hangs it on the noun that follows
     (grammar/relative/). Reduced before anything else looks for **ri**, since
     the clause has a **ri** of its own and it is not the clause's own. */

  /* Where the clause closed by the **rite** at `at` begins. Scanning back, it
     "takes at most one verb with its objects, **ri**, and one subject,
     stopping at the first word that would break that order" -- so it crosses
     an **a**, since objects are part of it, but only until it has taken a
     **ri** and the subject in front of that. */
  function relativeStart(tokens, at) {
    var i = at - 1, seenRi = false;
    while (i >= 0) {
      var k = tokens[i].k;
      if (k === 'te' || k === 'rite') break;
      if (k === 'ri') {
        if (seenRi) break;
        seenRi = true;
      } else if (k === 'a' && seenRi) {
        break;
      }
      i--;
    }
    return i + 1;
  }

  /* Replace each **rite** clause with a single token carrying its subtree, so
     that everything downstream -- which is looking for this clause's own
     **ri** -- never sees the clause's. */
  function reduceRelative(tokens, opts) {
    var at = find(tokens, function (t) { return t.k === 'rite'; });
    if (at < 0) return tokens;
    var start = relativeStart(tokens, at);
    var inner = clause(tokens.slice(start, at), opts);
    /* The clause travels as a token, and `rel` is what says the node joining it
       to its head is named for the **rite** rather than merely containing it.
       The head is not known yet -- it is whatever the ordinary right-branching
       modifier rule gives it -- so the naming happens where they meet. */
    var stand = { w: tokens[at].w, k: '', node: inner, rel: tokens[at].w,
                  comma: tokens[at].comma, end: false, first: start === 0 };
    return reduceRelative(tokens.slice(0, start).concat([stand])
                          .concat(tokens.slice(at + 1)), opts);
  }

  /* --- predicates ----------------------------------------------------------
     Everything after **ri**. */

  /* `kumPrep` says whether a **kum** in this predicate opens a phrase or joins
     two things in one slot. **kum** is both 'with' and 'and' (prepositions/,
     joining/) and the two are genuinely ambiguous -- *tene a nero kum anka
     pitur* joins two colors inside the object, while *komi kum tu* opens a
     phrase -- so one thing decides it for the whole predicate: **kum** is
     'with' only where there is no object for it to be joining onto. It is
     settled once, at the top, and passed down, or the object's own recursion
     would see no **a** in front of it and answer differently. */
  function predicate(tokens, opts, kumPrep) {
    if (!tokens.length) return null;
    if (kumPrep === undefined) {
      kumPrep = find(tokens, function (t) { return t.k === 'a'; }) < 0;
    }

    /* An aspect marker closes the whole description, so it comes off last and
       sits outermost. Only when something precedes it: a bare **vin** is the
       verb 'finish', not a marker with nothing to mark. */
    var last = tokens[tokens.length - 1];
    if (tokens.length > 1 && ASPECT[last.k]) {
      return branch([predicate(tokens.slice(0, -1), opts, kumPrep),
                     leaf(last.w)]);
    }

    /* The whole predicate may be prepositional and nothing else -- that is how
       Pikotika says *is here*, *is for you* (prepositions/). Taken before the
       scan below, or a **kum** inside such a phrase reads as a second phrase
       opening: *mets komparroko kum ronkaaku* is one phrase, not two. */
    if (isPrep(tokens[0], kumPrep)) {
      return branch(prepPhrases(tokens, opts, kumPrep));
    }

    var at = find(tokens, function (t) { return t.k === 'a'; });
    var prep = find(tokens, function (t, i) {
      return i > 0 && isPrep(t, kumPrep);
    });

    /* Which of the two splits first.

       A preposition ahead of the **a** belongs to the head: an object clause
       "runs to the end" and there is "no way back out of it" (subordinate/),
       so a phrase that would otherwise trail has to sit in front instead --
       *voritika ver komivakeomo a tis ri ...*, where **ver komivakeomo** names
       the cook and the clause is what is asked of them.

       A preposition after the **a** trails the sentence and comes off first --
       unless what follows the **a** is a whole clause, which runs to the end
       and keeps its own phrases inside it. */
    var objectIsClause = at >= 0 && find(tokens, function (t, i) {
      return i > at && t.k === 'ri';
    }) >= 0;
    if (at >= 0 && (prep < 0 || prep < at || objectIsClause)) {
      var head = tokens.slice(0, at);
      var rest = tokens.slice(at + 1);
      /* Chained objects nest rightward: each **a** clause runs to the end, so
         *vori a tentar a komi a karne* is want [try [eat [meat]]]. */
      var object = rest.length ? clause(rest, opts, kumPrep) : null;
      return joinNode(tokens[at].w,
                      head.length ? predicate(head, opts, kumPrep) : null,
                      object);
    }

    if (prep > 0) {
      return branch([predicate(tokens.slice(0, prep), opts, kumPrep)]
                    .concat(prepPhrases(tokens.slice(prep), opts, kumPrep)));
    }

    return phrase(tokens, opts);
  }

  function isPrep(tok, kumPrep) {
    if (!PREP[tok.k]) return false;
    return tok.k === 'kum' ? kumPrep : true;
  }

  /* Trailing phrases, one node each: *ire ver kase in tisroko* is two, not one
     long one. **kum** never starts one of these -- once inside a phrase it is
     'and', which is what keeps *mets komparroko kum ronkaaku* a single phrase
     with two things in it rather than two phrases. */
  function prepPhrases(tokens, opts, kumPrep) {
    var out = [], start = 0;
    for (var i = 1; i <= tokens.length; i++) {
      if (i === tokens.length || (tokens[i].k !== 'kum' &&
                                  isPrep(tokens[i], kumPrep))) {
        out.push(branch([nodeOf(tokens[start]),
                         phrase(tokens.slice(start + 1, i), opts)]));
        start = i;
      }
    }
    return out;
  }

  /* --- clauses -------------------------------------------------------------
     One **ri** per clause. */

  function clause(tokens, opts, kumPrep) {
    if (!tokens.length) return null;

    /* A condition is two ordinary sentences with markers on the front of each
       (grammar/conditions/). */
    if (CONDITION[tokens[0].k]) {
      var then = find(tokens, function (t) { return t.k === CONSEQUENCE; });
      if (then > 0) {
        return branch([
          branch([leaf(tokens[0].w), clause(tokens.slice(1, then), opts)]),
          branch([leaf(tokens[then].w), clause(tokens.slice(then + 1), opts)])
        ]);
      }
    }

    /* A joining word may open a sentence, picking up from the one before
       (joining/: "Sets may open a sentence, exactly as English But… does").
       It takes the whole clause after it, not just the first word. */
    if (tokens.length > 1 && OPENER[tokens[0].k] && !tokens[0].comma &&
        !CONDITION[tokens[0].k]) {
      return branch([leaf(tokens[0].w), clause(tokens.slice(1), opts, kumPrep)]);
    }

    /* A yes-or-no tag sits at the end after a comma, since there is no slot in
       the sentence to put the question word in (questions/). One word, so it
       is recognized by shape rather than by a list -- **ker**, **non** and
       **si**, but also **kerrason** and anything else a speaker tags on. */
    if (tokens.length > 2 && tokens[tokens.length - 2].comma) {
      return branch([clause(tokens.slice(0, -1), opts, kumPrep),
                     leaf(tokens[tokens.length - 1].w)]);
    }

    /* A comma followed by one of those opens a second clause -- *ire ver kase,
       rason eko ri kansa*.

       Except where an object clause is already open, which is the one case
       subordinate/ warns about: there the joined clause "would be swallowed
       into the object clause", and the fix is a semicolon rather than a comma.
       Modeling that is the point -- a diagram that quietly read the intended
       grouping would hide exactly the mistake the page tells you to avoid. */
    var joinAt = find(tokens, function (t, i) {
      return t.comma && i + 1 < tokens.length && OPENER[tokens[i + 1].k];
    });
    if (joinAt >= 0 && !objectClauseOpen(tokens, joinAt)) {
      return branch([clause(tokens.slice(0, joinAt + 1), opts, kumPrep),
                     clause(tokens.slice(joinAt + 1), opts, kumPrep)]);
    }

    /* A relative clause carries a **ri** that is not this clause's, so it is
       reduced to a single token before anything scans for one. */
    tokens = reduceRelative(tokens, opts);
    if (tokens.length === 1 && tokens[0].node) {
      return named(tokens[0].rel, [tokens[0].node]);
    }

    /* A phrase in front, set off by a comma, frames the sentence rather than
       being its subject (structure/: *Yanyer, eko ri vite a kanis*). */
    var comma = find(tokens, function (t) { return t.comma; });
    var ri = find(tokens, function (t) { return t.k === 'ri'; });
    if (comma >= 0 && (ri < 0 || comma < ri) && comma < tokens.length - 1) {
      return branch([clause(tokens.slice(0, comma + 1), opts),
                     clause(tokens.slice(comma + 1), opts)]);
    }

    var subject = tokens.slice(0, ri);
    if (ri < 0) {
      /* No **ri**: a command, a fragment, or an answer. Nothing to split on,
         so it is one phrase -- with any object still marked by **a**. */
      return predicate(tokens, opts, kumPrep);
    }

    return joinNode(tokens[ri].w,
                    subject.length ? phrase(subject, opts) : null,
                    predicate(tokens.slice(ri + 1), opts, kumPrep));
  }

  /* Is an **a** clause still open at `upto`? Only a clause counts -- a plain
     noun object closes on its own. */
  function objectClauseOpen(tokens, upto) {
    var at = find(tokens, function (t, i) { return i < upto && t.k === 'a'; });
    if (at < 0) return false;
    return find(tokens, function (t, i) {
      return i > at && i <= upto && t.k === 'ri';
    }) >= 0;
  }

  /* --- the entry point ----------------------------------------------------- */

  function parse(text, opts) {
    opts = opts || {};
    var tokens = lex(text);
    if (!tokens.length) return { ok: false, error: 'nothing to parse' };

    var trees = split(tokens).map(function (run) {
      return clause(run, opts);
    }).filter(Boolean);
    if (!trees.length) return { ok: false, error: 'nothing to parse' };

    /* The one invariant worth asserting: a bracketing rearranges nothing. */
    var flat = [];
    trees.forEach(function (tree) { words(tree, flat); });
    var want = tokens.map(function (t) { return t.w; });
    if (flat.join(' ') !== want.join(' ')) {
      return { ok: false, error: 'the bracketing lost or moved a word: ' +
               want.join(' ') + ' -> ' + flat.join(' ') };
    }
    return { ok: true, sentences: trees };
  }

  /* Does this text have a clause worth diagramming? A command has no **ri**
     and no subject, so there is no frame to draw. */
  function diagrammable(text) {
    return lex(text).some(function (t) { return t.k === 'ri'; });
  }

  exports.parse = parse;
  exports.bracket = bracket;
  exports.words = words;
  exports.diagrammable = diagrammable;
  exports.lex = lex;
})(typeof module !== 'undefined' && module.exports
   ? module.exports
   : (window.pikotikaSyntax = {}));
