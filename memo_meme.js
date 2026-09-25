/* ══════════════════════════════════════════════════════════════════════════
   memo_meme.js — site-wide meme touches (loaded on every page)
   · "Random meme" button in the navbar → a meme card with its name as Impact
     bottom text, plus Another / Open
   · Caption banners: page titles become white Impact "top text" over a strip
     of real memes from the corpus
   Reads memes_lite.json (a small index built by build_memes_lite.py).
   ══════════════════════════════════════════════════════════════════════════ */
(function() {
  'use strict';

  var CDN = 'https://i.kym-cdn.com/';
  var memesPromise = null;
  var BANNER_SELECTOR = [
    '#page-about .page-inner > h1',
    '#page-disclaimer .page-inner > h1',
    '#page-dataset .page-inner > h1',
    '.th-title h1',
    '.editor-title'
  ].join(',');

  function loadMemes() {
    if (!memesPromise) {
      memesPromise = fetch('memes_lite.json')
        .then(function(r) { return r.ok ? r.json() : []; })
        .catch(function() { return []; });
    }
    return memesPromise;
  }
  function imgUrl(m) { return /^https?:/.test(m.i) ? m.i : CDN + m.i; }
  function nameOf(slug) {
    return String(slug || '').replace(/^_+/, '').split('-').map(function(w) {
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pick(list, n) {
    var out = [], used = {};
    while (out.length < Math.min(n, list.length)) {
      var k = Math.floor(Math.random() * list.length);
      if (used[k]) continue;
      used[k] = 1;
      out.push(list[k]);
    }
    return out;
  }
  function memeHref(slug) {
    var onViz = /visualizations(\.html)?$/.test(location.pathname);
    return (onViz ? '' : 'visualizations.html') + '#meme/' + encodeURIComponent(slug);
  }

  /* ── Random meme card ─────────────────────────────────────────────────── */
  var card, btn, pool = null, current = null;

  function buildButton() {
    var nav = document.querySelector('.topnav');
    if (!nav || nav.querySelector('.rm-btn')) return;
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rm-btn';
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'rm-card');
    btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/>' +
      '<circle cx="8" cy="8" r="1.4"/><circle cx="16" cy="8" r="1.4"/><circle cx="12" cy="12" r="1.4"/>' +
      '<circle cx="8" cy="16" r="1.4"/><circle cx="16" cy="16" r="1.4"/></svg><span>Random meme</span>';
    btn.addEventListener('click', function() { card && card.classList.contains('open') ? closeCard() : openCard(); });
    nav.appendChild(btn);

    card = document.createElement('div');
    card.className = 'rm-card';
    card.id = 'rm-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-label', 'Random meme');
    card.innerHTML =
      '<figure class="rm-figure"><img alt="" id="rm-img"/><figcaption class="rm-caption" id="rm-name"></figcaption></figure>' +
      '<div class="rm-meta" id="rm-meta"></div>' +
      '<div class="rm-actions"><button type="button" class="rm-again">Another one</button>' +
      '<a class="rm-open" id="rm-open" href="#">Open entry →</a></div>';
    document.body.appendChild(card);
    card.querySelector('.rm-again').addEventListener('click', showRandom);
    card.querySelector('#rm-open').addEventListener('click', closeCard);
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeCard(); });
    document.addEventListener('click', function(e) {
      if (!card.classList.contains('open')) return;
      if (card.contains(e.target) || btn.contains(e.target)) return;
      closeCard();
    });
  }

  function openCard() {
    card.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
    showRandom();
  }
  function closeCard() {
    if (!card) return;
    card.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  }
  function showRandom() {
    card.classList.add('loading');
    loadMemes().then(function(list) {
      if (!pool) pool = list.filter(function(m) { return m.v > 20000; });  // the recognisable ones
      if (!pool.length) pool = list;
      if (!pool.length) return;
      var m;
      do { m = pool[Math.floor(Math.random() * pool.length)]; } while (pool.length > 1 && m === current);
      current = m;
      var img = document.getElementById('rm-img');
      img.onload = function() { card.classList.remove('loading'); };
      img.onerror = function() { card.classList.remove('loading'); };
      img.src = imgUrl(m);
      img.alt = nameOf(m.s);
      document.getElementById('rm-name').textContent = nameOf(m.s);
      document.getElementById('rm-meta').innerHTML =
        [m.y, m.f, m.t, m.v ? Number(m.v).toLocaleString() + ' views' : null]
          .filter(Boolean).map(function(x) { return '<span>' + esc(x) + '</span>'; }).join('');
      document.getElementById('rm-open').href = memeHref(m.s);
    });
  }

  /* ── Caption banners ──────────────────────────────────────────────────── */
  function decorate(root) {
    var titles = (root || document).querySelectorAll ? (root || document).querySelectorAll(BANNER_SELECTOR) : [];
    Array.prototype.forEach.call(titles, function(h) {
      if (h.closest('.meme-banner')) return;
      var wrap = document.createElement('div');
      wrap.className = 'meme-banner';
      var strip = document.createElement('div');
      strip.className = 'meme-banner-strip';
      strip.setAttribute('aria-hidden', 'true');
      h.parentNode.insertBefore(wrap, h);
      wrap.appendChild(strip);
      wrap.appendChild(h);
      h.classList.add('meme-caption');
      loadMemes().then(function(list) {
        var pics = list.filter(function(m) { return !m.a && m.v > 5000; });
        pick(pics.length ? pics : list, 14).forEach(function(m) {
          var img = document.createElement('img');
          img.src = imgUrl(m);
          img.alt = '';
          img.loading = 'lazy';
          img.decoding = 'async';
          img.onerror = function() { img.remove(); };
          strip.appendChild(img);
        });
      });
    });
  }

  function init() {
    buildButton();
    decorate(document);
    // About / Disclaimer titles are rendered later by meme_viz.js
    if ('MutationObserver' in window) {
      var queued = false;
      new MutationObserver(function() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function() { queued = false; decorate(document); });
      }).observe(document.body, { childList: true, subtree: true });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
