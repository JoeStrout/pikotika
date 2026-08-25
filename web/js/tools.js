/* The converter on /tools/ — the wiring only.
 *
 * The conversion itself is web/js/convert.js, a port of pikotika.py checked
 * against it on every build (build.py:check_convert); the tables it runs on are
 * web/data/convert.json, dumped straight out of pikotika.Tables.
 *
 * A page script rather than part of site.js, because the tables are 140 KB and
 * the converter is the only thing on the site that wants them.  It reaches the
 * sitewide helpers through window.pikotika, which is what that object is for.
 */
(function () {
  'use strict';

  var box = document.getElementById('converter');
  if (!box || !window.pikotikaConvert) return;

  var input = document.getElementById('converter-in');
  var out = document.getElementById('converter-out');
  var note = document.getElementById('converter-note');
  var diagram = document.getElementById('converter-tree');
  var site = window.pikotika || {};

  /* The four lines the converter writes, in the order pikotika.py prints them.
     `cls` is what the value is written in: Latin gets chips, Han gets the Han
     face, and gloss and English are ordinary text. */
  var ROWS = [
    { key: 'gloss', label: 'Gloss', cls: 'gloss' },
    { key: 'latin', label: 'Latin', cls: 'pk' },
    { key: 'han', label: 'Han', cls: 'han' },
    { key: 'english', label: 'English', cls: 'en' }
  ];

  var tables = null;
  var asked = false;
  var pending = false;

  /* Fetched on the first keystroke, not on page load: a reader who scrolls past
     the box should not pay for the tables. */
  function want() {
    if (asked) return;
    asked = true;
    note.textContent = 'Loading the lexicon…';
    fetch('/data/convert.json' + (site.dataVersion || ''))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (payload) {
        if (!payload) throw new Error('no data');
        tables = window.pikotikaConvert.tables(payload);
        note.textContent = '';
        if (pending) run();
      })
      .catch(function () {
        note.textContent = 'The lexicon would not load, so the converter ' +
          'cannot run. Reloading the page usually fixes it.';
      });
  }

  function row(label, cls, value) {
    var dt = document.createElement('dt');
    dt.textContent = label;
    var dd = document.createElement('dd');
    var span = document.createElement('span');
    span.className = cls;
    span.textContent = value;
    dd.appendChild(span);
    out.appendChild(dt);
    out.appendChild(dd);
  }

  /* The box fits what is in it, in both directions: the field grows with a long
     query rather than scrolling inside two rows, and nothing below it is held
     open by a reserved height.  `height = auto` first, or scrollHeight only
     ever measures the height the field already has and the field never
     shrinks again. */
  function autosize() {
    input.style.height = 'auto';
    input.style.height = input.scrollHeight + 'px';
  }

  /* --- the diagram --------------------------------------------------------
     web/js/syntax.js brackets the Latin into a tree; this draws it. The tree
     is unlabeled, so an internal node is a junction and nothing more, and
     every word sits at a leaf.

     A word is a `.pk` span, which is what makes it tappable: site.js chips
     each word inside a `.pk` and opens the usual entry. Words only -- a `.pk`
     around a branch would nest, and chipify would wrap the same words twice.

     A **te** or **rite** node carries its particle as its name, and the name is
     drawn where the junction dot would be. It is a `.pk` too, so the particle
     that does the joining opens its own entry from the spot in the tree where
     it is doing the joining. */

  function word(text) {
    var span = document.createElement('span');
    span.className = 'pk';
    span.textContent = text;
    return span;
  }

  function treeNode(node) {
    var li = document.createElement('li');
    if (node.w !== undefined) {
      li.appendChild(word(node.w));
      return li;
    }
    if (node.n) {
      var name = word(node.n);
      name.classList.add('tree-name');
      li.appendChild(name);
    } else {
      var join = document.createElement('span');
      join.className = 'tree-join';
      join.setAttribute('aria-hidden', 'true');
      li.appendChild(join);
    }
    var list = document.createElement('ul');
    /* An empty first slot gets drawn rather than skipped. A sentence with no
       subject really does have one -- "there IS a subject, but it's
       unspecified" (/grammar/nosubject/) -- so the slot is named for what it
       holds instead of leaving the particle hanging over a single child.
       Not a `.pk`: the word is English, and a chip on it would open nothing. */
    if (node.at === 0) {
      var gap = document.createElement('li');
      var mark = document.createElement('i');
      mark.className = 'tree-empty';
      mark.textContent = node.n.toLowerCase() === 'ri' ? 'indefinite' : '—';
      gap.appendChild(mark);
      list.appendChild(gap);
    }
    node.c.forEach(function (child) { list.appendChild(treeNode(child)); });
    li.appendChild(list);
    return li;
  }

  function drawTree(latin) {
    diagram.textContent = '';
    if (!window.pikotikaSyntax || !window.pikotikaSyntax.diagrammable(latin)) {
      return;
    }
    var parsed = window.pikotikaSyntax.parse(latin);
    if (!parsed.ok) return;
    parsed.sentences.forEach(function (tree) {
      var root = document.createElement('ul');
      root.appendChild(treeNode(tree));
      var wrap = document.createElement('div');
      wrap.className = 'tree';
      /* The sentence is one readable string to a screen reader; the tree is a
         picture of it, and reading out every junction would not help. */
      wrap.setAttribute('role', 'img');
      wrap.setAttribute('aria-label', 'Sentence diagram of ' +
                        window.pikotikaSyntax.words(tree).join(' '));
      wrap.appendChild(root);
      diagram.appendChild(wrap);
    });
    if (site.scanChips) site.scanChips(diagram);
  }

  function run() {
    var text = input.value.trim();
    autosize();
    out.textContent = '';
    if (diagram) diagram.textContent = '';
    if (!text) {
      note.textContent = '';
      pending = false;
      return;
    }
    want();
    if (!tables) { pending = true; return; }
    pending = false;

    var result = window.pikotikaConvert.lookup(text, tables);
    if (!result.ok) {
      note.textContent = result.token
        ? 'No match — “' + result.token + '” ' + result.error + '.'
        : 'No match — ' + result.error + '.';
      return;
    }

    ROWS.forEach(function (spec) {
      var value = result[spec.key];
      if (spec.key === 'english') {
        /* Only a query that is exactly one root, compound or name has an
           English equivalent to print; a sentence has none. */
        if (!value || !value.length) return;
        value = value.join('; ');
      }
      if (!value) return;
      row(spec.label, spec.cls, value);
    });

    /* Nothing else is printed.  `lookup` also answers which notation the query
       was read as and how hard the roots in it are, and neither earns its line:
       the parser tries gloss first and gloss notation accepts a bare English
       name, so **Alice** comes back "read as gloss" and a numeral comes back as
       whichever notation was asked first — true, and useless to say — while a
       root level is a fact about the course, which is not what anyone is at
       this box for.  Both are still returned, and check_convert still compares
       them against pikotika.py. */
    note.textContent = '';

    if (site.scanChips) site.scanChips(out);
    if (diagram) drawTree(result.latin);
  }

  /* The query rides in the hash, as it does on Vocab: a conversion is exactly
     the sort of thing worth linking someone to. */
  function setHash(text) {
    var next = text ? '#' + encodeURIComponent(text) : '';
    if ((location.hash || '') === next) return;
    /* replaceState, not a push: someone trying six sentences in a row should
       not have to press Back six times.  It also does not fire hashchange, so
       writing the hash cannot loop back into reading it. */
    history.replaceState(null, '', location.pathname + next);
  }

  function fromHash() {
    var raw = location.hash.replace(/^#/, '');
    if (!raw) return '';
    try { return decodeURIComponent(raw); } catch (e) { return raw; }
  }

  input.addEventListener('input', function () {
    setHash(input.value.trim());
    run();
  });

  window.addEventListener('hashchange', function () {
    input.value = fromHash();
    run();
  });

  var examples = box.querySelectorAll('.reader-eg');
  for (var i = 0; i < examples.length; i++) {
    examples[i].addEventListener('click', function (event) {
      input.value = event.currentTarget.textContent;
      input.focus();
      setHash(input.value);
      run();
    });
  }

  input.value = fromHash();
  run();
})();
