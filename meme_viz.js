/* ── State ─────────────────────────────────────────────────────────────────── */
let DATA        = null;
let panelSlugs  = [];
let panelShown  = 0;
let dsPage      = 0;
let dsFiltered  = [];
const PAGE_SIZE = 30;
const DS_PER_PAGE = 60;

/* ── Boot ──────────────────────────────────────────────────────────────────── */
fetch('meme_data.json')
  .then(r => r.json())
  .then(d => {
    DATA = d;
    document.getElementById('loader').classList.add('done');
    buildTooltip();
    buildHero();
    buildGraphs();
    buildNav();
    route();
    startLiveReload();
  })
  .catch(() => {
    document.querySelector('.loader-text').textContent =
      'Error loading data. Run: python -m http.server 8080';
  });

/* ── Live reload (polls while scraper runs) ──────────────────────────────── */
let _lastDataSize = 0;
function startLiveReload() {
  setInterval(() => {
    fetch('meme_data.json', { cache: 'no-store' })
      .then(r => {
        const size = parseInt(r.headers.get('content-length') || '0', 10);
        return r.json().then(d => ({ d, size }));
      })
      .then(({ d, size }) => {
        if (size && size === _lastDataSize) return;
        _lastDataSize = size;
        DATA = d;
        // reset and re-render all graphs
        document.getElementById('graph-time').innerHTML = '';
        document.getElementById('graph-popularity').innerHTML = '';
        document.getElementById('graph-platform-time').innerHTML = '';
        buildTimeline();
        buildPopularityByFormat();
        buildPlatformTimeStacked();
        // reset manovich flags so they rebuild on next scroll-into-view
        _imagePlotBuilt = false;
        _chronoBuilt    = false;
        _powerlawBuilt  = false;
        document.getElementById('wrap-imageplot').innerHTML = '';
        document.getElementById('wrap-chrono').innerHTML    = '';
        document.getElementById('wrap-powerlaw').innerHTML  = '';
        console.log('[live] meme_data.json updated — visualizations refreshed');
      })
      .catch(() => {});
  }, 30_000);
}

/* ══════════════════════════════════════════════════════════════════════════
   ROUTER
   ══════════════════════════════════════════════════════════════════════════ */
