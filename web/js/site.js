/* Pikotika — site behavior.  Deliberately tiny; nothing here is required for
   the page to be readable, only for it to be comfortable. */

(function () {
  'use strict';

  /* --- theme toggle ------------------------------------------------------
     Three states, not two: "light", "dark", and unset (follow the system).
     The toggle flips to whichever is the opposite of what is showing now, so
     the first tap always visibly changes something. */

  var root = document.documentElement;
  var button = document.getElementById('theme-toggle');
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  function currentlyDark() {
    var set = root.dataset.theme;
    if (set === 'dark') return true;
    if (set === 'light') return false;
    return media.matches;
  }

  if (button) {
    button.addEventListener('click', function () {
      var next = currentlyDark() ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem('pk-theme', next); } catch (e) {}
      syncWordmark();
    });
  }

  /* The wordmark is a <picture> whose <source> swaps on prefers-color-scheme,
     so that it is still right with JavaScript off.  But a matching <source>
     outranks the <img> src, which would override an explicit toggle -- so once
     we are running, drop the <source> and drive the <img> ourselves. */

  var picture = document.querySelector('.wordmark picture');
  if (picture) {
    var sources = picture.querySelectorAll('source');
    for (var i = 0; i < sources.length; i++) sources[i].remove();
  }

  function syncWordmark() {
    var img = document.querySelector('.wordmark img');
    if (!img) return;
    img.src = currentlyDark() ? '/images/Title_Dark.png'
                              : '/images/Title_Light.png';
  }

  media.addEventListener('change', syncWordmark);
  syncWordmark();

  /* --- collapsing header on mobile --------------------------------------
     Scrolling down hides the wordmark row and leaves the nav; scrolling back
     to the top restores it.  A dead band keeps it from flickering. */

  var lastY = window.scrollY;
  var ticking = false;

  function onScroll() {
    var y = window.scrollY;
    if (Math.abs(y - lastY) > 6) {
      document.body.classList.toggle('scrolled', y > 72 && y > lastY);
      lastY = y;
    }
    if (y <= 8) document.body.classList.remove('scrolled');
    ticking = false;
  }

  window.addEventListener('scroll', function () {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(onScroll);
    }
  }, { passive: true });
})();
