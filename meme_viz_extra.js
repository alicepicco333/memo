/* ══════════════════════════════════════════════════════════════════════════
   INTERACTIVE EXPLORATIONS
   Loaded after meme_viz.js; reuses its globals (DATA, D0_DATA, VARIANTS_DATA,
   TRANSFORM_MAP, showTip/moveTip/hideTip, openPanel, openDetail, escHtml…).
   Each visualization is built lazily the first time its section nears the
   viewport, and rebuilt on resize.
   ══════════════════════════════════════════════════════════════════════════ */
(function() {
  'use strict';

  const EXTENT_ORDER = ['Minimal', 'Moderate', 'Substantial', 'Parody'];
  const EXTENT_COLOR = { Minimal: '#4caf50', Moderate: '#ff9800', Substantial: '#f44336', Parody: '#9c27b0' };
  const DIM_ORDER = ['CaptionChange', 'VisualSubstrate', 'MediumShift', 'StyleShift',
                     'CompositionShift', 'CrossoverMerge', 'LanguageShift', 'Localization'];
  const PLATFORM_COLOR = {
    TwitterX: '#52b2e6', YouTube: '#e06464', TikTok: '#3ec4c4', Reddit: '#e08c68',
    Instagram: '#d06eb4', Facebook: '#7090d4', Tumblr: '#6898bc', '4chan': '#5cb87a',
    iFunny: '#e0b050', Vine: '#2fb58f', Other: '#98afbf', Unattributed: '#c8ccd2'
  };
  /* Wikidata items as they appear in meme_ontology.ttl (wdp:P123 / wdp:P495) */
  const PLATFORM_QID = {
    TwitterX: 'Q918', TikTok: 'Q48938223', YouTube: 'Q866', Reddit: 'Q1136', Instagram: 'Q209330',
    Facebook: 'Q355', Tumblr: 'Q384060', '4chan': 'Q238330', iFunny: 'Q97573363', Twitch: 'Q4555537',
    Vine: 'Q3700238', Imgur: 'Q355022', DeviantArt: 'Q46523', Discord: 'Q22907849', '9gag': 'Q277421',
    FunnyJunk: 'Q63891999', Snapchat: 'Q333618', SomethingAwful: 'Q1048635', KnowYourMeme: 'Q2071334'
  };
  const REGION_QID = {
    UnitedStates: 'wd:Q30', Japan: 'wd:Q17', UnitedKingdom: 'wd:Q145', Worldwide: 'memo:Worldwide',
    China: 'wd:Q148', Brazil: 'wd:Q155', India: 'wd:Q668', France: 'wd:Q142',
    SouthKorea: 'wd:Q884', Russia: 'wd:Q159', Mexico: 'wd:Q96'
  };

  const built = {};
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DUR = reduceMotion ? 0 : 1;

  /* ── Shared helpers ────────────────────────────────────────────────────── */
  function memes() { return (DATA && DATA.memes) ? DATA.memes : {}; }
  function memeImg(m) { return m ? (memeRemoteSrc(m) || memeLocalSrc(m)) : ''; }
  function yearOf(m) {
    const y = parseInt(m && m.year, 10);
    return Number.isFinite(y) ? y : null;
  }
  function wrapSize(wrap, fallbackH) {
    const r = wrap.getBoundingClientRect();
    return { W: Math.max(280, r.width || 900), H: Math.max(260, r.height || fallbackH || 560) };
  }
  function makeCanvas(wrap, W, H) {
    const dpr = window.devicePixelRatio || 1;
    const c = document.createElement('canvas');
    c.width = Math.round(W * dpr);
    c.height = Math.round(H * dpr);
    c.style.width = W + 'px';
    c.style.height = H + 'px';
    const ctx = c.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    wrap.appendChild(c);
    return { canvas: c, ctx };
  }
  function tipWithImage(m, extra) {
    const src = escHtml(memeImg(m));
    return (src ? `<img class="tip-thumb" src="${src}" alt="">` : '') +
      `<b>${escHtml(slugToName(m.slug))}</b>` + (extra ? `<br>${extra}` : '');
  }
  function sparqlHref(query) { return 'sparql.html?q=' + encodeURIComponent(query); }
  const SPARQL_PREFIXES =
    'PREFIX memo: <https://purl.org/memo#>\n' +
    'PREFIX wdp:  <http://www.wikidata.org/prop/direct/>\n' +
    'PREFIX wd:   <http://www.wikidata.org/entity/>\n' +
    'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n\n';

  function lazyBuild(id, fn) {
    const section = document.getElementById(id);
    if (!section) return;
    const obs = new IntersectionObserver(entries => {
      if (!entries.some(e => e.isIntersecting)) return;
      obs.disconnect();
      built[id] = fn;
      try { fn(); } catch (err) { console.error('[extra] ' + id, err); }
    }, { rootMargin: '300px 0px' });
    obs.observe(section);
  }

  let started = false;
  window.buildExtraGraphs = function() {
    if (started || !DATA) return;
    started = true;
    lazyBuild('sec-family', buildFamilyTree);
    lazyBuild('sec-spectrum', buildSpectrum);
    lazyBuild('sec-walk', buildGraphWalk);
    lazyBuild('sec-story', buildPlatformStory);
    lazyBuild('sec-confidence', buildConfidence);
    lazyBuild('sec-flow', buildFlow);
  };

  // A tooltip left open by a hovered chart shouldn't follow the page as it scrolls
  window.addEventListener('scroll', () => { if (typeof hideTip === 'function' && tip) hideTip(); }, { passive: true });

  let resizeT;
  let lastW = window.innerWidth;
  window.addEventListener('resize', () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(() => {
      if (Math.abs(window.innerWidth - lastW) < 40) return; // ignore mobile URL-bar jitter
      lastW = window.innerWidth;
      Object.keys(built).forEach(id => {
        if (id === 'sec-walk') return; // keeps its own state; svg scales via viewBox
        try { built[id](); } catch (err) { console.error(err); }
      });
    }, 300);
  });

  function controlBtn(label, onClick, extraClass) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'viz-btn' + (extraClass ? ' ' + extraClass : '');
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }
  function setActive(container, btn) {
    container.querySelectorAll('.viz-btn[data-group]').forEach(b => {
      if (b.dataset.group === btn.dataset.group) b.classList.toggle('active', b === btn);
    });
  }

  /* ═════════════════════════════════════════════════════════════════════════
     1. VARIANT FAMILY TREE — radial: rings = extent, sectors = dimension
     ═════════════════════════════════════════════════════════════════════════ */
  let familyCurrent = null;

  function familyGroups() {
    const varById = {};
    (VARIANTS_DATA || []).forEach(v => { varById[String(v.photo_id)] = v; });
    const groups = {};
    Object.values(TRANSFORM_MAP).forEach(a => {
      const slug = (a.memeConceptIRI || '').split('#')[1] || '';
      const g = groups[a.memeName] || (groups[a.memeName] = { name: a.memeName, slug, variants: [], seen: {} });
      const key = String(a.captionText || '').toLowerCase().replace(/\s+/g, ' ').trim() || a.imageURL || a.photoId;
      if (g.seen[key]) return;
      g.seen[key] = true;
      const v = varById[String(a.photoId)];
      g.variants.push({
        id: String(a.photoId),
        title: a.variantTitle || (v && v.title) || 'Variant',
        extent: EXTENT_ORDER.includes(a.transformationExtent) ? a.transformationExtent : 'Moderate',
        dims: Array.isArray(a.transformationDimension) ? a.transformationDimension : [a.transformationDimension].filter(Boolean),
        type: a.variantImageType || '',
        img: a.imageURL || (v && v.image_url) || ''
      });
    });
    return Object.values(groups).sort((a, b) => a.name.localeCompare(b.name));
  }

  function buildFamilyTree() {
    const wrap = document.getElementById('graph-family');
    const bar = document.getElementById('family-controls');
    if (!wrap || !bar) return;
    const groups = familyGroups();
    if (!groups.length) {
      wrap.innerHTML = '<p class="viz-empty">No annotated variants available.</p>';
      return;
    }
    if (!familyCurrent || !groups.find(g => g.name === familyCurrent)) familyCurrent = groups[0].name;

    bar.innerHTML = '';
    const label = document.createElement('span');
    label.className = 'viz-controls-label';
    label.textContent = 'Meme';
    bar.appendChild(label);
    groups.forEach(g => {
      const b = controlBtn(g.name, () => {
        if (familyCurrent === g.name) return;
        familyCurrent = g.name;
        setActive(bar, b);
        drawFamily(wrap, groups.find(x => x.name === familyCurrent), true);
      });
      b.dataset.group = 'meme';
      if (g.name === familyCurrent) b.classList.add('active');
      bar.appendChild(b);
    });
    const legend = document.createElement('span');
    legend.className = 'viz-legend';
    legend.innerHTML = EXTENT_ORDER.map(e =>
      `<span><i style="background:${EXTENT_COLOR[e]}"></i>${e}</span>`).join('') +
      '<span class="viz-legend-note">ring = extent · sector = main dimension</span>';
    bar.appendChild(legend);

    drawFamily(wrap, groups.find(g => g.name === familyCurrent), false);
  }

  function drawFamily(wrap, group, animateOut) {
    const render = () => renderFamily(wrap, group);
    const old = wrap.querySelector('svg');
    if (animateOut && old && DUR) {
      d3.select(old).selectAll('.fam-node, .fam-link, .fam-sector')
        .transition().duration(260).style('opacity', 0)
        .end().then(render, render);
    } else {
      render();
    }
  }

  function renderFamily(wrap, group) {
    const { W, H } = wrapSize(wrap, 620);
    const S = Math.min(W, H);
    const R = S / 2 - (isMobile() ? 34 : 64);
    const ringR = { Minimal: R * 0.44, Moderate: R * 0.63, Substantial: R * 0.82, Parody: R };
    const coreR = R * 0.24;
    const thumbR = Math.max(12, Math.min(26, R * 0.085));

    // Sectors: primary dimension of each variant; angular span ∝ count
    const bySector = {};
    group.variants.forEach(v => {
      const dim = DIM_ORDER.find(d => v.dims.includes(d)) || v.dims[0] || 'Other';
      (bySector[dim] || (bySector[dim] = [])).push(v);
    });
    const sectors = Object.keys(bySector)
      .sort((a, b) => DIM_ORDER.indexOf(a) - DIM_ORDER.indexOf(b))
      .map(dim => ({ dim, items: bySector[dim].sort((a, b) => EXTENT_ORDER.indexOf(a.extent) - EXTENT_ORDER.indexOf(b.extent)) }));
    const total = group.variants.length;
    let a0 = 0;
    sectors.forEach(s => {
      s.start = a0;
      s.span = (Math.PI * 2) * (s.items.length / total);
      s.mid = s.start + s.span / 2;
      s.items.forEach((v, k) => {
        v.angle = s.start + s.span * (k + 0.5) / s.items.length;
        v.r = ringR[v.extent];
        v.sector = s;
      });
      a0 += s.span;
    });
    const polar = (ang, r) => [r * Math.sin(ang), -r * Math.cos(ang)];

    wrap.innerHTML = '';
    const svg = d3.select(wrap).append('svg')
      .attr('viewBox', `${-W / 2} ${-H / 2} ${W} ${H}`)
      .attr('class', 'fam-svg')
      .attr('role', 'img')
      .attr('aria-label', `Variant family tree for ${group.name}`);
    const defs = svg.append('defs');
    defs.append('clipPath').attr('id', 'fam-clip').attr('clipPathUnits', 'objectBoundingBox')
      .append('circle').attr('cx', .5).attr('cy', .5).attr('r', .5);

    // Rings
    const ringG = svg.append('g').attr('class', 'fam-rings');
    EXTENT_ORDER.forEach(e => {
      ringG.append('circle').attr('r', ringR[e]).attr('fill', 'none')
        .attr('stroke', EXTENT_COLOR[e]).attr('stroke-opacity', .35).attr('stroke-dasharray', '3 5');
      ringG.append('text').attr('y', -ringR[e] - 5).attr('text-anchor', 'middle')
        .attr('class', 'fam-ring-label').attr('fill', EXTENT_COLOR[e]).text(e.toUpperCase());
    });

    // Sector dividers + labels
    const sectG = svg.append('g');
    sectors.forEach(s => {
      const [x1, y1] = polar(s.start, coreR + 6);
      const [x2, y2] = polar(s.start, R + 14);
      sectG.append('line').attr('class', 'fam-sector').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2);
      const [lx, ly] = polar(s.mid, R + (isMobile() ? 20 : 34));
      const deg = s.mid * 180 / Math.PI;
      const flip = deg > 90 && deg < 270;
      sectG.append('text').attr('class', 'fam-sector fam-sector-label')
        .attr('transform', `translate(${lx},${ly}) rotate(${flip ? deg - 180 : deg})`)
        .attr('text-anchor', 'middle').attr('dy', '.35em')
        .text(s.dim + ' · ' + s.items.length);
    });

    // Branches: core → sector hub → variant
    const link = d3.linkRadial().angle(d => d[0]).radius(d => d[1]);
    const linkG = svg.append('g');
    const links = linkG.selectAll('path').data(group.variants).join('path')
      .attr('class', 'fam-link')
      .attr('d', v => {
        const hub = link({ source: [v.sector.mid, coreR], target: [v.sector.mid, coreR + (R - coreR) * 0.22] });
        const twig = link({ source: [v.sector.mid, coreR + (R - coreR) * 0.22], target: [v.angle, v.r - thumbR] });
        return hub + twig.replace(/^M/, 'L');
      })
      .attr('stroke', v => EXTENT_COLOR[v.extent]);
    links.each(function() {
      const len = this.getTotalLength();
      d3.select(this).attr('stroke-dasharray', len).attr('stroke-dashoffset', DUR ? len : 0);
    });
    links.transition().delay(v => DUR * (120 + EXTENT_ORDER.indexOf(v.extent) * 160))
      .duration(DUR * 650).ease(d3.easeCubicOut).attr('stroke-dashoffset', 0);

    // Core: original (bottom) + hovered variant (top, cross-fades)
    const m = memes()[group.slug];
    const core = svg.append('g').attr('class', 'fam-core');
    core.append('circle').attr('r', coreR + 3).attr('fill', '#111');
    const coreImg = core.append('image').attr('x', -coreR).attr('y', -coreR)
      .attr('width', coreR * 2).attr('height', coreR * 2)
      .attr('clip-path', 'url(#fam-clip)').attr('preserveAspectRatio', 'xMidYMid slice')
      .attr('href', memeImg(m));
    const hoverImg = core.append('image').attr('x', -coreR).attr('y', -coreR)
      .attr('width', coreR * 2).attr('height', coreR * 2)
      .attr('clip-path', 'url(#fam-clip)').attr('preserveAspectRatio', 'xMidYMid slice')
      .style('opacity', 0);
    const caption = svg.append('text').attr('class', 'fam-caption').attr('y', coreR + 20).attr('text-anchor', 'middle')
      .text('ORIGINAL · ' + group.name);
    core.style('cursor', 'pointer').on('click', () => {
      if (group.slug && memes()[group.slug]) openDetail(group.slug);
    });
    if (!m) coreImg.remove();

    // Variant nodes
    const nodes = svg.append('g').selectAll('g').data(group.variants).join('g')
      .attr('class', 'fam-node')
      .attr('transform', v => { const [x, y] = polar(v.angle, v.r); return `translate(${x},${y})`; })
      .attr('tabindex', 0)
      .attr('role', 'link')
      .attr('aria-label', v => `${v.title}: ${v.extent}, ${v.dims.join(', ')}`)
      .style('opacity', 0);
    nodes.append('circle').attr('r', thumbR + 2.5).attr('fill', v => EXTENT_COLOR[v.extent]);
    nodes.append('image').attr('x', -thumbR).attr('y', -thumbR).attr('width', thumbR * 2).attr('height', thumbR * 2)
      .attr('clip-path', 'url(#fam-clip)').attr('preserveAspectRatio', 'xMidYMid slice')
      .attr('href', v => v.img);
    nodes.transition().delay(v => DUR * (500 + EXTENT_ORDER.indexOf(v.extent) * 160))
      .duration(DUR * 380).style('opacity', 1);

    function focus(v, on) {
      nodes.classed('dim', on ? (d => d !== v) : false);
      links.classed('hot', on ? (d => d === v) : false).classed('dim', on ? (d => d !== v) : false);
      if (on) {
        hoverImg.attr('href', v.img).interrupt().transition().duration(DUR * 220).style('opacity', 1);
        caption.text(v.extent.toUpperCase() + ' · ' + v.dims.join(' + '));
      } else {
        hoverImg.interrupt().transition().duration(DUR * 220).style('opacity', 0);
        caption.text('ORIGINAL · ' + group.name);
      }
    }
    nodes
      .on('mouseenter focus', (e, v) => {
        focus(v, true);
        showTip(`<b>${escHtml(v.title)}</b><br>${escHtml(v.extent)} · ${escHtml(v.dims.join(', '))}` +
          (v.type ? `<br><small>variant image type: ${escHtml(v.type)}</small>` : '') +
          '<br><small>click to open</small>', e.clientX != null ? e : { clientX: innerWidth / 2, clientY: innerHeight / 2 });
      })
      .on('mousemove', moveTip)
      .on('mouseleave blur', (e, v) => { focus(v, false); hideTip(); })
      .on('click', (e, v) => { hideTip(); location.hash = '#variant/' + encodeURIComponent(v.id); })
      .on('keydown', (e, v) => { if (e.key === 'Enter') location.hash = '#variant/' + encodeURIComponent(v.id); });
  }

  /* ═════════════════════════════════════════════════════════════════════════
     2. COLOUR SPECTRUM — every meme as its average colour (Manovich-style)
     ═════════════════════════════════════════════════════════════════════════ */
  let COLOR_DATA = null;
  let colorPromise = null;
  const spectrum = { mode: 'year', upTo: null, items: null, playing: null };

  function loadColors() {
    if (!colorPromise) {
      colorPromise = fetch('color_data.json').then(r => r.ok ? r.json() : {}).catch(() => ({}))
        .then(d => (COLOR_DATA = d));
    }
    return colorPromise;
  }

  function buildSpectrum() {
    const wrap = document.getElementById('graph-spectrum');
    const bar = document.getElementById('spectrum-controls');
    if (!wrap || !bar) return;
    if (!COLOR_DATA) {
      wrap.innerHTML = '<p class="viz-empty">Loading colour data…</p>';
      loadColors().then(buildSpectrum);
      return;
    }
    if (!spectrum.items) {
      spectrum.items = Object.keys(memes()).filter(s => COLOR_DATA[s]).map(slug => {
        const m = memes()[slug];
        const c = COLOR_DATA[slug];
        return { slug, m, h: +c.h || 0, s: +c.s || 0, l: +c.l || 0, year: yearOf(m),
                 fill: `hsl(${c.h},${c.s}%,${c.l}%)`, x: 0, y: 0, size: 0 };
      });
    }
    const items = spectrum.items;
    const years = items.map(d => d.year).filter(y => y && y >= 1990);
    const yMin = Math.max(1995, d3.min(years) || 1995);
    const yMax = d3.max(years) || 2026;
    if (spectrum.upTo == null) spectrum.upTo = yMax;

    // ── controls
    if (!bar.dataset.ready) {
      bar.dataset.ready = '1';
      const lab = document.createElement('span');
      lab.className = 'viz-controls-label';
      lab.textContent = 'Arrange by';
      bar.appendChild(lab);
      [['year', 'Year grid'], ['time', 'Hue over time'], ['wheel', 'Colour wheel'], ['plane', 'Hue × lightness']]
        .forEach(([mode, text]) => {
          const b = controlBtn(text, () => { spectrum.mode = mode; setActive(bar, b); layoutSpectrum(true); });
          b.dataset.group = 'mode';
          if (mode === spectrum.mode) b.classList.add('active');
          bar.appendChild(b);
        });
      const slider = document.createElement('label');
      slider.className = 'viz-slider';
      slider.innerHTML = `<span>Up to <b id="spectrum-year">${spectrum.upTo}</b></span>` +
        `<input type="range" id="spectrum-range" min="${yMin}" max="${yMax}" step="1" value="${spectrum.upTo}" aria-label="Show memes up to year">`;
      bar.appendChild(slider);
      const play = controlBtn('▶ Play', () => togglePlay(play, yMin, yMax), 'viz-btn-play');
      bar.appendChild(play);
      slider.querySelector('input').addEventListener('input', e => {
        spectrum.upTo = +e.target.value;
        document.getElementById('spectrum-year').textContent = spectrum.upTo;
        drawSpectrum();
      });
      const note = document.createElement('span');
      note.className = 'viz-note';
      note.id = 'spectrum-note';
      bar.appendChild(note);
    }

    // Data-driven caption: average saturation early vs recent
    const avgSat = (a, b) => d3.mean(items.filter(d => d.year >= a && d.year <= b), d => d.s);
    const early = avgSat(1995, 2011), late = avgSat(2018, 2026);
    const noteEl = document.getElementById('spectrum-note');
    if (noteEl && early != null && late != null) {
      noteEl.textContent = `Avg. saturation ${Math.round(early)}% (≤2011) → ${Math.round(late)}% (2018+)`;
    }

    wrap.innerHTML = '';
    const { W, H } = wrapSize(wrap, 560);
    const { canvas, ctx } = makeCanvas(wrap, W, H);
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Every meme drawn as its average colour');
    spectrum.ctx = ctx; spectrum.W = W; spectrum.H = H; spectrum.yMin = yMin; spectrum.yMax = yMax;
    spectrum.labels = [];
    layoutSpectrum(false);

    canvas.addEventListener('mousemove', e => {
      if (!spectrum.tree) return;
      const r = canvas.getBoundingClientRect();
      const d = spectrum.tree.find(e.clientX - r.left, e.clientY - r.top, 14);
      canvas.style.cursor = d ? 'pointer' : 'default';
      if (d) {
        showTip(tipWithImage(d.m, `${d.year || 'year unknown'} · hsl(${Math.round(d.h)}°, ${Math.round(d.s)}%, ${Math.round(d.l)}%)`), e);
      } else hideTip();
    });
    canvas.addEventListener('mouseleave', hideTip);
    canvas.addEventListener('click', e => {
      if (!spectrum.tree) return;
      const r = canvas.getBoundingClientRect();
      const d = spectrum.tree.find(e.clientX - r.left, e.clientY - r.top, 14);
      if (d) { hideTip(); openDetail(d.slug); }
    });
  }

  function togglePlay(btn, yMin, yMax) {
    if (spectrum.playing) {
      clearInterval(spectrum.playing);
      spectrum.playing = null;
      btn.textContent = '▶ Play';
      return;
    }
    const input = document.getElementById('spectrum-range');
    let y = Math.max(yMin, 2004);
    btn.textContent = '❚❚ Pause';
    spectrum.playing = setInterval(() => {
      spectrum.upTo = y;
      input.value = y;
      document.getElementById('spectrum-year').textContent = y;
      drawSpectrum();
      if (++y > yMax) { clearInterval(spectrum.playing); spectrum.playing = null; btn.textContent = '▶ Play'; }
    }, 380);
  }

  function layoutSpectrum(animate) {
    const { W, H, items } = spectrum;
    if (!spectrum.ctx) return;
    const pad = { l: 44, r: 16, t: 16, b: 30 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const known = y => y && y >= 1990;
    items.forEach(d => { d.px = d.x; d.py = d.y; d.psize = d.size; });
    spectrum.labels = [];

    if (spectrum.mode === 'year') {
      const sorted = items.slice().sort((a, b) =>
        (known(a.year) ? a.year : 9999) - (known(b.year) ? b.year : 9999) || a.h - b.h);
      const cell = Math.max(3, Math.floor(Math.sqrt((iw * ih) / sorted.length)));
      const cols = Math.max(1, Math.floor(iw / cell));
      let lastYear = null;
      sorted.forEach((d, i) => {
        d.x = pad.l + (i % cols) * cell + cell / 2;
        d.y = pad.t + Math.floor(i / cols) * cell + cell / 2;
        d.size = cell - 1;
        const yLabel = known(d.year) ? d.year : 'n/a';
        if (yLabel !== lastYear && (i % cols) < cols) {
          if (!spectrum.labels.length || d.y - spectrum.labels[spectrum.labels.length - 1].y > 12) {
            spectrum.labels.push({ x: pad.l - 6, y: d.y, text: String(yLabel), align: 'right' });
          }
          lastYear = yLabel;
        }
      });
    } else if (spectrum.mode === 'time') {
      const x = d3.scaleLinear().domain([spectrum.yMin - 0.5, spectrum.yMax + 0.5]).range([pad.l, pad.l + iw]);
      const y = d3.scaleLinear().domain([0, 360]).range([pad.t, pad.t + ih]);
      const bw = iw / (spectrum.yMax - spectrum.yMin + 1);
      items.forEach(d => {
        const yr = known(d.year) ? Math.max(spectrum.yMin, d.year) : spectrum.yMax;
        d.x = x(yr) + (hash(d.slug) - .5) * bw * .8;
        d.y = y(d.h);
        d.size = known(d.year) ? 3 : 0; // undated memes have no place on a time axis
      });
      x.ticks(Math.min(12, Math.floor(iw / 70))).forEach(t => spectrum.labels.push({ x: x(t), y: H - 10, text: String(t), align: 'center' }));
      [0, 60, 120, 180, 240, 300].forEach(h => spectrum.labels.push({ x: pad.l - 6, y: y(h), text: h + '°', align: 'right' }));
    } else if (spectrum.mode === 'wheel') {
      const cx = pad.l + iw / 2, cy = pad.t + ih / 2, R = Math.min(iw, ih) / 2;
      items.forEach(d => {
        const a = (d.h - 90) * Math.PI / 180;
        const r = R * Math.sqrt(d.s / 100);
        d.x = cx + r * Math.cos(a) + (hash(d.slug) - .5) * 3;
        d.y = cy + r * Math.sin(a) + (hash(d.slug + 'y') - .5) * 3;
        d.size = 3.2;
      });
      spectrum.labels.push({ x: cx, y: cy + 4, text: 'grey', align: 'center' });
      spectrum.labels.push({ x: cx, y: pad.t + 10, text: 'saturated →', align: 'center', rim: true });
    } else {
      const x = d3.scaleLinear().domain([0, 360]).range([pad.l, pad.l + iw]);
      const y = d3.scaleLinear().domain([100, 0]).range([pad.t, pad.t + ih]);
      items.forEach(d => {
        d.x = x(d.h) + (hash(d.slug) - .5) * 2;
        d.y = y(d.l) + (hash(d.slug + 'l') - .5) * 2;
        d.size = 3;
      });
      [0, 60, 120, 180, 240, 300, 360].forEach(h => spectrum.labels.push({ x: x(h), y: H - 10, text: h + '°', align: 'center' }));
      [0, 50, 100].forEach(l => spectrum.labels.push({ x: pad.l - 6, y: y(l), text: 'L' + l, align: 'right' }));
    }

    spectrum.tree = null;
    if (spectrum.timer) spectrum.timer.stop();
    if (!animate || !DUR || !items[0].psize) {
      items.forEach(d => { d.cx = d.x; d.cy = d.y; d.csize = d.size; });
      drawSpectrum();
      spectrum.tree = d3.quadtree(items.filter(d => d.size > 0), d => d.cx, d => d.cy);
      return;
    }
    const n = items.length;
    const order = new Map(items.slice().sort((a, b) => a.h - b.h).map((d, i) => [d, i / n]));
    const total = 1100;
    spectrum.timer = d3.timer(elapsed => {
      items.forEach(d => {
        const t = d3.easeCubicInOut(Math.max(0, Math.min(1, (elapsed - order.get(d) * 350) / (total - 350))));
        d.cx = d.px + (d.x - d.px) * t;
        d.cy = d.py + (d.y - d.py) * t;
        d.csize = d.psize + (d.size - d.psize) * t;
      });
      drawSpectrum();
      if (elapsed > total) {
        spectrum.timer.stop();
        spectrum.tree = d3.quadtree(items.filter(d => d.size > 0), d => d.cx, d => d.cy);
      }
    });
  }

  function drawSpectrum() {
    const { ctx, W, H, items, upTo } = spectrum;
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0d0d0d';
    ctx.fillRect(0, 0, W, H);
    let shown = 0;
    items.forEach(d => {
      const visible = !d.year || d.year < 1990 || d.year <= upTo;
      if (visible) shown++;
      ctx.globalAlpha = visible ? 1 : 0.07;
      ctx.fillStyle = d.fill;
      const s = d.csize;
      if (s < 0.3) return;
      ctx.fillRect(d.cx - s / 2, d.cy - s / 2, s, s);
    });
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(255,255,255,.6)';
    ctx.font = '10px system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    spectrum.labels.forEach(l => {
      ctx.textAlign = l.align === 'right' ? 'right' : 'center';
      ctx.fillText(l.text, l.x, l.y);
    });
    ctx.textAlign = 'right';
    ctx.fillStyle = 'rgba(255,255,255,.75)';
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillText(`${shown.toLocaleString()} memes`, W - 12, 12);
  }

  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return ((h >>> 0) % 10000) / 10000;
  }

  /* ═════════════════════════════════════════════════════════════════════════
     3. KNOWLEDGE-GRAPH WALK — expand a meme into its properties and back
     ═════════════════════════════════════════════════════════════════════════ */
  const PROP_FIELDS = {
    hasFormat:          { label: 'format',       color: '#e0873a' },
    hasOriginPlatform:  { label: 'platform',     color: '#3a8fd8' },
    hasImageType:       { label: 'image type',   color: '#8e5cc9' },
    hasTimePeriod:      { label: 'period',       color: '#2a9d6f' },
    hasSubjectMatter:   { label: 'subject',      color: '#c9505f' },
    hasRegion:          { label: 'region',       color: '#7a7a2e' }
  };
  const MAX_NODES = 140;
  let walk = null;

  function propValues(m, field) {
    const v = m[field];
    const arr = Array.isArray(v) ? v : [v];
    return arr.filter(x => x && x !== 'Unknown');
  }

  function propIndex() {
    if (walk && walk.index) return walk.index;
    const idx = {};
    Object.keys(PROP_FIELDS).forEach(f => { idx[f] = {}; });
    Object.values(memes()).forEach(m => {
      Object.keys(PROP_FIELDS).forEach(f => {
        propValues(m, f).forEach(v => { (idx[f][v] || (idx[f][v] = [])).push(m.slug); });
      });
    });
    Object.values(idx).forEach(byVal => Object.values(byVal).forEach(list =>
      list.sort((a, b) => (memes()[b].popularityViews || 0) - (memes()[a].popularityViews || 0))));
    return idx;
  }

  function propSparql(field, value) {
    const local = String(value).replace(/\s+/g, '_');
    let triple = null;
    if (field === 'hasFormat') triple = `wdp:P2283 memo:${local}`;
    else if (field === 'hasImageType') triple = `memo:hasImageType memo:${local}`;
    else if (field === 'hasTimePeriod') triple = `wdp:P2408 memo:${local}`;
    else if (field === 'hasSubjectMatter') triple = `memo:hasSubjectMatter memo:${local}`;
    else if (field === 'hasOriginPlatform' && PLATFORM_QID[value]) triple = `wdp:P123 wd:${PLATFORM_QID[value]}`;
    else if (field === 'hasRegion' && REGION_QID[value]) triple = `wdp:P495 ${REGION_QID[value]}`;
    if (!triple) return null;
    return SPARQL_PREFIXES +
      `SELECT ?meme ?label ?views WHERE {\n  ?meme a memo:MemeConcept ;\n        ${triple} ;\n        rdfs:label ?label .\n` +
      `  OPTIONAL { ?meme memo:views ?views }\n}\nORDER BY DESC(?views)\nLIMIT 50`;
  }
  function memeSparql(slug) {
    return SPARQL_PREFIXES + `SELECT ?property ?value WHERE {\n  <https://purl.org/memo#${slug}> ?property ?value .\n}`;
  }

  function buildGraphWalk() {
    const wrap = document.getElementById('graph-walk');
    const bar = document.getElementById('walk-controls');
    if (!wrap || !bar) return;
    walk = { index: propIndex(), nodes: [], links: [], byId: new Map(), trail: [] };

    bar.innerHTML = '';
    const form = document.createElement('form');
    form.className = 'viz-search';
    form.innerHTML = '<input type="search" placeholder="Start from a meme…" aria-label="Start the walk from a meme" list="walk-suggest">' +
      '<datalist id="walk-suggest"></datalist>';
    const input = form.querySelector('input');
    const list = form.querySelector('datalist');
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      if (q.length < 2) { list.innerHTML = ''; return; }
      list.innerHTML = Object.keys(memes()).filter(s => s.includes(q.replace(/\s+/g, '-'))).slice(0, 12)
        .map(s => `<option value="${escHtml(slugToName(s))}">`).join('');
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      const q = input.value.trim().toLowerCase().replace(/\s+/g, '-');
      const slug = memes()[q] ? q : Object.keys(memes()).find(s => s.includes(q));
      if (slug) startWalk(slug);
    });
    bar.appendChild(form);
    bar.appendChild(controlBtn('Random start', () => startWalk(randomSeed())));
    const trail = document.createElement('div');
    trail.className = 'walk-trail';
    trail.id = 'walk-trail';
    bar.appendChild(trail);

    const { W, H } = wrapSize(wrap, 600);
    wrap.innerHTML = '';
    const svg = d3.select(wrap).append('svg').attr('viewBox', `${-W / 2} ${-H / 2} ${W} ${H}`)
      .attr('class', 'walk-svg').attr('role', 'img').attr('aria-label', 'Knowledge graph walk');
    svg.append('defs').append('clipPath').attr('id', 'walk-clip').attr('clipPathUnits', 'objectBoundingBox')
      .append('circle').attr('cx', .5).attr('cy', .5).attr('r', .5);
    const zoomG = svg.append('g');
    // Plain wheel keeps scrolling the page; Ctrl/⌘ + wheel zooms
    svg.call(d3.zoom().scaleExtent([0.3, 3])
      .filter(e => e.type === 'wheel' ? (e.ctrlKey || e.metaKey) : !e.button)
      .on('zoom', e => zoomG.attr('transform', e.transform)));
    walk.svg = svg;
    walk.linkG = zoomG.append('g').attr('class', 'walk-links');
    walk.nodeG = zoomG.append('g');

    const card = document.createElement('div');
    card.className = 'walk-card';
    card.id = 'walk-card';
    wrap.appendChild(card);
    const hint = document.createElement('div');
    hint.className = 'walk-hint';
    hint.textContent = 'Click a meme to reveal its properties · click a property to pull in more memes that share it · drag to move · Ctrl/⌘ + scroll to zoom';
    wrap.appendChild(hint);

    walk.sim = d3.forceSimulation(walk.nodes)
      .force('link', d3.forceLink(walk.links).id(d => d.id).distance(l => l.target.type === 'prop' || l.source.type === 'prop' ? 78 : 60).strength(.7))
      .force('charge', d3.forceManyBody().strength(-280))
      .force('collide', d3.forceCollide(d => d.type === 'meme' ? 30 : 26))
      .force('x', d3.forceX(0).strength(.04))
      .force('y', d3.forceY(0).strength(.06))
      .on('tick', walkTick);

    startWalk(randomSeed());
  }

  function randomSeed() {
    const top = Object.values(memes()).filter(m => m.hasOriginPlatform && (m.hasFormat || []).length)
      .sort((a, b) => (b.popularityViews || 0) - (a.popularityViews || 0)).slice(0, 250);
    return top[Math.floor(Math.random() * top.length)].slug;
  }

  function startWalk(slug) {
    walk.nodes.length = 0;
    walk.links.length = 0;
    walk.byId.clear();
    walk.trail = [];
    const n = addMemeNode(slug, 0, 0);
    expandMeme(n);
  }

  function addMemeNode(slug, x, y) {
    const id = 'm:' + slug;
    if (walk.byId.has(id)) return walk.byId.get(id);
    const n = { id, type: 'meme', slug, m: memes()[slug], x: x + (Math.random() - .5) * 20, y: y + (Math.random() - .5) * 20 };
    walk.nodes.push(n);
    walk.byId.set(id, n);
    return n;
  }
  function addPropNode(field, value, x, y) {
    const id = 'p:' + field + ':' + value;
    if (walk.byId.has(id)) return walk.byId.get(id);
    const n = { id, type: 'prop', field, value, offset: 0, x: x + (Math.random() - .5) * 20, y: y + (Math.random() - .5) * 20 };
    walk.nodes.push(n);
    walk.byId.set(id, n);
    return n;
  }
  function addLink(a, b) {
    const key = [a.id, b.id].sort().join('|');
    if (walk.links.some(l => l.key === key)) return;
    walk.links.push({ key, source: a, target: b });
  }

  function expandMeme(n) {
    n.expanded = true;
    Object.keys(PROP_FIELDS).forEach(f => propValues(n.m, f).forEach(v => {
      if (walk.nodes.length >= MAX_NODES) return;
      addLink(n, addPropNode(f, v, n.x, n.y));
    }));
    pushTrail(n);
    selectNode(n);
    walkRender();
  }

  function expandProp(n) {
    const pool = (walk.index[n.field][n.value] || []).filter(s => !walk.byId.has('m:' + s));
    const take = pool.slice(0, 6);
    take.forEach(s => {
      if (walk.nodes.length >= MAX_NODES) return;
      addLink(n, addMemeNode(s, n.x, n.y));
    });
    n.expanded = true;
    pushTrail(n);
    selectNode(n);
    walkRender();
  }

  function pushTrail(n) {
    walk.trail.push(n);
    const el = document.getElementById('walk-trail');
    if (!el) return;
    el.innerHTML = walk.trail.slice(-6).map((t, i, arr) =>
      `<span class="walk-step walk-step-${t.type}"${t.type === 'prop' ? ` style="--c:${PROP_FIELDS[t.field].color}"` : ''}>` +
      escHtml(t.type === 'meme' ? slugToName(t.slug) : t.value) + '</span>' + (i < arr.length - 1 ? '<span class="walk-arrow">→</span>' : '')).join('');
  }

  function selectNode(n) {
    walk.selected = n;
    const card = document.getElementById('walk-card');
    if (!card) return;
    if (n.type === 'meme') {
      const m = n.m;
      card.innerHTML =
        `<img src="${escHtml(memeImg(m))}" alt="">` +
        `<div class="walk-card-body"><b>${escHtml(slugToName(n.slug))}</b>` +
        `<small>${(m.popularityViews || 0).toLocaleString()} views · ${escHtml(m.year || 'n/a')}</small>` +
        `<div class="walk-card-actions"><a href="#meme/${encodeURIComponent(n.slug)}">Open meme</a>` +
        `<a href="${sparqlHref(memeSparql(n.slug))}" target="_blank" rel="noopener">SPARQL ↗</a></div></div>`;
    } else {
      const total = (walk.index[n.field][n.value] || []).length;
      const q = propSparql(n.field, n.value);
      card.innerHTML =
        `<div class="walk-card-body"><small>${escHtml(PROP_FIELDS[n.field].label)}</small><b>${escHtml(n.value)}</b>` +
        `<small>${total.toLocaleString()} memes share this</small>` +
        `<div class="walk-card-actions"><button type="button" id="walk-more">Pull in 6 more</button>` +
        (q ? `<a href="${sparqlHref(q)}" target="_blank" rel="noopener">SPARQL ↗</a>` : '') + '</div></div>';
      card.querySelector('#walk-more').addEventListener('click', () => expandProp(n));
    }
    card.classList.add('show');
    walk.nodeG && walk.nodeG.selectAll('.walk-node').classed('selected', d => d === n);
  }

  function walkRender() {
    const drag = d3.drag()
      .on('start', (e, d) => { if (!e.active) walk.sim.alphaTarget(.2).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) walk.sim.alphaTarget(0); d.fx = null; d.fy = null; });

    walk.linkG.selectAll('line').data(walk.links, l => l.key).join(
      enter => enter.append('line').attr('stroke-opacity', 0).call(s => s.transition().duration(DUR * 400).attr('stroke-opacity', .5))
    );

    walk.nodeG.selectAll('.walk-node').data(walk.nodes, d => d.id).join(enter => {
      const g = enter.append('g').attr('class', d => 'walk-node walk-' + d.type)
        .attr('tabindex', 0).style('cursor', 'pointer').style('opacity', 0).call(drag);
      g.transition().duration(DUR * 400).style('opacity', 1);
      const memeG = g.filter(d => d.type === 'meme');
      memeG.append('circle').attr('r', 24);
      memeG.append('image').attr('x', -22).attr('y', -22).attr('width', 44).attr('height', 44)
        .attr('clip-path', 'url(#walk-clip)').attr('preserveAspectRatio', 'xMidYMid slice')
        .attr('href', d => memeImg(d.m));
      const propG = g.filter(d => d.type === 'prop');
      propG.append('rect').attr('rx', 11).attr('height', 22).attr('y', -11)
        .attr('fill', d => PROP_FIELDS[d.field].color);
      propG.append('text').attr('dy', '.35em').attr('text-anchor', 'middle').text(d => d.value);
      propG.each(function() {
        const t = d3.select(this).select('text').node();
        const w = Math.max(40, t.getComputedTextLength() + 18);
        d3.select(this).select('rect').attr('x', -w / 2).attr('width', w);
      });
      g.on('click', (e, d) => {
        if (e.defaultPrevented) return;
        if (d.type === 'meme') { d.expanded ? selectNode(d) : expandMeme(d); }
        else expandProp(d);
      })
        .on('keydown', (e, d) => { if (e.key === 'Enter') d.type === 'meme' ? expandMeme(d) : expandProp(d); })
        .on('mouseenter', (e, d) => showTip(d.type === 'meme'
          ? tipWithImage(d.m, `${(d.m.popularityViews || 0).toLocaleString()} views`)
          : `<small>${escHtml(PROP_FIELDS[d.field].label)}</small><br><b>${escHtml(d.value)}</b>`, e))
        .on('mousemove', moveTip)
        .on('mouseleave', hideTip);
      return g;
    });
    walk.nodeG.selectAll('.walk-node').classed('expanded', d => !!d.expanded).classed('selected', d => d === walk.selected);

    walk.sim.nodes(walk.nodes);
    walk.sim.force('link').links(walk.links);
    walk.sim.alpha(.9).restart();
  }

  function walkTick() {
    walk.linkG.selectAll('line')
      .attr('x1', l => l.source.x).attr('y1', l => l.source.y)
      .attr('x2', l => l.target.x).attr('y2', l => l.target.y);
    walk.nodeG.selectAll('.walk-node').attr('transform', d => `translate(${d.x},${d.y})`);
  }

  /* ═════════════════════════════════════════════════════════════════════════
     4. PLATFORM STORY — scroll-driven streamgraph
     ═════════════════════════════════════════════════════════════════════════ */
  const story = { step: 0, mode: 'count' };

  function storyData() {
    if (story.data) return story.data;
    const Y0 = 2004, Y1 = 2025;
    // Same plausibility filter as the Platform × TimePeriod chart: drop memes dated
    // before their platform existed (see MODERN_PLATFORMS / POST2015_PLATFORMS).
    const rows = Object.values(memes()).filter(m => {
      const yr = yearOf(m), p = m.hasOriginPlatform;
      if (!p || !yr || yr < Y0 || yr > Y1) return false;
      if (yr < 2010 && MODERN_PLATFORMS.has(p)) return false;
      if (yr < 2016 && POST2015_PLATFORMS.has(p)) return false;
      return true;
    });
    const totals = d3.rollup(rows, v => v.length, m => m.hasOriginPlatform);
    const top = [...totals].sort((a, b) => b[1] - a[1]).slice(0, 8).map(d => d[0]);
    if (totals.has('Vine') && !top.includes('Vine')) top.push('Vine');
    const keys = [...top, 'Other'];
    const years = d3.range(Y0, Y1 + 1);
    const table = years.map(y => {
      const row = { year: y };
      keys.forEach(k => { row[k] = 0; });
      return row;
    });
    rows.forEach(m => {
      const k = top.includes(m.hasOriginPlatform) ? m.hasOriginPlatform : 'Other';
      table[yearOf(m) - Y0][k]++;
    });
    const share = (a, b, k) => {
      const slice = table.filter(r => r.year >= a && r.year <= b);
      const tot = d3.sum(slice, r => d3.sum(keys, kk => r[kk]));
      return tot ? d3.sum(slice, r => r[k]) / tot : 0;
    };
    const topIn = (a, b, n) => keys.filter(k => k !== 'Other')
      .map(k => ({ k, s: share(a, b, k) })).sort((x, y) => y.s - x.s).slice(0, n);
    const topMemes = (a, b, plats) => rows
      .filter(m => yearOf(m) >= a && yearOf(m) <= b && (!plats || plats.includes(m.hasOriginPlatform)))
      .sort((x, y) => (y.popularityViews || 0) - (x.popularityViews || 0)).slice(0, 4);
    const pct = v => Math.round(v * 100) + '%';

    const peak = table.reduce((best, r) => {
      const t = d3.sum(keys, k => r[k]);
      return t > best.t ? { y: r.year, t } : best;
    }, { y: null, t: 0 });

    const steps = [];
    steps.push({ range: [Y0, Y1], hi: null,
      title: 'The archive',
      text: `${rows.length.toLocaleString()} of the 5,000 memes name the platform they came from. The count per year peaks in ${peak.y} (${peak.t.toLocaleString()} memes).`,
      memes: topMemes(Y0, Y1) });
    const e1 = topIn(Y0, 2012, 2);
    steps.push({ range: [Y0, 2012], hi: e1.map(d => d.k),
      title: 'Before 2013',
      text: `${e1.map(d => `${d.k} (${pct(d.s)})`).join(' and ')} dominate the early record of attributed memes.`,
      memes: topMemes(Y0, 2012, e1.map(d => d.k)) });
    const vineYears = rows.filter(m => m.hasOriginPlatform === 'Vine').map(yearOf);
    const e2 = topIn(2013, 2017, 1);
    steps.push({ range: [2013, 2017], hi: vineYears.length ? [e2[0].k, 'Vine'] : [e2[0].k],
      title: '2013–2017',
      text: `${e2[0].k} leads with ${pct(e2[0].s)}.` + (vineYears.length
        ? ` Vine, the six-second video app, accounts for ${vineYears.length} memes dated ${d3.min(vineYears)}–${d3.max(vineYears)}.` : ''),
      memes: topMemes(2013, 2017, vineYears.length ? ['Vine'] : [e2[0].k]) });
    const e3 = topIn(2018, 2021, 2);
    steps.push({ range: [2018, 2021], hi: e3.map(d => d.k),
      title: '2018–2021',
      text: `${e3.map(d => `${d.k} (${pct(d.s)})`).join(' and ')} carry the busiest years of the dataset.`,
      memes: topMemes(2018, 2021, e3.map(d => d.k)) });
    if (keys.includes('TikTok')) {
      const early = share(2013, 2017, 'TikTok'), late = share(2022, Y1, 'TikTok');
      steps.push({ range: [2022, Y1], hi: ['TikTok'],
        title: '2022 onward',
        text: `TikTok grows from ${pct(early)} of attributed memes in 2013–2017 to ${pct(late)} since 2022.`,
        memes: topMemes(2022, Y1, ['TikTok']) });
    }
    story.data = { keys, table, steps, years, rows };
    return story.data;
  }

  function buildPlatformStory() {
    const wrap = document.getElementById('graph-story');
    const stepsEl = document.getElementById('story-steps');
    const bar = document.getElementById('story-controls');
    if (!wrap || !stepsEl) return;
    const { steps } = storyData();

    if (!stepsEl.dataset.ready) {
      stepsEl.dataset.ready = '1';
      stepsEl.innerHTML = steps.map((s, i) =>
        `<article class="story-step" data-step="${i}"><h3>${escHtml(s.title)}</h3><p>${escHtml(s.text)}</p>` +
        `<div class="story-thumbs">${s.memes.map(m =>
          `<a href="#meme/${encodeURIComponent(m.slug)}" title="${escHtml(slugToName(m.slug))}">${memeImgTag(m, slugToName(m.slug))}</a>`).join('')}</div></article>`).join('');
      const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
          if (!e.isIntersecting) return;
          story.step = +e.target.dataset.step;
          stepsEl.querySelectorAll('.story-step').forEach(el => el.classList.toggle('active', el === e.target));
          updateStory();
        });
      }, { rootMargin: '-45% 0px -45% 0px' });
      stepsEl.querySelectorAll('.story-step').forEach(el => obs.observe(el));

      if (bar) {
        [['count', 'Memes per year'], ['share', 'Share of year']].forEach(([mode, text]) => {
          const b = controlBtn(text, () => { story.mode = mode; setActive(bar, b); drawStory(true); });
          b.dataset.group = 'mode';
          if (mode === story.mode) b.classList.add('active');
          bar.appendChild(b);
        });
      }
    }
    drawStory(false);
  }

  function drawStory(animate) {
    const wrap = document.getElementById('graph-story');
    const { keys, table } = storyData();
    const { W, H } = wrapSize(wrap, 520);
    const mobile = isMobile();
    const M = mobile ? { t: 14, r: 10, b: 28, l: 10 } : { t: 24, r: 28, b: 34, l: 24 };
    const iw = W - M.l - M.r, ih = H - M.t - M.b;

    const stack = d3.stack().keys(keys).order(d3.stackOrderInsideOut)
      .offset(story.mode === 'share' ? d3.stackOffsetExpand : d3.stackOffsetWiggle)(table);
    const x = d3.scaleLinear().domain(d3.extent(table, r => r.year)).range([0, iw]);
    const y = d3.scaleLinear()
      .domain([d3.min(stack, s => d3.min(s, d => d[0])), d3.max(stack, s => d3.max(s, d => d[1]))])
      .range([ih, 0]);
    const area = d3.area().curve(d3.curveBasis)
      .x(d => x(d.data.year)).y0(d => y(d[0])).y1(d => y(d[1]));

    let svg = d3.select(wrap).select('svg');
    if (svg.empty() || !animate) {
      wrap.innerHTML = '';
      svg = d3.select(wrap).append('svg').attr('viewBox', `0 0 ${W} ${H}`)
        .attr('role', 'img').attr('aria-label', 'Streamgraph of meme origin platforms per year');
      const g = svg.append('g').attr('class', 'story-g').attr('transform', `translate(${M.l},${M.t})`);
      g.append('rect').attr('class', 'story-band').attr('y', -M.t).attr('height', H).attr('width', 0);
      g.append('g').attr('class', 'story-layers');
      g.append('g').attr('class', 'story-axis').attr('transform', `translate(0,${ih + 6})`)
        .call(d3.axisBottom(x).ticks(mobile ? 5 : 11).tickFormat(d3.format('d')).tickSize(0))
        .call(s => s.select('.domain').remove());
      g.append('g').attr('class', 'story-labels');
    }
    const g = svg.select('.story-g');
    g.select('.story-layers').selectAll('path').data(stack, s => s.key).join('path')
      .attr('fill', s => PLATFORM_COLOR[s.key] || '#b0b8c8')
      .on('mouseenter', (e, s) => {
        const tot = d3.sum(table, r => r[s.key]);
        showTip(`<b>${escHtml(s.key)}</b><br>${tot.toLocaleString()} memes 2004–2025<br><small>click to browse</small>`, e);
      })
      .on('mousemove', moveTip).on('mouseleave', hideTip)
      .on('click', (e, s) => {
        const slugs = storyData().rows.filter(m =>
          s.key === 'Other' ? !keys.includes(m.hasOriginPlatform) : m.hasOriginPlatform === s.key
        ).map(m => m.slug);
        openPanel(s.key, slugs, 'platform story', 'platform');
      })
      .transition().duration(animate ? DUR * 700 : 0).attr('d', area);

    // Direct labels at the widest point of each layer (desktop)
    const labels = mobile ? [] : stack.map(s => {
      const best = s.reduce((b, d) => (d[1] - d[0] > b[1] - b[0] ? d : b), s[0]);
      return { key: s.key, x: x(best.data.year), y: y((best[0] + best[1]) / 2), th: y(best[0]) - y(best[1]) };
    }).filter(l => l.th > 14);
    g.select('.story-labels').selectAll('text').data(labels, l => l.key).join('text')
      .attr('text-anchor', 'middle').attr('dy', '.35em')
      .transition().duration(animate ? DUR * 700 : 0)
      .attr('x', l => Math.min(iw - 30, Math.max(30, l.x))).attr('y', l => l.y).text(l => l.key);

    story.x = x;
    updateStory();
  }

  function updateStory() {
    const wrap = document.getElementById('graph-story');
    if (!wrap || !story.x) return;
    const s = storyData().steps[story.step];
    if (!s) return;
    const g = d3.select(wrap).select('.story-g');
    const [a, b] = s.range;
    g.select('.story-band').transition().duration(DUR * 500)
      .attr('x', story.x(a) - 4).attr('width', Math.max(0, story.x(b) - story.x(a) + 8));
    g.select('.story-layers').selectAll('path').transition().duration(DUR * 500)
      .attr('opacity', d => !s.hi || s.hi.includes(d.key) ? 1 : 0.18);
    g.select('.story-labels').selectAll('text')
      .attr('opacity', d => !s.hi || s.hi.includes(d.key) ? 1 : 0.3);
  }

  /* ═════════════════════════════════════════════════════════════════════════
     5. CLASSIFIER CONFIDENCE — dot plot of CLIP scores per image type
     ═════════════════════════════════════════════════════════════════════════ */
  const conf = { t: 0.5 };

  function buildConfidence() {
    const wrap = document.getElementById('graph-confidence');
    const bar = document.getElementById('confidence-controls');
    if (!wrap || !bar) return;
    const items = Object.values(memes())
      .filter(m => m.hasImageType && m.clipImageTypeScore != null)
      .map(m => ({ m, type: m.hasImageType, score: +m.clipImageTypeScore }));
    const types = ['Cartoon', 'Photograph', 'Drawing', 'Illustration', 'Painting']
      .filter(t => items.some(d => d.type === t));

    if (!bar.dataset.ready) {
      bar.dataset.ready = '1';
      bar.innerHTML =
        `<label class="viz-slider"><span>Confidence threshold <b id="conf-val">${conf.t.toFixed(2)}</b></span>` +
        `<input type="range" id="conf-range" min="0.25" max="0.95" step="0.01" value="${conf.t}" aria-label="CLIP confidence threshold"></label>` +
        '<span class="viz-note" id="conf-summary"></span>';
      bar.querySelector('input').addEventListener('input', e => {
        conf.t = +e.target.value;
        document.getElementById('conf-val').textContent = conf.t.toFixed(2);
        drawConfidence();
      });
    }

    wrap.innerHTML = '';
    const { W, H } = wrapSize(wrap, 540);
    const { canvas, ctx } = makeCanvas(wrap, W, H);
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Dot plot of CLIP classifier confidence per image type');
    const mobile = isMobile();
    const pad = { l: mobile ? 12 : 120, r: mobile ? 12 : 170, t: 18, b: 34 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const rowH = ih / types.length;
    const x = d3.scaleLinear().domain([0.25, 1]).range([pad.l, pad.l + iw]);

    // Pick the largest dot size for which every stack fits its row
    let d = 7;
    let bins;
    for (let step = 70; step >= 14; step -= 2) {
      d = step / 10;
      bins = {};
      let fits = true;
      types.forEach(t => {
        const b = {};
        items.filter(it => it.type === t).forEach(it => {
          const k = Math.floor((x(it.score) - pad.l) / d);
          (b[k] || (b[k] = [])).push(it);
        });
        bins[t] = b;
        const maxN = d3.max(Object.values(b), v => v.length) || 0;
        if (maxN * d > rowH - 8) fits = false;
      });
      if (fits) break;
    }
    types.forEach((t, ti) => {
      const mid = pad.t + rowH * ti + rowH / 2;
      Object.entries(bins[t]).forEach(([k, list]) => {
        list.sort((a, b) => a.score - b.score).forEach((it, j) => {
          const off = (j % 2 ? 1 : -1) * Math.ceil(j / 2) * d;
          it.x = pad.l + (+k + 0.5) * d;
          it.y = mid + off;
        });
      });
    });
    Object.assign(conf, { ctx, W, H, items, types, x, pad, rowH, d, mobile });
    conf.tree = d3.quadtree(items, it => it.x, it => it.y);
    drawConfidence();

    canvas.addEventListener('mousemove', e => {
      const r = canvas.getBoundingClientRect();
      const it = conf.tree.find(e.clientX - r.left, e.clientY - r.top, Math.max(6, conf.d * 2));
      canvas.style.cursor = it ? 'pointer' : 'default';
      if (it) showTip(tipWithImage(it.m, `${escHtml(it.type)} · CLIP score <b>${it.score.toFixed(3)}</b>`), e);
      else hideTip();
    });
    canvas.addEventListener('mouseleave', hideTip);
    canvas.addEventListener('click', e => {
      const r = canvas.getBoundingClientRect();
      const it = conf.tree.find(e.clientX - r.left, e.clientY - r.top, Math.max(6, conf.d * 2));
      if (it) { hideTip(); openDetail(it.m.slug); }
    });
  }

  const TYPE_COLOR = { Cartoon: '#e0873a', Photograph: '#3a8fd8', Drawing: '#8e5cc9', Illustration: '#2a9d6f', Painting: '#c9505f' };

  function drawConfidence() {
    const { ctx, W, H, items, types, x, pad, rowH, d, mobile, t } = conf;
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    ctx.textBaseline = 'middle';

    types.forEach((ty, i) => {
      const y0 = pad.t + rowH * i;
      if (i % 2) { ctx.fillStyle = 'rgba(0,0,0,.025)'; ctx.fillRect(pad.l, y0, W - pad.l - pad.r, rowH); }
      const all = items.filter(it => it.type === ty);
      const below = all.filter(it => it.score < t).length;
      ctx.fillStyle = '#111';
      ctx.font = '600 12px system-ui, sans-serif';
      ctx.textAlign = mobile ? 'left' : 'right';
      ctx.fillText(ty, mobile ? pad.l + 2 : pad.l - 12, mobile ? y0 + 10 : y0 + rowH / 2 - 7);
      ctx.font = '11px system-ui, sans-serif';
      ctx.fillStyle = '#666';
      if (!mobile) ctx.fillText(all.length.toLocaleString() + ' memes', pad.l - 12, y0 + rowH / 2 + 8);
      ctx.textAlign = mobile ? 'right' : 'left';
      ctx.fillStyle = below ? '#c0392b' : '#666';
      ctx.fillText(`${below.toLocaleString()} below (${(below / all.length * 100).toFixed(1)}%)`,
        mobile ? W - pad.r - 2 : W - pad.r + 14, mobile ? y0 + 10 : y0 + rowH / 2);
    });

    items.forEach(it => {
      ctx.fillStyle = it.score < t ? '#cfcfcf' : TYPE_COLOR[it.type] || '#888';
      ctx.beginPath();
      ctx.arc(it.x, it.y, Math.max(0.7, d / 2 - 0.3), 0, Math.PI * 2);
      ctx.fill();
    });

    // Threshold line
    const tx = x(t);
    ctx.strokeStyle = '#c0392b';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(tx, pad.t - 6); ctx.lineTo(tx, H - pad.b + 4); ctx.stroke();
    ctx.setLineDash([]);

    // Axis
    ctx.fillStyle = '#666';
    ctx.font = '10px system-ui, sans-serif';
    ctx.textAlign = 'center';
    x.ticks(mobile ? 4 : 8).forEach(v => ctx.fillText(v.toFixed(1), x(v), H - pad.b + 16));
    ctx.fillText('CLIP zero-shot confidence for the assigned image type', pad.l + (W - pad.l - pad.r) / 2, H - 6);

    const belowAll = items.filter(it => it.score < t).length;
    const sum = document.getElementById('conf-summary');
    if (sum) sum.textContent = `At ${t.toFixed(2)}, ${belowAll.toLocaleString()} memes (${(belowAll / items.length * 100).toFixed(1)}%) would fall back to Unknown.`;
  }

  /* ═════════════════════════════════════════════════════════════════════════
     6. FLOW — Platform → Format → Image type → Text presence (Sankey)
     ═════════════════════════════════════════════════════════════════════════ */
  function buildFlow() {
    const wrap = document.getElementById('graph-flow');
    if (!wrap) return;
    if (!d3.sankey) {
      wrap.innerHTML = '<p class="viz-empty">Sankey library failed to load.</p>';
      return;
    }
    const all = Object.values(memes());
    const topOf = (fn, n) => {
      const c = d3.rollup(all, v => v.length, fn);
      return new Set([...c].filter(d => d[0] && d[0] !== 'Unknown').sort((a, b) => b[1] - a[1]).slice(0, n).map(d => d[0]));
    };
    const topPlat = topOf(m => m.hasOriginPlatform, 7);
    const primaryFormat = m => (m.hasFormat || []).find(f => f && f !== 'Unknown') || null;
    const topFmt = topOf(primaryFormat, 8);
    const stages = [
      { key: 'platform', label: 'Origin platform', get: m => !m.hasOriginPlatform ? 'Unattributed' : (topPlat.has(m.hasOriginPlatform) ? m.hasOriginPlatform : 'Other platform') },
      { key: 'format', label: 'Primary format', get: m => { const f = primaryFormat(m); return !f ? 'No format' : (topFmt.has(f) ? f : 'Other format'); } },
      { key: 'type', label: 'Image type', get: m => m.hasImageType || 'Unknown type' },
      { key: 'text', label: 'Text', get: m => m.hasTextPresence === 'ContainsText' ? 'Contains text' : 'No text' }
    ];

    const nodeMap = new Map();
    const linkMap = new Map();
    const node = (si, name) => {
      const id = si + ':' + name;
      if (!nodeMap.has(id)) nodeMap.set(id, { id, name, stage: si, memes: new Set() });
      return nodeMap.get(id);
    };
    all.forEach(m => {
      const path = stages.map((s, si) => node(si, s.get(m)));
      path.forEach(n => n.memes.add(m.slug));
      for (let i = 0; i < path.length - 1; i++) {
        const key = path[i].id + '→' + path[i + 1].id;
        if (!linkMap.has(key)) linkMap.set(key, { source: path[i].id, target: path[i + 1].id, value: 0, memes: new Set() });
        const l = linkMap.get(key);
        l.value++;
        l.memes.add(m.slug);
      }
    });

    wrap.innerHTML = '';
    const { W, H } = wrapSize(wrap, 560);
    const mobile = isMobile();
    const M = { t: 26, r: mobile ? 62 : 120, b: 10, l: mobile ? 8 : 12 };
    const sankey = d3.sankey().nodeId(d => d.id).nodeWidth(12).nodePadding(mobile ? 6 : 9)
      .extent([[M.l, M.t], [W - M.r, H - M.b]]);
    const graph = sankey({
      nodes: [...nodeMap.values()].map(d => ({ ...d })),
      links: [...linkMap.values()].map(d => ({ ...d }))
    });

    const nodeColor = n => {
      if (n.stage === 0) return PLATFORM_COLOR[n.name] || (n.name === 'Other platform' ? PLATFORM_COLOR.Other : PLATFORM_COLOR.Unattributed);
      if (n.stage === 2) return TYPE_COLOR[n.name] || '#999';
      if (n.stage === 3) return n.name === 'Contains text' ? '#111' : '#aaa';
      return '#e0873a';
    };

    const svg = d3.select(wrap).append('svg').attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', 'Flow from origin platform to format, image type and text presence');
    const colX = d3.rollup(graph.nodes, v => v[0].x0, d => d.stage);
    stages.forEach((s, si) => {
      svg.append('text').attr('class', 'flow-stage').attr('x', colX.get(si)).attr('y', 12).text(s.label.toUpperCase());
    });
    const pathGen = d3.sankeyLinkHorizontal();
    const base = svg.append('g').attr('class', 'flow-links').selectAll('path').data(graph.links).join('path')
      .attr('d', pathGen).attr('stroke-width', l => Math.max(1, l.width))
      .attr('stroke', l => nodeColor(l.source)).attr('stroke-opacity', .28);
    const hiG = svg.append('g').attr('class', 'flow-hi');

    const nodes = svg.append('g').selectAll('g').data(graph.nodes).join('g').attr('class', 'flow-node')
      .attr('tabindex', 0).style('cursor', 'pointer');
    nodes.append('rect').attr('x', d => d.x0).attr('y', d => d.y0)
      .attr('width', d => d.x1 - d.x0).attr('height', d => Math.max(1, d.y1 - d.y0))
      .attr('fill', nodeColor);
    nodes.filter(d => d.y1 - d.y0 > 9 || !mobile).append('text')
      .attr('x', d => d.stage === stages.length - 1 ? d.x1 + 6 : d.x1 + 5)
      .attr('y', d => (d.y0 + d.y1) / 2).attr('dy', '.35em')
      .text(d => (d.y1 - d.y0 > 7 ? d.name : '') + (d.y1 - d.y0 > 7 && !mobile ? ` ${d.value.toLocaleString()}` : ''));

    function highlight(n) {
      hiG.selectAll('path').remove();
      if (!n) { base.attr('stroke-opacity', .28); nodes.classed('dim', false); return; }
      base.attr('stroke-opacity', .06);
      const touched = new Set();
      graph.links.forEach(l => {
        let k = 0;
        l.memes.forEach(s => { if (n.memes.has(s)) k++; });
        if (!k) return;
        touched.add(l.source.id); touched.add(l.target.id);
        hiG.append('path').attr('d', pathGen(l)).attr('stroke', nodeColor(n))
          .attr('stroke-width', Math.max(1, l.width * k / l.value)).attr('stroke-opacity', .75);
      });
      nodes.classed('dim', d => !touched.has(d.id) && d.id !== n.id);
    }
    nodes.on('mouseenter focus', (e, n) => {
      highlight(n);
      showTip(`<b>${escHtml(n.name)}</b><br>${n.value.toLocaleString()} memes<br><small>click to browse</small>`,
        e.clientX != null ? e : { clientX: innerWidth / 2, clientY: innerHeight / 2 });
    })
      .on('mousemove', moveTip)
      .on('mouseleave blur', () => { highlight(null); hideTip(); })
      .on('click', (e, n) => openPanel(n.name, [...n.memes].sort((a, b) =>
        (memes()[b].popularityViews || 0) - (memes()[a].popularityViews || 0)), 'flow', stages[n.stage].label));
    base.on('mouseenter', (e, l) => showTip(`${escHtml(l.source.name)} → ${escHtml(l.target.name)}<br><b>${l.value.toLocaleString()}</b> memes`, e))
      .on('mousemove', moveTip).on('mouseleave', hideTip)
      .on('click', (e, l) => openPanel(`${l.source.name} → ${l.target.name}`, [...l.memes], 'flow', 'link'));
  }
})();