function route() {
  const hash = location.hash.replace(/^#\/?/, '');
  if (!DATA) return;
  if (hash.startsWith('meme/')) {
    showMemePage(decodeURIComponent(hash.slice(5)));
  } else if (hash === 'about') {
    showPage('about');
    if (!document.getElementById('about-content').hasChildNodes()) buildAboutPage();
  } else if (hash === 'dataset') {
    showPage('dataset');
    if (!dsFiltered.length) buildDatasetPage();
  } else if (hash === 'ontology') {
    showPage('ontology');
  } else {
    showViz();
  }
}
window.addEventListener('hashchange', route);

function showPage(name) {
  document.getElementById('app').classList.add('hidden');
  document.getElementById('dot-nav').classList.add('hidden');
  document.getElementById('node-panel').classList.add('hidden');
  document.getElementById('app').classList.remove('panel-open');
  ['about', 'dataset', 'ontology', 'meme'].forEach(p =>
    document.getElementById('page-' + p).classList.add('hidden'));
  document.getElementById('page-' + name).classList.remove('hidden');
  setActiveNav(name);
}

function showViz() {
  ['about', 'dataset', 'ontology', 'meme'].forEach(p =>
    document.getElementById('page-' + p).classList.add('hidden'));
  document.getElementById('app').classList.remove('hidden');
  document.getElementById('dot-nav').classList.remove('hidden');
  setActiveNav('viz');
}

function setActiveNav(page) {
  document.querySelectorAll('.topnav-link').forEach(l =>
    l.classList.toggle('active', l.dataset.page === page));
}

/* ── Shared tooltip ────────────────────────────────────────────────────────── */
let tip;
function buildTooltip() {
  tip = document.createElement('div');
  tip.id = 'tooltip';
  document.body.appendChild(tip);
}
function showTip(html, e) {
  tip.innerHTML = html;
  tip.style.display = 'block';
  moveTip(e);
}
function moveTip(e) {
  const x = e.clientX + 14, y = e.clientY - 10;
  tip.style.left = Math.min(x, window.innerWidth - 260) + 'px';
  tip.style.top  = Math.max(y, 4) + 'px';
}
function hideTip() { tip.style.display = 'none'; }

/* ── Hero image collage ────────────────────────────────────────────────────── */
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function buildHero() {
  const container = document.getElementById('hero-images');
  if (!container || !DATA) return;
  shuffle(Object.keys(DATA.memes)).slice(0, 200).forEach(slug => {
    const meme = DATA.memes[slug];
    if (!meme?.imageFilename) return;
    const img     = document.createElement('img');
    img.src       = meme.imageURL || `images_flat/${meme.imageFilename}`;
    img.alt       = slug;
    img.title     = slug.replace(/_/g, ' ');
    img.loading   = 'lazy';
    img.addEventListener('click', () => openDetail(slug));
    container.appendChild(img);
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   1. POPULARITY x FORMAT — Bubble chart
   ═══════════════════════════════════════════════════════════════════════════ */
function buildPopularityByFormat() {
  const wrap = document.getElementById('graph-popularity');
  if (!wrap || !DATA) return;

  const popularity = DATA.graphs.popularity || {};
  const points = [...(popularity.points || [])]
    .filter(d => d && d.format)
    .sort((a, b) => (b.avgViews || 0) - (a.avgViews || 0));
  const nodeToMemes = popularity.nodeToMemes || {};
  if (!points.length) {
    wrap.innerHTML = '<div style="padding:20px;color:#666">No popularity data available yet.</div>';
    return;
  }

  const rect = wrap.getBoundingClientRect();
  const W = rect.width || (window.innerWidth - 48);
  const H = rect.height || (window.innerHeight - 72);

  const margin = { top: 30, right: 28, bottom: 140, left: 100 };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top - margin.bottom;

  const x = d3.scaleBand()
    .domain(points.map(d => d.format))
    .range([0, iW])
    .padding(0.22);

  const yMax = d3.max(points, d => d.avgViews || 0) || 1;
  const y = d3.scaleLinear()
    .domain([0, yMax * 1.08])
    .range([iH, 0]);

  const maxEntries = d3.max(points, d => d.entries || 0) || 1;
  const r = d3.scaleSqrt()
    .domain([0, maxEntries])
    .range([4, Math.max(14, Math.min(42, x.bandwidth() * 0.45))]);

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `${-20} ${-20} ${W + 40} ${H + 40}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  g.append('g')
    .attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .attr('transform', 'rotate(-40)')
    .style('text-anchor', 'end')
    .attr('dx', '-.5em')
    .attr('dy', '.2em')
    .style('font-size', '11px')
    .style('fill', '#1a1a3a');

  g.append('g')
    .call(d3.axisLeft(y).ticks(6).tickFormat(d3.format('.2s')))
    .selectAll('text')
    .style('font-size', '11px')
    .style('fill', '#1a1a3a');

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');

  g.append('text')
    .attr('x', -iH / 2)
    .attr('y', -64)
    .attr('transform', 'rotate(-90)')
    .attr('text-anchor', 'middle')
    .attr('fill', '#444')
    .attr('font-size', 12)
    .text('Average views');

  const color = d3.scaleSequential(d3.interpolateYlOrRd)
    .domain([0, yMax]);

  g.selectAll('circle.pop')
    .data(points)
    .join('circle')
    .attr('class', 'pop')
    .attr('cx', d => x(d.format) + x.bandwidth() / 2)
    .attr('cy', d => y(d.avgViews || 0))
    .attr('r', d => r(d.entries || 0))
    .attr('fill', d => color(d.avgViews || 0))
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)
    .attr('opacity', 0.88)
    .style('cursor', 'pointer')
    .on('mouseover', (e, d) => {
      showTip(
        `<b>${d.format}</b><br>avg views: <b>${Math.round(d.avgViews || 0).toLocaleString()}</b>` +
        `<br>entries: <b>${(d.entries || 0).toLocaleString()}</b>` +
        `<br>entries with views: <b>${(d.entriesWithViews || 0).toLocaleString()}</b>` +
        '<br><small>click to browse memes</small>',
        e
      );
    })
    .on('mousemove', moveTip)
    .on('mouseout', hideTip)
    .on('click', (e, d) => {
      openPanel(d.format, nodeToMemes[d.format] || [], 'popularity', 'format');
    });
}

/* ═══════════════════════════════════════════════════════════════════════════
   2. FORMAT TIMELINE — Bubble matrix (year × format)
   ═══════════════════════════════════════════════════════════════════════════ */
function buildTimeline() {
  const wrap = document.getElementById('graph-time');
  if (!wrap || !DATA) return;

  const { nodes, links, nodeToMemes } = DATA.graphs.time;
  const yearNodes = nodes.filter(d => d.group === 'year').sort((a, b) => a.year - b.year);
  const fmtNodes  = nodes.filter(d => d.group === 'format').sort((a, b) => b.count - a.count);
  const years = yearNodes.map(d => d.year);
  const fmts  = fmtNodes.map(d => d.id);

  const matrix = {};
  links.forEach(l => {
    const yr  = String(l.source?.id ?? l.source);
    const fmt = String(l.target?.id ?? l.target);
    if (!matrix[fmt]) matrix[fmt] = {};
    matrix[fmt][yr] = (matrix[fmt][yr] || 0) + (l.value || 1);
  });

  const rect = wrap.getBoundingClientRect();
  const W = rect.width  || window.innerWidth  - 48;
  const H = rect.height || window.innerHeight - 72;

  const margin = { top: 36, right: 56, bottom: 80, left: 180 };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top  - margin.bottom;

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `${-24} ${-24} ${W + 48} ${H + 48}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);

  const root = svg.append('g');
  const g = root.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  const xScale = d3.scaleBand().domain(years).range([0, iW]).padding(.18);
  const yScale = d3.scaleBand().domain(fmts).range([0, iH]).padding(.28);
  const maxVal = d3.max(links, d => d.value) || 1;
  const rMax   = Math.min(xScale.bandwidth(), yScale.bandwidth()) / 2 * 0.9;
  const rScale = d3.scaleSqrt().domain([0, maxVal]).range([0, rMax]);
  const color  = d3.scaleOrdinal(d3.schemeSet2).domain(fmts);

  g.append('g').selectAll('line.gy').data(fmts).join('line')
    .attr('x1', 0).attr('x2', iW)
    .attr('y1', d => yScale(d) + yScale.bandwidth() / 2)
    .attr('y2', d => yScale(d) + yScale.bandwidth() / 2)
    .attr('stroke', '#e0e0ec').attr('stroke-width', .6);

  g.append('g').selectAll('line.gx').data(years).join('line')
    .attr('x1', d => xScale(d) + xScale.bandwidth() / 2)
    .attr('x2', d => xScale(d) + xScale.bandwidth() / 2)
    .attr('y1', 0).attr('y2', iH)
    .attr('stroke', '#ebebf5').attr('stroke-width', .6);

  const bubbles = [];
  fmts.forEach(fmt => years.forEach(year => {
    const count = (matrix[fmt] || {})[String(year)] || 0;
    if (count > 0) bubbles.push({ fmt, year, count });
  }));

  g.selectAll('circle.bubble').data(bubbles).join('circle')
    .attr('cx', d => xScale(d.year) + xScale.bandwidth() / 2)
    .attr('cy', d => yScale(d.fmt)  + yScale.bandwidth() / 2)
    .attr('r',  d => rScale(d.count))
    .attr('fill', d => color(d.fmt))
    .attr('opacity', .82)
    .attr('stroke', 'white').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('mouseover', (e, d) =>
      showTip(`<b>${d.fmt}</b><br>${d.year}: <b>${d.count}</b> entries<br><small>click to browse</small>`, e))
    .on('mousemove', moveTip).on('mouseout', hideTip)
    .on('click', (e, d) => {
      const fmtSlugs = nodeToMemes[d.fmt] || [];
      const yearSet  = new Set(nodeToMemes[String(d.year)] || []);
      const filtered = fmtSlugs.filter(s => yearSet.has(s));
      openPanel(`${d.fmt} · ${d.year}`, filtered.length ? filtered : fmtSlugs, 'time', d.fmt);
    });

  g.selectAll('text.blabel')
    .data(bubbles.filter(d => rScale(d.count) > 10)).join('text')
    .attr('x', d => xScale(d.year) + xScale.bandwidth() / 2)
    .attr('y', d => yScale(d.fmt)  + yScale.bandwidth() / 2 + 4)
    .attr('text-anchor', 'middle')
    .attr('font-size', 10).attr('font-weight', '700')
    .attr('fill', 'white').attr('pointer-events', 'none')
    .text(d => d.count);

  g.append('g').attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(xScale).tickFormat(d3.format('d')))
    .selectAll('text')
    .attr('transform', 'rotate(-45)').style('text-anchor', 'end')
    .attr('dy', '.15em').attr('dx', '-.4em')
    .style('font-size', '11px').style('fill', '#1a1a3a');

  g.append('g').call(d3.axisLeft(yScale))
    .selectAll('text').style('font-size', '11px').style('fill', '#1a1a3a');

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');
}

/* ═══════════════════════════════════════════════════════════════════════════
   4. PLATFORM ORIGIN x TIME PERIOD — 100% stacked bars
   ═══════════════════════════════════════════════════════════════════════════ */
function buildPlatformTimeStacked() {
  const wrap = document.getElementById('graph-platform-time');
  if (!wrap || !DATA) return;

  const source = DATA.graphs.platformTime || {};
  const periods = source.periods || [];
  const comboToMemes = source.comboToMemes || {};
  if (!periods.length) {
    wrap.innerHTML = '<div style="padding:20px;color:#666">Platform/time data not available.</div>';
    return;
  }

  const platforms = [];
  periods.forEach(p => {
    (p.segments || []).forEach(s => {
      if (!platforms.includes(s.platform)) platforms.push(s.platform);
    });
  });

  const rect = wrap.getBoundingClientRect();
  const W = rect.width || (window.innerWidth - 48);
  const H = rect.height || (window.innerHeight - 72);

  const margin = { top: 30, right: 220, bottom: 70, left: 72 };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top - margin.bottom;

  const rows = periods.map(periodRow => {
    const row = { period: periodRow.period };
    platforms.forEach(p => { row[p] = 0; });
    (periodRow.segments || []).forEach(seg => {
      row[seg.platform] = seg.ratio || 0;
    });
    return row;
  });

  const x = d3.scaleBand()
    .domain(rows.map(d => d.period))
    .range([0, iW])
    .padding(0.22);

  const y = d3.scaleLinear().domain([0, 1]).range([iH, 0]);

  const color = d3.scaleOrdinal()
    .domain(platforms)
    .range(d3.schemeTableau10.concat(d3.schemeSet3));

  const stack = d3.stack().keys(platforms);
  const stacked = stack(rows);

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `${-20} ${-20} ${W + 40} ${H + 40}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);
  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  g.selectAll('g.layer')
    .data(stacked)
    .join('g')
    .attr('class', 'layer')
    .attr('fill', d => color(d.key))
    .selectAll('rect')
    .data(d => d.map(v => ({ ...v, key: d.key })))
    .join('rect')
    .attr('x', d => x(d.data.period))
    .attr('y', d => y(d[1]))
    .attr('height', d => Math.max(0, y(d[0]) - y(d[1])))
    .attr('width', x.bandwidth())
    .attr('stroke', '#fff')
    .attr('stroke-width', 1)
    .style('cursor', 'pointer')
    .on('mouseover', (e, d) => {
      const proportion = (d[1] - d[0]) * 100;
      showTip(`<b>${d.key}</b><br>${d.data.period}: <b>${proportion.toFixed(1)}%</b><br><small>click to browse</small>`, e);
    })
    .on('mousemove', moveTip)
    .on('mouseout', hideTip)
    .on('click', (e, d) => {
      const key = `${d.data.period}||${d.key}`;
      openPanel(`${d.data.period} · ${d.key}`, comboToMemes[key] || [], 'platformTime', 'segment');
    });

  g.append('g')
    .attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .style('font-size', '11px')
    .style('fill', '#1a1a3a');

  g.append('g')
    .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${Math.round(d * 100)}%`))
    .selectAll('text')
    .style('font-size', '11px')
    .style('fill', '#1a1a3a');

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');

  const legend = svg.append('g').attr('transform', `translate(${W - margin.right + 20},${margin.top})`);
  platforms.forEach((platform, i) => {
    const y0 = i * 20;
    legend.append('rect')
      .attr('x', 0)
      .attr('y', y0)
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', color(platform));
    legend.append('text')
      .attr('x', 18)
      .attr('y', y0 + 10)
      .attr('fill', '#1a1a3a')
      .attr('font-size', 11)
      .text(platform);
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   MANOVICH A — Visual Landscape  (saturation × brightness image grid)
   All 5,000 thumbs placed by sat (X) × lightness (Y) after loading
   color_data.json.  Uses absolute positioning on a pre-sized canvas so
   the browser never has to reflow 5 k elements.
   ═══════════════════════════════════════════════════════════════════════════ */
let _imagePlotBuilt = false;

function buildImagePlot() {
  if (_imagePlotBuilt) return;
  const wrap = document.getElementById('wrap-imageplot');
  if (!wrap || !DATA) return;

  wrap.innerHTML = '<div style="padding:24px;color:#888;font-size:.85rem">Loading colour data…</div>';

  fetch('color_data.json')
    .then(r => r.json())
    .then(colorData => {
      _imagePlotBuilt = true;
      _renderImagePlot(wrap, colorData);
    })
    .catch(() => {
      wrap.innerHTML = '<div style="padding:24px;color:#888">colour data unavailable — run compute_colors.py first</div>';
    });
}

function _renderImagePlot(wrap, colorData) {
  const slugs = Object.keys(DATA.memes).filter(s => {
    const m = DATA.memes[s];
    return m && m.imageFilename && colorData[s];
  });

  /* Grid geometry: 100 cols × rows-to-fit  */
  const COLS    = 100;
  const THUMB   = 24;   // px per cell (square)
  const GAP     = 1;
  const CELL    = THUMB + GAP;
  const ROWS    = Math.ceil(slugs.length / COLS);
  const W       = COLS * CELL;
  const H       = ROWS * CELL + 32; // extra for axis labels

  /* Sort: X = saturation (left dark/grey → right vivid),
           Y = lightness  (top dark → bottom bright)
     We bin into discrete grid positions so it looks like ImagePlot.     */
  const maxS = 100, maxL = 100;
  slugs.sort((a, b) => {
    const ca = colorData[a], cb = colorData[b];
    const sa = ca.s || 0, sb = cb.s || 0;
    const la = ca.l || 0, lb = cb.l || 0;
    // primary: saturation bin; secondary: lightness
    const binSa = Math.round(sa / maxS * (COLS - 1));
    const binSb = Math.round(sb / maxS * (COLS - 1));
    if (binSa !== binSb) return binSa - binSb;
    return la - lb;
  });

  wrap.style.height = H + 'px';
  wrap.style.position = 'relative';
  wrap.innerHTML = '';

  /* Axis labels */
  const axX = document.createElement('div');
  axX.style.cssText = 'position:absolute;bottom:4px;left:0;right:0;text-align:center;font-size:10px;color:rgba(255,255,255,.35);letter-spacing:.1em;pointer-events:none';
  axX.textContent = '← less saturated   SATURATION   more saturated →';
  wrap.appendChild(axX);

  const axY = document.createElement('div');
  axY.style.cssText = 'position:absolute;top:50%;left:4px;font-size:10px;color:rgba(255,255,255,.35);letter-spacing:.1em;pointer-events:none;transform:rotate(-90deg) translateX(-50%);transform-origin:left center;white-space:nowrap';
  axY.textContent = '← darker   BRIGHTNESS   brighter →';
  wrap.appendChild(axY);

  /* Build a col→array map so items in each col stack top-to-bottom by lightness */
  const cols = Array.from({ length: COLS }, () => []);
  slugs.forEach(slug => {
    const c = colorData[slug];
    const col = Math.min(COLS - 1, Math.round((c.s || 0) / maxS * (COLS - 1)));
    cols[col].push(slug);
  });
  /* Sort each column by lightness ascending (dark top → bright bottom) */
  cols.forEach(col => col.sort((a, b) => (colorData[a]?.l || 0) - (colorData[b]?.l || 0)));

  /* Place images */
  const frag = document.createDocumentFragment();
  cols.forEach((col, ci) => {
    col.forEach((slug, ri) => {
      const m = DATA.memes[slug];
      if (!m || !m.imageFilename) return;

      const div = document.createElement('div');
      div.className = 'mv-img';
      div.style.cssText = `width:${THUMB}px;height:${THUMB}px;left:${ci * CELL}px;top:${ri * CELL}px`;
      div.title = (m.title || slug).replace(/_/g, ' ');

      const img = document.createElement('img');
      img.src = m.imageURL || `images_flat/${m.imageFilename}`;
      img.alt = slug;
      img.loading = 'lazy';
      div.appendChild(img);

      div.addEventListener('click', () => openDetail(slug));
      div.addEventListener('mouseenter', e => {
        const c = colorData[slug] || {};
        showTip(`<b>${(m.title || slug).replace(/_/g,' ')}</b><br>sat: ${(c.s||0).toFixed(1)}  light: ${(c.l||0).toFixed(1)}<br><small>click to open</small>`, e);
      });
      div.addEventListener('mousemove', moveTip);
      div.addEventListener('mouseleave', hideTip);

      frag.appendChild(div);
    });
  });
  wrap.appendChild(frag);
}

/* ═══════════════════════════════════════════════════════════════════════════
   MANOVICH B — Chronological Strip
   Thumbs arranged in columns by year, stacked vertically within each year.
   Horizontally scrollable.
   ═══════════════════════════════════════════════════════════════════════════ */
let _chronoBuilt = false;

function buildChronoStrip() {
  if (_chronoBuilt) return;
  const wrap = document.getElementById('wrap-chrono');
  if (!wrap || !DATA) return;
  _chronoBuilt = true;

  const THUMB = 26;
  const GAP   = 1;
  const CELL  = THUMB + GAP;

  /* Group slugs by year */
  const byYear = {};
  Object.keys(DATA.memes).forEach(slug => {
    const m = DATA.memes[slug];
    if (!m || !m.imageFilename) return;
    const yr = parseInt(m.year, 10);
    if (!yr || yr < 1995 || yr > 2026) return;
    if (!byYear[yr]) byYear[yr] = [];
    byYear[yr].push(slug);
  });

  const years = Object.keys(byYear).map(Number).sort((a, b) => a - b);
  const maxCount = Math.max(...years.map(y => byYear[y].length));
  const ROWS = Math.min(maxCount, 80); // cap row count so it stays readable
  const H    = ROWS * CELL + 32;      // 32 for year label at bottom

  wrap.style.height = H + 'px';
  wrap.style.position = 'relative';
  wrap.style.whiteSpace = 'nowrap';
  wrap.innerHTML = '';

  let xCursor = 32; // left padding

  const frag = document.createDocumentFragment();

  years.forEach(yr => {
    const slugsForYear = byYear[yr];
    const cols = Math.ceil(slugsForYear.length / ROWS);

    /* Year label */
    const lbl = document.createElement('div');
    lbl.className = 'chrono-label';
    const lblW = cols * CELL;
    lbl.style.cssText = `left:${xCursor}px;bottom:4px;width:${lblW}px;text-align:center`;
    lbl.textContent = yr;
    frag.appendChild(lbl);

    /* Thumbnails: fill columns top-down, then next column */
    slugsForYear.forEach((slug, idx) => {
      const m = DATA.memes[slug];
      if (!m || !m.imageFilename) return;

      const col = Math.floor(idx / ROWS);
      const row = idx % ROWS;

      const div = document.createElement('div');
      div.className = 'mv-img';
      div.style.cssText = `width:${THUMB}px;height:${THUMB}px;left:${xCursor + col * CELL}px;top:${row * CELL}px`;
      div.title = (m.title || slug).replace(/_/g, ' ');

      const img = document.createElement('img');
      img.src = m.imageURL || `images_flat/${m.imageFilename}`;
      img.alt = slug;
      img.loading = 'lazy';
      div.appendChild(img);

      div.addEventListener('click', () => openDetail(slug));
      div.addEventListener('mouseenter', e => showTip(`<b>${(m.title || slug).replace(/_/g,' ')}</b><br>${yr}<br><small>click to open</small>`, e));
      div.addEventListener('mousemove', moveTip);
      div.addEventListener('mouseleave', hideTip);

      frag.appendChild(div);
    });

    xCursor += cols * CELL + 8; // 8px gap between years
  });

  /* Set canvas width so the scroll container knows the real extent */
  const canvas = document.createElement('div');
  canvas.style.cssText = `position:relative;width:${xCursor}px;height:${H}px;display:inline-block`;
  canvas.appendChild(frag);
  wrap.appendChild(canvas);
}

/* ═══════════════════════════════════════════════════════════════════════════
   MANOVICH C — Power-Law Montage
   Top 200 most-viewed = large thumb, next 500 = medium, rest = tiny.
   Packed left-to-right in rows by tier, demonstrating preferential attachment.
   ═══════════════════════════════════════════════════════════════════════════ */
let _powerlawBuilt = false;

function buildPowerLawMontage() {
  if (_powerlawBuilt) return;
  const wrap = document.getElementById('wrap-powerlaw');
  if (!wrap || !DATA) return;
  _powerlawBuilt = true;

  /* Sort all slugs by views descending, unknowns last */
  const slugs = Object.keys(DATA.memes)
    .filter(s => DATA.memes[s]?.imageFilename)
    .sort((a, b) => {
      const va = DATA.memes[a].popularityViews ?? -1;
      const vb = DATA.memes[b].popularityViews ?? -1;
      return vb - va;
    });

  /* Tier definitions */
  const TIERS = [
    { label: 'TOP 200',  count: 200,  size: 56,  badge: '' },
    { label: 'NEXT 500', count: 500,  size: 22,  badge: '' },
    { label: 'REST',     count: Infinity, size: 9, badge: '' },
  ];

  const wrapW = wrap.getBoundingClientRect().width || (window.innerWidth - 164);
  let yOffset  = 0;
  let tierIdx  = 0;
  let remaining = slugs.length;
  let slugIdx   = 0;

  const frag = document.createDocumentFragment();

  TIERS.forEach(tier => {
    const take  = Math.min(tier.count, remaining);
    if (take <= 0) return;

    const sz    = tier.size;
    const GAP   = sz <= 18 ? 1 : 2;
    const CELL  = sz + GAP;

    /* Section header label */
    const hdr = document.createElement('div');
    hdr.style.cssText = `position:absolute;left:0;top:${yOffset}px;padding:4px 12px;font-size:9px;font-weight:700;letter-spacing:.15em;color:rgba(255,255,255,.35);pointer-events:none`;
    hdr.textContent = tier.label;
    frag.appendChild(hdr);
    yOffset += 18;

    /* Pack rows */
    const cols = Math.floor(wrapW / CELL);
    const rows = Math.ceil(take / cols);

    for (let i = 0; i < take; i++) {
      const slug = slugs[slugIdx++];
      const m    = DATA.memes[slug];
      if (!m || !m.imageFilename) continue;

      const col = i % cols;
      const row = Math.floor(i / cols);

      const div = document.createElement('div');
      div.className = 'mv-img';
      div.style.cssText = `width:${sz}px;height:${sz}px;left:${col * CELL}px;top:${yOffset + row * CELL}px`;

      const img = document.createElement('img');
      img.src = m.imageURL || `images_flat/${m.imageFilename}`;
      img.alt = slug;
      img.loading = 'lazy';
      div.appendChild(img);

      if (sz >= 22) {
        div.addEventListener('mouseenter', e => {
          const views = m.popularityViews != null ? m.popularityViews.toLocaleString() + ' views' : 'views unknown';
          showTip(`<b>${(m.title || slug).replace(/_/g,' ')}</b><br>${views}<br><small>click to open</small>`, e);
        });
        div.addEventListener('mousemove', moveTip);
        div.addEventListener('mouseleave', hideTip);
      }
      div.addEventListener('click', () => openDetail(slug));

      frag.appendChild(div);
    }

    yOffset += rows * CELL + 16;
    remaining -= take;
  });

  const canvas = document.createElement('div');
  canvas.style.cssText = `position:relative;width:100%;height:${yOffset}px`;
  canvas.appendChild(frag);
  wrap.style.height = yOffset + 'px';
  wrap.appendChild(canvas);
}

/* ═══════════════════════════════════════════════════════════════════════════
   Build all graphs
   ═══════════════════════════════════════════════════════════════════════════ */
function buildGraphs() {
  buildTimeline();
  buildPopularityByFormat();
  buildPlatformTimeStacked();
}

/* ── Node panel ────────────────────────────────────────────────────────────── */
function openPanel(nodeId, slugs, graphKey, group) {
  panelSlugs = slugs;
  panelShown = 0;

  document.getElementById('panel-label').textContent = graphKey + (group ? ' · ' + group : '');
  document.getElementById('panel-title').textContent = nodeId;
  document.getElementById('panel-count').textContent =
    `${slugs.length} meme${slugs.length !== 1 ? 's' : ''}`;

  const grid = document.getElementById('meme-grid');
  grid.innerHTML = '';
  appendThumbnails(grid, slugs, 0, PAGE_SIZE);
  panelShown = Math.min(PAGE_SIZE, slugs.length);

  document.getElementById('panel-more').classList.toggle('hidden', slugs.length <= PAGE_SIZE);
  document.getElementById('node-panel').classList.remove('hidden');
  document.getElementById('app').classList.add('panel-open');
}

function appendThumbnails(grid, slugs, from, count) {
  slugs.slice(from, from + count).forEach(slug => {
    const meme = DATA.memes[slug];
    if (!meme) return;

    const card = document.createElement('div');
    card.className = 'meme-thumb';

    const img     = document.createElement('img');
    img.src       = meme.imageURL || `images_flat/${meme.imageFilename}`;
    img.alt       = slug;
    img.loading   = 'lazy';

    const imgWrap = document.createElement('div');
    imgWrap.className = 'meme-thumb-img';
    imgWrap.appendChild(img);

    const name       = document.createElement('div');
    name.className   = 'meme-thumb-name';
    name.textContent = slug.replace(/_/g, ' ');

    card.appendChild(imgWrap);
    card.appendChild(name);
    card.addEventListener('click', () => openDetail(slug));
    grid.appendChild(card);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('panel-close').addEventListener('click', () => {
    document.getElementById('node-panel').classList.add('hidden');
    document.getElementById('app').classList.remove('panel-open');
  });

  document.getElementById('btn-show-more').addEventListener('click', () => {
    const grid = document.getElementById('meme-grid');
    appendThumbnails(grid, panelSlugs, panelShown, PAGE_SIZE);
    panelShown = Math.min(panelShown + PAGE_SIZE, panelSlugs.length);
    if (panelShown >= panelSlugs.length)
      document.getElementById('panel-more').classList.add('hidden');
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.getElementById('node-panel').classList.add('hidden');
      document.getElementById('app').classList.remove('panel-open');
    }
  });
});

/* ── Meme detail page (routed) ─────────────────────────────────────────────── */
function openDetail(slug) {
  location.hash = '#meme/' + encodeURIComponent(slug);
}

function showMemePage(slug) {
  const m = DATA?.memes[slug];
  if (!m) { showViz(); return; }

  const title = (m.title && m.title !== slug) ? m.title : slug.replace(/_/g, ' ');
  const fmts  = (m.hasFormat || []).filter(f => f && f !== 'Unknown').join(', ') || '—';

  document.getElementById('meme-page-content').innerHTML = `
    <button class="meme-page-back" onclick="history.back()">&#8592; Back</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        <img src="${m.imageURL || `images_flat/${escHtml(m.imageFilename)}`}" alt="${escHtml(title)}"/>
        ${m.memeUrl ? `<a href="${escHtml(m.memeUrl)}" target="_blank" rel="noopener">Open on Know Your Meme ↗</a>` : ''}
      </div>
      <div class="meme-page-info">
        <h1>${escHtml(title)}</h1>
        <div class="meme-page-id">id: ${String(m.id).padStart(4,'0')} · ${escHtml(m.imageFilename)}</div>

        <div class="detail-section">
          <div class="detail-section-title">Visual Analysis — CLIP</div>
          ${row('hasImageType',          m.hasImageType,     'accent')}
          ${row('clipImageTypeScore',    fmt2(m.clipImageTypeScore), 'score')}
          ${row('hasSubjectMatter',      m.hasSubjectMatter, 'accent')}
          ${row('hasTextPresence',       m.hasTextPresence)}
          ${row('clipTextScore',         fmt2(m.clipTextScore), 'score')}
          ${row('hasColorMode',          m.hasColorMode)}
          ${row('clipPublicFigureScore', fmt2(m.clipPublicFigureScore), 'score')}
          ${m.ocrSnippet ? row('ocrSnippet', `"${escHtml(m.ocrSnippet)}"`) : ''}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Origin &amp; Distribution</div>
          ${row('hasOriginPlatform', m.hasOriginPlatform, 'accent')}
          ${row('hasOriginWork',     m.hasOriginWork)}
          ${row('hasRegion',         m.hasRegion)}
          ${row('hasTimePeriod',     m.hasTimePeriod)}
          ${row('yearOfOrigin',      m.year)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Meme Format</div>
          ${row('hasFormat', fmts)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">File &amp; FRBR</div>
          ${row('hasFileFormat',      m.hasFileFormat)}
          ${row('hasAnimationStatus', m.hasAnimationStatus)}
          ${row('hasFRBRLevel',       'Manifestation')}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Tags</div>
          <div style="padding-top:4px">
            ${(m.tags || []).map(t => `<span class="tag-pill">#${escHtml(t)}</span>`).join('')
              || '<span style="color:var(--muted);font-size:.8rem">no tags</span>'}
          </div>
        </div>
      </div>
    </div>
  `;

  showPage('meme');
}

function row(key, val, cls = '') {
  if (val == null || val === '' || val === 'Unknown') return '';
  return `<div class="detail-row">
    <span class="detail-key">${key}</span>
    <span class="detail-val ${cls}">${escHtml(String(val))}</span>
  </div>`;
}

function fmt2(v) { return v != null ? Number(v).toFixed(4) : null; }

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── About page ────────────────────────────────────────────────────────────── */
function buildAboutPage() {
  const memeCount = Object.keys(DATA.memes).length;
  document.getElementById('about-content').innerHTML = `
    <h1>The Meme Ontology</h1>
    <p class="page-sub">A structured knowledge base of internet memes, combining large-scale image classification with semantic ontology design.</p>

    <div class="about-section">
      <h2>At a Glance</h2>
      <div class="about-stats">
        <div class="stat-card"><span class="stat-num">${memeCount.toLocaleString()}</span><span class="stat-label">Memes</span></div>
        <div class="stat-card"><span class="stat-num">OWL</span><span class="stat-label">Ontology format</span></div>
        <div class="stat-card"><span class="stat-num">CLIP</span><span class="stat-label">Image classifier</span></div>
        <div class="stat-card"><span class="stat-num">KYM</span><span class="stat-label">Data source</span></div>
      </div>
    </div>

    <div class="about-section">
      <h2>Project</h2>
      <p>The Meme Ontology is a research project that applies formal knowledge representation to internet culture. Each meme in the dataset is represented as an OWL individual with properties covering its visual content, cultural context, origin, and format classification.</p>
      <p>The dataset is sourced from <a href="https://knowyourmeme.com" target="_blank" rel="noopener" style="color:var(--accent2)">Know Your Meme</a>, enriched with automated CLIP-based image classification and structured using a custom OWL ontology with classes for image type, subject matter, meme format, origin platform, geographic region, and temporal period.</p>
    </div>

    <div class="about-section">
      <h2>Pipeline</h2>
      <div class="about-pipeline">
        <div class="pipeline-step">
          <div class="pipeline-num">01</div>
          <div class="pipeline-label">Data Collection</div>
          <div class="pipeline-desc">Metadata and images scraped from Know Your Meme via the public API and image archives.</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-num">02</div>
          <div class="pipeline-label">CLIP Classification</div>
          <div class="pipeline-desc">Each image is classified across six ontology dimensions using OpenAI CLIP zero-shot inference.</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-num">03</div>
          <div class="pipeline-label">OWL Generation</div>
          <div class="pipeline-desc">Classifications are serialised into an OWL/RDF ontology using rdflib and a custom vocabulary.</div>
        </div>
        <div class="pipeline-step">
          <div class="pipeline-num">04</div>
          <div class="pipeline-label">Visualisation</div>
          <div class="pipeline-desc">Interactive D3.js visualisations expose co-occurrence patterns across tags, formats, and platforms.</div>
        </div>
      </div>
    </div>

    <div class="about-section">
      <h2>Ontology Structure</h2>
      <p>The ontology uses the MEME namespace and defines properties including <code style="font-family:monospace;color:var(--accent2)">hasImageType</code>, <code style="font-family:monospace;color:var(--accent2)">hasSubjectMatter</code>, <code style="font-family:monospace;color:var(--accent2)">hasFormat</code>, <code style="font-family:monospace;color:var(--accent2)">hasOriginPlatform</code>, <code style="font-family:monospace;color:var(--accent2)">hasRegion</code>, and <code style="font-family:monospace;color:var(--accent2)">hasTimePeriod</code>. FRBR levels (Work → Expression → Manifestation → Item) are used to model the abstraction hierarchy of meme instances.</p>
    </div>
  `;
}

/* ── Dataset page ──────────────────────────────────────────────────────────── */
function buildDatasetPage() {
  const slugs = Object.keys(DATA.memes);

  /* Populate filter dropdowns */
  const fmtSet  = new Set(), platSet = new Set();
  slugs.forEach(s => {
    const m = DATA.memes[s];
    (m.hasFormat || []).forEach(f => { if (f && f !== 'Unknown') fmtSet.add(f); });
    if (m.hasOriginPlatform && m.hasOriginPlatform !== 'Unknown') platSet.add(m.hasOriginPlatform);
  });

  const fmtSel  = document.getElementById('ds-filter-fmt');
  const platSel = document.getElementById('ds-filter-plat');
  [...fmtSet].sort().forEach(f => {
    const o = document.createElement('option'); o.value = f; o.textContent = f; fmtSel.appendChild(o);
  });
  [...platSet].sort().forEach(p => {
    const o = document.createElement('option'); o.value = p; o.textContent = p; platSel.appendChild(o);
  });

  function refilter() {
    const q    = document.getElementById('ds-search').value.toLowerCase().trim();
    const fmt  = fmtSel.value;
    const plat = platSel.value;
    dsFiltered = slugs.filter(s => {
      const m = DATA.memes[s];
      if (q   && !s.toLowerCase().includes(q) && !(m.title||'').toLowerCase().includes(q)) return false;
      if (fmt  && !(m.hasFormat||[]).includes(fmt))   return false;
      if (plat && m.hasOriginPlatform !== plat)        return false;
      return true;
    });
    dsPage = 0;
    renderDsPage();
  }

  document.getElementById('ds-search').addEventListener('input',  refilter);
  fmtSel.addEventListener('change', refilter);
  platSel.addEventListener('change', refilter);

  dsFiltered = slugs;
  renderDsPage();
}

function renderDsPage() {
  const total  = dsFiltered.length;
  const pages  = Math.ceil(total / DS_PER_PAGE);
  const start  = dsPage * DS_PER_PAGE;
  const slice  = dsFiltered.slice(start, start + DS_PER_PAGE);

  document.getElementById('ds-count').textContent =
    `${total.toLocaleString()} meme${total !== 1 ? 's' : ''}`;

  const grid = document.getElementById('ds-grid');
  grid.innerHTML = slice.map(slug => {
    const m = DATA.memes[slug];
    const label = (m.title && m.title !== slug) ? m.title : slug.replace(/_/g,' ');
    return `<a class="ds-card" href="#meme/${encodeURIComponent(slug)}">
      <div class="ds-card-img"><img src="${m.imageURL || `images_flat/${escHtml(m.imageFilename)}`}" alt="${escHtml(label)}" loading="lazy"/></div>
      <span class="ds-card-name">${escHtml(label)}</span>
    </a>`;
  }).join('');

  /* Pagination */
  const pag = document.getElementById('ds-pagination');
  if (pages <= 1) { pag.innerHTML = ''; return; }

  const nearPages = new Set([0, pages-1, dsPage, dsPage-1, dsPage+1, dsPage-2, dsPage+2]
    .filter(p => p >= 0 && p < pages));
  let pagHtml = `<button class="ds-page-btn" onclick="dsNav(${dsPage-1})" ${dsPage===0?'disabled':''}>&#8592;</button>`;
  let prev = -1;
  [...nearPages].sort((a,b)=>a-b).forEach(p => {
    if (prev !== -1 && p - prev > 1) pagHtml += `<span class="ds-page-info">…</span>`;
    pagHtml += `<button class="ds-page-btn${p===dsPage?' cur':''}" onclick="dsNav(${p})">${p+1}</button>`;
    prev = p;
  });
  pagHtml += `<button class="ds-page-btn" onclick="dsNav(${dsPage+1})" ${dsPage===pages-1?'disabled':''}>&#8594;</button>`;
  pag.innerHTML = pagHtml;
}

function dsNav(p) {
  dsPage = p;
  renderDsPage();
  document.getElementById('page-dataset').scrollTop = 0;
}

/* ── Dot nav + scroll tracking ─────────────────────────────────────────────── */
function buildNav() {
  const dots = [...document.querySelectorAll('.dot')];
  const obs = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (en.isIntersecting && en.intersectionRatio > .4) {
        dots.forEach(d => d.classList.remove('active'));
        document.querySelector(`.dot[href="#${en.target.id}"]`)?.classList.add('active');
      }
    });
  }, { threshold: .4 });

  document.querySelectorAll('.viz-section').forEach(s => obs.observe(s));
  dots.forEach(dot => dot.addEventListener('click', e => {
    e.preventDefault();
    document.querySelector(dot.getAttribute('href'))?.scrollIntoView({ behavior: 'smooth' });
  }));

  /* Lazy-build Manovich visualizations when their section enters viewport */
  const lazyObs = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      const id = en.target.id;
      if (id === 'sec-imageplot') buildImagePlot();
      if (id === 'sec-chrono')    buildChronoStrip();
      if (id === 'sec-powerlaw')  buildPowerLawMontage();
    });
  }, { rootMargin: '200px', threshold: 0 });

  ['sec-imageplot', 'sec-chrono', 'sec-powerlaw'].forEach(id => {
    const el = document.getElementById(id);
    if (el) lazyObs.observe(el);
  });
}
