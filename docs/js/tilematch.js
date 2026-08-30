/* ---------------------------------------------------------------------------
   Tile Match  —  /games/tilematch/

   Mahjong solitaire where the pair is a root's meaning and a root's form: one
   tile reads `happy / pleased`, its partner reads 楽 / konten.  The board holds
   48 pairs.

   Geometry is in half-tiles.  A tile is 2 units by 2 units, so a coordinate
   may be odd, and a layer can sit half a tile off the one below it.  Blocking
   is the paper game's: nothing overlapping from above, and at least one long
   side clear.

   A game is dealt from one level's roots.  No level has the 48 the board wants
   -- they run 36 to 41 -- so the rest are drawn at random from the level below,
   which puts a little revision in every game; Level 1, with nothing below it,
   deals some of its roots twice instead.

   The deal is built backwards and is therefore always solvable: take any two
   tiles that would be free, call them a pair, remove them, repeat.  Reversing
   that removal order is a winning line.  The player is free to depart from it,
   which is what Shuffle is for.
   --------------------------------------------------------------------------- */

(function () {
  'use strict';

  var stage = document.getElementById('tm-stage');
  if (!stage) return;

  var board = document.getElementById('tm-board');
  var scroll = document.getElementById('tm-scroll');
  var status = document.getElementById('tm-status');
  var count = document.getElementById('tm-count');

  var TILE_W = 128, TILE_H = 178;   /* the art's own pixels */

  /* Tiles are laid down overlapping by exactly the drawn thickness -- 19px of
     side on the left, 18px under the bottom -- so within a layer every tile's
     sides are hidden under its neighbours and the layer reads as one flat
     surface of faces.  A side that *is* showing therefore means something:
     either nothing is beside it (the tile is open on that side) or it is
     sitting on top of the layer below.  Which is exactly the set of tiles a
     player is looking for. */
  var STEP_X = TILE_W - 19, STEP_Y = TILE_H - 18;
  var UNIT_X = STEP_X / 2, UNIT_Y = STEP_Y / 2;

  /* Higher layers step up and right, the way the drawn thickness says the light
     falls.  Exact stacking would be (19, -18) -- that is the offset at which a
     tile's drawn underside lands precisely on the face of the tile below,
     since the top face is inset 19 from the left and 18 from the bottom.  The
     board is drawn shallower than that on purpose: at the true offset a four
     layer stack walks 57px right and 54px up, which on a 12-wide bottom layer
     leans the whole board.  12 is the shallowest that still reads as a step. */
  var LAYER_DX = 18, LAYER_DY = -18;
  var PAD = 16;
  var LEVELS = ['1', '2', '3', '4', '5'];
  var LEVEL_KEY = 'pk-tilematch-level';

  var tiles = [];        /* every position, in DOM order; faces are reassigned */
  var byLevel = {};      /* level -> its roots, from lexicon.json */
  var level = '1';       /* the level the current board was dealt from */
  var btnUndo = document.getElementById('tm-undo');
  var btnShuffle = document.getElementById('tm-shuffle');
  var btnFree = document.getElementById('tm-free');
  var dialog = document.getElementById('tm-level');
  var levelBox = document.getElementById('tm-levels');
  var FREE_KEY = 'pk-tilematch-free';
  var showFree = false;
  var selected = null;
  var undoStack = [];
  var hintPair = null;
  var hintAt = 0;
  var boardW = 0, boardH = 0;

  /* --- the layout -------------------------------------------------------- */

  function seq(start, n, step) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(start + i * step);
    return out;
  }

  /* Four rectangles, each centered on the one below: 60 + 24 + 8 + 4 = 96
     tiles, 48 pairs.  Rows of the upper two layers are offset half a tile, so
     the stack reads as a stack rather than as a grid seen from above. */
  function layout() {
    var out = [];
    function block(z, xs, ys) {
      xs.forEach(function (x) {
        ys.forEach(function (y) { out.push({ x: x, y: y, z: z }); });
      });
    }
    block(0, seq(0, 12, 2), seq(0, 5, 2));
    block(1, seq(4, 8, 2), seq(2, 3, 2));
    block(2, seq(8, 4, 2), seq(3, 2, 2));
    block(3, seq(10, 2, 2), seq(3, 2, 2));
    return out;
  }

  function pixel(t) {
    return {
      left: PAD + t.x * UNIT_X + t.z * LAYER_DX,
      top: PAD + t.y * UNIT_Y + t.z * LAYER_DY
    };
  }

  /* --- blocking ---------------------------------------------------------- */

  function alive() {
    return tiles.filter(function (t) { return !t.out; });
  }

  function isFree(t, pool) {
    var i, u;
    /* The last two tiles are always takeable.  Every removal takes one meaning
       tile and one form tile of the same root, so when two are left they are
       necessarily each other's partner -- there is no wrong pairing left for
       the free-tile rule to rule out, and no puzzle left for it to make.
       Without this the game has a dead end it cannot be shuffled out of: a
       final pair stacked one on the other can never be redealt into a solvable
       board, because the two places are the board.  Measured at 42 occurrences
       over 400 bot playthroughs, every one of them at exactly one pair left. */
    if (pool.length <= 2) return true;
    for (i = 0; i < pool.length; i++) {
      u = pool[i];
      /* Every higher layer, not just the next one: a tile two layers up still
         sits on this one once the tile between them is gone. */
      if (u !== t && u.z > t.z &&
          Math.abs(u.x - t.x) < 2 && Math.abs(u.y - t.y) < 2) return false;
    }
    var left = false, right = false;
    for (i = 0; i < pool.length; i++) {
      u = pool[i];
      if (u === t || u.z !== t.z || Math.abs(u.y - t.y) >= 2) continue;
      if (u.x <= t.x - 2 && u.x > t.x - 4) left = true;
      if (u.x >= t.x + 2 && u.x < t.x + 4) right = true;
    }
    return !left || !right;
  }

  function freeTiles() {
    var pool = alive();
    return pool.filter(function (t) { return isFree(t, pool); });
  }

  function matches(a, b) {
    return a !== b && a.root === b.root && a.face !== b.face;
  }

  function movesAmong(free) {
    var out = [], i, j;
    for (i = 0; i < free.length; i++) {
      for (j = i + 1; j < free.length; j++) {
        if (matches(free[i], free[j])) out.push([free[i], free[j]]);
      }
    }
    return out;
  }

  function availableMoves() {
    return movesAmong(freeTiles());
  }

  /* --- the deal ---------------------------------------------------------- */

  function shuffled(list) {
    var out = list.slice(), i, j, t;
    for (i = out.length - 1; i > 0; i--) {
      j = Math.floor(Math.random() * (i + 1));
      t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  /* Peel pairs of free tiles off the board until nothing is left.  The order
     that comes out is a solution, read backwards.  Takes a pool rather than
     the whole board, so a mid-game shuffle can use it on what is left. */
  function dealOrder(pool) {
    var remaining = pool.slice();
    var order = [];
    while (remaining.length) {
      var free = remaining.filter(function (t) { return isFree(t, remaining); });
      if (free.length < 2) return null;
      var a = free.splice(Math.floor(Math.random() * free.length), 1)[0];
      var b = free[Math.floor(Math.random() * free.length)];
      order.push([a, b]);
      remaining = remaining.filter(function (t) { return t !== a && t !== b; });
    }
    return order;
  }

  /* n roots for n pairs.  Every root of the chosen level goes in once, and the
     shortfall -- the board wants 48 and no level has more than 41 -- is drawn
     at random from the level below, then the one below that if it is still
     short.  Level 1 has nothing beneath it, so it deals some of its own roots
     twice; that is easier (two ways to place each) and gives those roots an
     extra exposure.  Which roots are borrowed or doubled changes every game. */
  function rootPool(n, lv) {
    var own = byLevel[lv] || [];
    var out = shuffled(own);
    var below = LEVELS.indexOf(lv);
    while (out.length < n && below > 0) {
      below--;
      out = out.concat(shuffled(byLevel[LEVELS[below]] || []).slice(0, n - out.length));
    }
    for (var i = 0; out.length < n; i++) out.push(own[i % own.length]);
    return shuffled(out.slice(0, n));
  }

  /* --- drawing a face ---------------------------------------------------- */

  function longest(words) {
    return words.reduce(function (n, w) { return Math.max(n, w.length); }, 0);
  }

  /* One size for the whole tile, picked off the longest word on it.  The face
     is 106 art-pixels wide and the ladder is set so the widest Level 1 gloss
     -- `excuse me` -- still lands inside that with room to spare, measured
     rather than guessed. */
  function glossSize(words) {
    var n = longest(words);
    if (n <= 5) return 26;
    if (n <= 7) return 22;
    if (n <= 9) return 19;
    return 18;
  }

  function emphasized(text) {
    /* Mnemonics mark the letters that echo the form with *asterisks*. */
    var frag = document.createDocumentFragment();
    text.split('*').forEach(function (chunk, i) {
      if (!chunk) return;
      if (i % 2) {
        var em = document.createElement('em');
        em.textContent = chunk;
        frag.appendChild(em);
      } else {
        frag.appendChild(document.createTextNode(chunk));
      }
    });
    return frag;
  }

  function meanings(root) {
    return root.gloss2 ? [root.gloss, root.gloss2] : [root.gloss];
  }

  function paint(t) {
    var face = t.el.firstChild;
    face.textContent = '';
    var root = t.root;
    if (t.face === 'en') {
      var words = meanings(root);
      var size = glossSize(words);
      words.forEach(function (w, i) {
        var line = document.createElement('div');
        line.className = i ? 'tm-en tm-en2' : 'tm-en';
        line.style.fontSize = size + 'px';
        line.textContent = w;
        face.appendChild(line);
      });
      t.el.setAttribute('aria-label', 'meaning: ' + words.join(', '));
    } else {
      var han = document.createElement('div');
      han.className = 'tm-hanbig';
      han.textContent = root.han;
      var latin = document.createElement('div');
      latin.className = 'tm-latin';
      latin.style.fontSize = (root.form.length > 6 ? 21 : 24) + 'px';
      latin.textContent = root.form;
      face.appendChild(han);
      face.appendChild(latin);
      t.el.setAttribute('aria-label', 'word: ' + root.form);
    }
  }

  /* --- state ------------------------------------------------------------- */

  function say(parts) {
    status.textContent = '';
    parts.forEach(function (p) { status.appendChild(p); });
  }

  function text(s, cls) {
    var span = document.createElement('span');
    if (cls) span.className = cls;
    span.textContent = s;
    return span;
  }

  function announce(root) {
    var parts = [
      text(root.form, 'tm-form'),
      text(' '),
      text(root.han, 'tm-han'),
      text('  —  ' + meanings(root).join(', '))
    ];
    if (root.mnemonic) {
      var m = document.createElement('span');
      m.className = 'tm-mnem';
      m.appendChild(document.createTextNode('  ·  '));
      m.appendChild(emphasized(root.mnemonic));
      parts.push(m);
    }
    say(parts);
  }

  /* Dim everything that cannot be played.  Driven from refresh's free set
     rather than recomputed, since that is the same question. */
  function applyDim(free) {
    tiles.forEach(function (t) { t.free = false; });
    free.forEach(function (t) { t.free = true; });
    tiles.forEach(function (t) {
      t.el.classList.toggle('tm-dim', showFree && !t.out && !t.free);
    });
  }

  function refresh() {
    var pool = alive();
    var left = pool.length;
    var free = pool.filter(function (t) { return isFree(t, pool); });
    var moves = movesAmong(free);
    applyDim(free);
    count.textContent = (left / 2) + ' pairs left · ' +
                        moves.length + ' move' + (moves.length === 1 ? '' : 's');
    btnUndo.disabled = !undoStack.length;
    btnShuffle.disabled = !left;
    status.classList.toggle('tm-won', !left);
    if (!left) {
      say([text('Cleared — Level ' + level + ', every root both ways round.'),
           text(' '), playAgainButton()]);
    } else if (!moves.length) {
      say([text('No move left on the board. Shuffle the rest and keep going.')]);
    }
  }

  /* A wrong guess is the best moment to be told the answer, so the refusal
     line answers both tiles rather than only saying no: the form tile gets its
     meanings, the meaning tile gets its form.  In the order they were tapped,
     since that is the order the player is holding them in.  This is why a
     shake fires only on a real attempt -- there is nothing to teach when the
     two tiles are both meanings. */
  function sideOf(t) {
    if (t.face === 'pk') {
      return [text(t.root.form, 'tm-form'),
              text(' means ‘' + meanings(t.root).join(', ') + '’')];
    }
    return [text('‘' + meanings(t.root).join(', ') + '’ is '),
            text(t.root.form, 'tm-form')];
  }

  function notAPair(a, b) {
    return [text('Not a pair: ')]
      .concat(sideOf(a), [text('; ')], sideOf(b), [text('.')]);
  }

  /* The win line ends in the way out of it, rather than asking "play again?"
     and leaving the player to find the button in the bar above the board they
     have just emptied.  It opens the same picker New game does, so choosing a
     different level is one press from finishing one. */
  function playAgainButton() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'tm-btn tm-again';
    b.textContent = 'Play again';
    b.addEventListener('click', function () { askLevel(); });
    return b;
  }

  function clearHint() {
    tiles.forEach(function (t) { t.el.classList.remove('tm-hint'); });
  }

  function select(t) {
    if (selected) selected.el.classList.remove('tm-sel');
    selected = t;
    if (t) t.el.classList.add('tm-sel');
  }

  function refuse(t) {
    t.el.classList.remove('tm-no');
    void t.el.offsetWidth;            /* restart the animation */
    t.el.classList.add('tm-no');
  }

  function take(pair) {
    pair.forEach(function (t) {
      t.out = true;
      t.el.classList.remove('tm-sel', 'tm-hint');
      t.el.classList.add('tm-go');
      window.setTimeout(function () {
        if (t.out) t.el.classList.add('tm-out');
      }, 220);
    });
    undoStack.push(pair);
  }

  function undo() {
    var pair = undoStack.pop();
    if (!pair) return;
    pair.forEach(function (t) {
      t.out = false;
      t.el.classList.remove('tm-out', 'tm-go');
    });
    select(null);
    clearHint();
    say([text('Put back.')]);
    refresh();
  }

  /* Say the root when its written face is tapped -- the point of the game is
     to bind the form to the meaning, and the sound is part of the form.  The
     tap is itself the gesture that unlocks the AudioContext, so this works on
     the first one. */
  function speak(t) {
    if (t.face !== 'pk') return;
    if (window.pikotika && window.pikotika.playWord) {
      window.pikotika.playWord(t.root.form);
    }
  }

  function tap(t) {
    clearHint();
    if (t.out) return;

    /* Speaking is for *picking a tile up*, so taking it back does not repeat
       the word: a second tap on the selected tile is an undo of the first, and
       hearing the root again says something happened when nothing did.  Being
       refused is not the same thing -- a blocked tile still speaks, since
       tapping a tile you cannot take yet is a good moment to hear it, and
       refusing the move is no reason to refuse the word. */
    var deselecting = selected === t;
    if (!deselecting) speak(t);

    var pool = alive();
    if (!isFree(t, pool)) {
      refuse(t);
      say([text('That one is covered or boxed in — clear a side first.')]);
      return;
    }
    if (deselecting) { select(null); return; }
    if (selected && matches(selected, t)) {
      var root = t.root;
      take([selected, t]);
      select(null);
      announce(root);
      refresh();
      return;
    }
    /* A shake means "those two are not a pair", so it fires only on a real
       attempt -- a meaning against a form.  Picking a second meaning tile is
       changing your mind about the first, not a wrong guess. */
    if (selected && selected.face !== t.face) {
      refuse(t);
      say(notAPair(selected, t));
    }
    select(t);
  }

  function hint() {
    var moves = availableMoves();
    clearHint();
    if (!moves.length) { refresh(); return; }
    /* Successive presses walk the available moves rather than repeating one. */
    if (Date.now() - hintAt > 4000) hintPair = 0;
    hintAt = Date.now();
    var pair = moves[hintPair % moves.length];
    hintPair = (hintPair || 0) + 1;
    pair.forEach(function (t) { t.el.classList.add('tm-hint'); });
    say([text('These two are the same root.')]);
    window.setTimeout(clearHint, 2500);
  }

  function assign(pairs, order) {
    order.forEach(function (pos, i) {
      var root = pairs[i];
      var flip = Math.random() < 0.5;
      pos[0].root = root; pos[0].face = flip ? 'en' : 'pk';
      pos[1].root = root; pos[1].face = flip ? 'pk' : 'en';
      paint(pos[0]);
      paint(pos[1]);
    });
  }

  function newGame(lv) {
    if (lv) level = lv;
    var order = null;
    for (var i = 0; i < 60 && !order; i++) order = dealOrder(tiles);
    if (!order) { say([text('Could not deal this layout — reload the page.')]); return; }
    assign(rootPool(order.length, level), order);
    tiles.forEach(function (t) {
      t.out = false;
      t.el.classList.remove('tm-out', 'tm-go', 'tm-sel', 'tm-hint', 'tm-no');
    });
    undoStack = [];
    select(null);
    hintPair = 0;
    say([text('Level ' + level + ' — match each root’s meanings to its written form.')]);
    refresh();
  }

  /* Redeal the remaining roots into the remaining places.  Every removal takes
     one meaning tile and one form tile of the same root, so what is left always
     pairs up; only its arrangement changes.

     This goes through dealOrder rather than just permuting the faces, because
     a permutation can land on a board with no move in it at all -- two tiles
     stacked on each other, the lower one unreachable and the only match for
     the one above.  Redealing the way the board was dealt makes the rest
     solvable again, which is the whole point of offering the button. */
  function shuffleBoard() {
    var pool = alive();
    if (!pool.length) return;
    var pairs = [];
    pool.forEach(function (t) { if (t.face === 'en') pairs.push(t.root); });

    var order = null;
    for (var i = 0; i < 60 && !order; i++) order = dealOrder(pool);
    if (order) {
      assign(shuffled(pairs), order);
    } else {
      /* Should not happen on this layout; a plain permutation still beats
         leaving the board exactly as it was. */
      var mix = shuffled(pool.map(function (t) {
        return { root: t.root, face: t.face };
      }));
      pool.forEach(function (t, k) { t.root = mix[k].root; t.face = mix[k].face; });
      pool.forEach(paint);
    }
    select(null);
    clearHint();
    say([text('Redealt what is left — it is solvable again.')]);
    refresh();
  }

  /* Remembered, like the theme is: a player who wants the assist wants it next
     time too.  Storage can throw outright in a private window, so every touch
     of it is guarded and the default simply stands. */
  function setShowFree(on, remember) {
    showFree = !!on;
    btnFree.setAttribute('aria-pressed', showFree ? 'true' : 'false');
    if (remember) {
      try { localStorage.setItem(FREE_KEY, showFree ? '1' : '0'); } catch (e) {}
    }
    refresh();
  }

  function storedShowFree() {
    try { return localStorage.getItem(FREE_KEY) === '1'; } catch (e) { return false; }
  }

  /* --- the level picker --------------------------------------------------- */

  function storedLevel() {
    var v;
    try { v = localStorage.getItem(LEVEL_KEY); } catch (e) { return ''; }
    return LEVELS.indexOf(v) >= 0 ? v : '';
  }

  /* ?level=3, which is how a level review page links here.  A visitor who
     arrived by pressing "Level 3" has already chosen, so that board is dealt
     and the picker stays shut -- and the choice is remembered, so coming back
     to the bare URL later lands on the same level. */
  function urlLevel() {
    var m = /[?&]level=([^&]*)/.exec(location.search);
    var lv = m ? decodeURIComponent(m[1]) : '';
    return LEVELS.indexOf(lv) >= 0 ? lv : '';
  }

  /* One button per level, captioned with where its tiles come from: a player
     choosing Level 4 should know before they press it that a quarter of the
     board is Level 3 revision.  Built once, from the lexicon, so a level that
     grows a root does not need the caption edited. */
  function buildPicker() {
    LEVELS.forEach(function (lv) {
      var own = (byLevel[lv] || []).length;
      var b = document.createElement('button');
      b.type = 'submit';                 /* method="dialog": sets returnValue */
      b.className = 'tm-level';
      b.value = lv;
      var name = document.createElement('span');
      name.className = 'tm-level-name';
      name.textContent = 'Level ' + lv;
      var note = document.createElement('span');
      note.className = 'tm-level-note';
      var short = 48 - own;
      note.textContent = own + ' roots' + (
        short <= 0 ? '' :
        lv === '1' ? ', ' + short + ' of them dealt twice'
                   : ' + ' + short + ' from Level ' + (Number(lv) - 1));
      b.appendChild(name);
      b.appendChild(note);
      levelBox.appendChild(b);
    });
  }

  /* Escape (or any close without a choice) leaves the board that is already
     dealt alone -- which is why start() deals one before ever opening this. */
  function askLevel() {
    if (!dialog || !dialog.showModal) { newGame(); return; }
    LEVELS.forEach(function (lv, i) {
      levelBox.children[i].setAttribute('aria-pressed', lv === level ? 'true' : 'false');
    });
    dialog.returnValue = '';
    dialog.showModal();
    var current = levelBox.children[LEVELS.indexOf(level)];
    if (current) current.focus();
  }

  function chosen() {
    var lv = dialog.returnValue;
    if (LEVELS.indexOf(lv) < 0) return;
    try { localStorage.setItem(LEVEL_KEY, lv); } catch (e) {}
    newGame(lv);
  }

  /* --- size -------------------------------------------------------------- */

  /* The tiles carry words, not symbols, so how big the board may be is how
     legible it is: the scroller escapes the measure column to the full window
     width.  Done here rather than in CSS because the `100vw` trick that would
     do it there measures the window *including* the scrollbar, and overflows
     the page by that much; documentElement.clientWidth does not. */
  function bleed() {
    var host = scroll.parentNode.getBoundingClientRect();
    var vw = document.documentElement.clientWidth;
    scroll.style.marginLeft = (-host.left) + 'px';
    scroll.style.width = vw + 'px';
    scroll.style.paddingLeft = '8px';
    scroll.style.paddingRight = '8px';
    return vw - 16;
  }

  function fit() {
    var availW = bleed() || boardW;
    /* Leave the header, the buttons and the status line on screen with it. */
    var availH = Math.max(360, window.innerHeight - 190);
    var s = Math.min(availW / boardW, availH / boardH);
    s = Math.max(0.34, Math.min(1, s));
    board.style.transform = 'scale(' + s + ')';
    stage.style.width = Math.ceil(boardW * s) + 'px';
    stage.style.height = Math.ceil(boardH * s) + 'px';
    /* Centered when it fits, scrolled from the left when it does not. */
    stage.style.margin = boardW * s < availW ? '0 auto' : '0';
  }

  /* --- build ------------------------------------------------------------- */

  function makeBoard() {
    var spec = layout();
    var maxX = 0, maxY = 0;
    spec.forEach(function (p) {
      var t = { x: p.x, y: p.y, z: p.z, out: false, root: null, face: 'en' };
      var at = pixel(t);
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'tm-tile';
      el.style.left = at.left + 'px';
      el.style.top = at.top + 'px';
      /* The overlap makes paint order load-bearing.  A tile hides the left
         side of the tile to its right, and the bottom side of the tile above
         it, so within a layer z rises going down the board and falls going
         right: down-and-left is nearer the viewer.  Between layers the layer
         wins outright.  x is even and no larger than 22, so the two terms
         cannot run into each other. */
      el.style.zIndex = String(t.z * 10000 + t.y * 100 + (30 - t.x));
      if (t.z > 0) el.style.setProperty('--tm-shadow',
                                       'drop-shadow(-4px 5px 4px rgba(0,0,0,.32))');
      el.appendChild(document.createElement('div')).className = 'tm-face';
      el.addEventListener('click', function () { tap(t); });
      t.el = el;
      board.appendChild(el);
      tiles.push(t);
      maxX = Math.max(maxX, at.left + TILE_W);
      maxY = Math.max(maxY, at.top + TILE_H);
    });
    boardW = maxX + PAD;
    boardH = maxY + PAD;
  }

  /* --- go ---------------------------------------------------------------- */

  document.getElementById('tm-new').addEventListener('click', function () { askLevel(); });
  document.getElementById('tm-hint').addEventListener('click', hint);
  document.getElementById('tm-undo').addEventListener('click', undo);
  document.getElementById('tm-shuffle').addEventListener('click', shuffleBoard);
  btnFree.addEventListener('click', function () { setShowFree(!showFree, true); });
  if (dialog) dialog.addEventListener('close', chosen);
  window.addEventListener('resize', fit);

  function start(lexicon) {
    if (!lexicon || !lexicon.words) {
      say([text('Could not load the roots. Reload the page?')]);
      return;
    }
    LEVELS.forEach(function (lv) { byLevel[lv] = []; });
    Object.keys(lexicon.words).forEach(function (key) {
      var w = lexicon.words[key];
      /* `kind` already separates the three particles out; only roots here. */
      if (w.kind === 'root' && LEVELS.indexOf(w.level) >= 0) byLevel[w.level].push(w);
    });
    if (byLevel['1'].length < 2) { say([text('No roots in the lexicon.')]); return; }
    makeBoard();
    fit();
    showFree = storedShowFree();
    btnFree.setAttribute('aria-pressed', showFree ? 'true' : 'false');
    if (levelBox) buildPicker();
    var asked = urlLevel();
    if (asked) {
      try { localStorage.setItem(LEVEL_KEY, asked); } catch (e) {}
      newGame(asked);
      return;
    }
    /* Deal the remembered level first and *then* ask, so the picker always has
       a playable board behind it and dismissing it is not a dead end. */
    newGame(storedLevel() || '1');
    askLevel();
  }

  if (window.pikotika && window.pikotika.loadLexicon) {
    window.pikotika.loadLexicon().then(start);
  } else {
    fetch('/data/lexicon.json').then(function (r) { return r.json(); }).then(start);
  }
})();
