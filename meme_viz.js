/* ── State ─────────────────────────────────────────────────────────────────── */
let DATA        = null;
let D0_DATA     = null;
let VARIANTS_DATA = null;
let TRANSFORM_MAP = {};   /* photoId  → transformation annotation */
let CULTURAL_MAP  = {};   /* slug     → cultural reference annotation */
let panelSlugs  = [];
let panelShown  = 0;
let dsPage      = 0;
let dsFiltered  = [];
let dsBuilt     = false;
let dsVariantMode = 'annotated';
const PAGE_SIZE = 30;
const DS_PER_PAGE = 60;

function slugToName(slug) {
  return String(slug || '').split('-').map(function(w) {
    return w.charAt(0).toUpperCase() + w.slice(1);
  }).join(' ');
}

function hasBlockedKeyword(text) {
  return /\bnft\b/i.test(String(text || ''));
}

function isBlockedAnnotation(a) {
  if (!a) return false;
  return hasBlockedKeyword(a.variantTitle) ||
         hasBlockedKeyword(a.captionText);
}

function isBlockedVariantMeta(v) {
  if (!v) return false;
  return hasBlockedKeyword(v.title) ||
         hasBlockedKeyword(v.img_alt);
}

/* ── Boot ──────────────────────────────────────────────────────────────────── */
function fetchJson(path) {
  return fetch(path).then(function(r) {
    if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + path);
    return r.json();
  });
}

function fetchJsonWithFallback(paths) {
  var i = 0;
  function tryNext() {
    if (i >= paths.length) {
      throw new Error('All paths failed: ' + paths.join(', '));
    }
    var path = paths[i++];
    return fetchJson(path).catch(function() {
      return tryNext();
    });
  }
  return tryNext();
}

Promise.all([
  fetchJson('meme_data.json'),
  fetchJson('sampled_dataset.json').catch(function() { return []; }),
  fetchJson('variants_metadata.json').catch(function() { return []; }),
  fetchJson('transformation_annotations.json').catch(function() { return []; }),
  fetchJsonWithFallback([
    'cultural_reference_annotations.json',
    'cultural_reference_annotations(1).json',
    'cultural_reference_annotations%281%29.json'
  ]).catch(function() { return []; })
])
  .then(function(result) {
    var memeData = result[0];
    var d0Data = result[1];
    var variantsData = result[2];
    var transformAnnots = result[3];
    var culturalAnnots = result[4];

    DATA          = memeData;
    D0_DATA       = d0Data;
    VARIANTS_DATA = variantsData;

    TRANSFORM_MAP = {};
    transformAnnots.forEach(function(a) {
      if (isBlockedAnnotation(a)) return;
      TRANSFORM_MAP[a.photoId] = a;
    });

    CULTURAL_MAP = {};
    culturalAnnots.forEach(function(a) {
      CULTURAL_MAP[a.slug] = a;
    });

    document.getElementById('loader').classList.add('done');
    buildTooltip();
    buildHero();
    buildGraphs();
    buildNav();
    route();
    startLiveReload();
  })
  .catch(function() {
    document.querySelector('.loader-text').textContent =
      'Critical dataset missing (meme_data.json).';
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
  } else if (hash.startsWith('d0/')) {
    showD0Page(decodeURIComponent(hash.slice(3)));
  } else if (hash.startsWith('variant/')) {
    showVariantPage(decodeURIComponent(hash.slice(8)));
  } else if (hash === 'about') {
    showPage('about');
    if (!document.getElementById('about-content').hasChildNodes()) buildAboutPage();
  } else if (hash === 'dataset') {
    showPage('dataset');
    if (!dsBuilt) buildDatasetPage();
  } else if (hash === 'ontology') {
    showPage('ontology');
    initOntoPage();
  } else {
    showViz();
  }
}
window.addEventListener('hashchange', route);

function showPage(name, navPage) {
  document.getElementById('app').classList.add('hidden');
  document.getElementById('dot-nav').classList.add('hidden');
  document.getElementById('node-panel').classList.add('hidden');
  document.getElementById('app').classList.remove('panel-open');
  ['about', 'dataset', 'ontology', 'meme', 'd0', 'variant'].forEach(p =>
    document.getElementById('page-' + p).classList.add('hidden'));
  document.getElementById('page-' + name).classList.remove('hidden');
  setActiveNav(navPage || name);
}

/* ── Ontology page: WebVOWL + local docs ─────────────────────────────────── */
var ontoInited = false;
function normalizeHttpUrl(raw) {
  var s = (raw || '').trim();
  if (!s) return '';
  if (/^https?:\/\//i.test(s)) return s;
  if (/^[\w.-]+\.[a-z]{2,}(\/.*)?$/i.test(s)) return 'https://' + s;
  return s;
}

function updateLiveLodeLink(owlUrl) {
  var lodeA = document.getElementById('onto-lode-live-link');
  var vowlA = document.getElementById('onto-vowl-live-link');
  var lodeUrl = 'https://w3id.org/lode/';
  var vowlUrl = 'https://service.tib.eu/webvowl/';

  if (!owlUrl) {
    if (lodeA) lodeA.href = lodeUrl;
    if (vowlA) vowlA.href = vowlUrl;
    return;
  }

  // Current LODE service endpoint pattern documented at https://essepuntato.it/lode/
  lodeUrl = 'https://w3id.org/lode/owlapi/' + owlUrl;
  vowlUrl = 'https://service.tib.eu/webvowl/#file=' + encodeURIComponent(owlUrl);

  if (lodeA) lodeA.href = lodeUrl;
  if (vowlA) vowlA.href = vowlUrl;
}

function initOntoPage() {
  if (ontoInited) return;
  ontoInited = true;

  var host = window.location.hostname;
  var isLocal = !host || host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local');

  // Pre-fill the URL input
  var input = document.getElementById('onto-url-input');
  var status = document.getElementById('onto-vowl-status');

  if (!isLocal) {
    // On deployed domains we prefill URL, but we do not auto-open a popup.
    // Auto-open is often blocked by the browser if not user-triggered.
    var owlUrl = window.location.origin + '/ontology';
    input.value = owlUrl;
    updateLiveLodeLink(owlUrl);

    if (status) {
      var vowlUrl = 'https://service.tib.eu/webvowl/#file=' + encodeURIComponent(owlUrl);
      status.style.display = 'block';
      status.innerHTML = 'Ready to open WebVOWL. Click <b>Load</b> or <a href="' + vowlUrl + '" target="_blank" rel="noopener">open directly</a>.';
    }
  } else {
    updateLiveLodeLink('');
  }
  // On localhost: show the hint overlay, leave input empty for user to fill
}

function loadWebVOWL() {
  var url = normalizeHttpUrl(document.getElementById('onto-url-input').value || '');
  if (!url) return;
  document.getElementById('onto-url-input').value = url;
  updateLiveLodeLink(url);
  _loadWebVOWLUrl(url);
}

function _loadWebVOWLUrl(owlUrl) {
  var vowlUrl = 'https://service.tib.eu/webvowl/#file=' + encodeURIComponent(owlUrl);
  var status = document.getElementById('onto-vowl-status');
  var hint  = document.getElementById('onto-vowl-hint');
  var frame = document.getElementById('webvowl-frame');

  if (hint)  { hint.style.display  = 'none'; }
  if (frame) { frame.style.display = 'none'; frame.src = 'about:blank'; }

  var popup = window.open(vowlUrl, '_blank', 'noopener');
  var opened = !!popup;

  if (status) {
    status.style.display = 'block';
    if (opened) {
      status.innerHTML = 'Opened WebVOWL in a new tab. If needed, <a href="' + vowlUrl + '" target="_blank" rel="noopener">open again</a>.';
    } else {
      status.innerHTML = 'Popup blocked by browser. Please <a href="' + vowlUrl + '" target="_blank" rel="noopener">click here to open WebVOWL</a>.';
    }
  }
}

function switchOntoTab(tab) {
  document.getElementById('onto-pane-vowl').classList.toggle('hidden', tab !== 'vowl');
  document.getElementById('onto-pane-lode').classList.toggle('hidden', tab !== 'lode');
  document.getElementById('onto-tab-vowl').classList.toggle('active', tab === 'vowl');
  document.getElementById('onto-tab-lode').classList.toggle('active', tab === 'lode');
  var urlRow = document.getElementById('onto-url-row');
  if (urlRow) urlRow.style.display = tab === 'vowl' ? '' : 'none';
}

function showViz() {
  ['about', 'dataset', 'ontology', 'meme', 'd0', 'variant'].forEach(p =>
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

function memeLocalSrc(meme) {
  if (!meme || !meme.imageFilename) return '';
  return 'images_flat/' + String(meme.imageFilename);
}

function memeRemoteSrc(meme) {
  return (meme && meme.imageURL) ? String(meme.imageURL) : '';
}

function setMemeImageWithFallback(img, meme) {
  var local = memeLocalSrc(meme);
  var remote = memeRemoteSrc(meme);
  img.src = remote || local || '';
  if (local && remote) {
    img.addEventListener('error', function() {
      if (img.dataset.fallbackTried) return;
      img.dataset.fallbackTried = '1';
      img.src = local;
    });
  }
}

function memeImgTag(meme, altText) {
  var local = escHtml(memeLocalSrc(meme));
  var remote = escHtml(memeRemoteSrc(meme));
  var src = remote || local;
  var onerr = (local && remote)
    ? ' onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried=\'1\';this.src=\'' + local + '\';}"'
    : '';
  return '<img src="' + src + '" alt="' + escHtml(altText || '') + '" loading="lazy"' + onerr + '/>';
}

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
    setMemeImageWithFallback(img, meme);
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
      if (!platforms.includes(s.platform))
        platforms.push(s.platform);
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

  const color = d3.scaleOrdinal()
    .domain(platforms)
    .range(d3.schemeTableau10.concat(d3.schemeSet3));

  const stack = d3.stack().keys(platforms);
  const stacked = stack(rows);

  const yMax = d3.max(stacked[stacked.length - 1] || [[0, 1]], d => d[1]) || 1;
  const y = d3.scaleLinear().domain([0, yMax]).range([iH, 0]);

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
      let slugs = comboToMemes[key] || [];
      if (!slugs.length && DATA && DATA.memes) {
        const PERIOD_MAP = {
          'Pre2010':      'Pre2010',
          '2010-2015':    'Period2010to2015',
          '2016-2020':    'Period2016to2020',
          '2021-present': 'Period2021toPresent'
        };
        const storedPeriod = PERIOD_MAP[d.data.period] || d.data.period;
        const namedPlatforms = new Set(platforms.filter(p => p !== 'Other'));
        slugs = Object.keys(DATA.memes).filter(slug => {
          const m = DATA.memes[slug];
          if (m.hasTimePeriod !== storedPeriod) return false;
          if (d.key === 'Other') return !m.hasOriginPlatform || !namedPlatforms.has(m.hasOriginPlatform);
          return m.hasOriginPlatform === d.key;
        });
      }
      openPanel(`${d.data.period} · ${d.key}`, slugs, 'platformTime', 'segment');
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
   Build all graphs
   ═══════════════════════════════════════════════════════════════════════════ */
function buildGraphs() {
  buildTimeline();
  buildPopularityByFormat();
  buildPlatformTimeStacked();
  buildVariantGallery();
  buildVariantBubble();
}

/* ── Variant Gallery (Viz B) ─────────────────────────────────────────────── */
function buildVariantGallery() {
  var wrap = document.getElementById('graph-variant-gallery');
  if (!wrap || !Object.keys(TRANSFORM_MAP).length || !VARIANTS_DATA) return;

  var EXTENT_ORDER = ['Minimal', 'Moderate', 'Substantial', 'Parody'];
  var EXTENT_COLOR = { Minimal: '#4caf50', Moderate: '#ff9800', Substantial: '#f44336', Parody: '#9c27b0' };
  var CANON_COLOR  = { Photograph: '#4a9eff', Drawing: '#f5a623', Cartoon: '#7ed321' };

  function toSlug(name) {
    return String(name || '').toLowerCase()
      .replace(/\u2019/g, '').replace(/'/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  }

  // Build lookup: photo_id → variant entry
  var varByPhotoId = {};
  VARIANTS_DATA.forEach(function(v) { varByPhotoId[String(v.photo_id)] = v; });

  // Group annotations by meme name
  var memeGroups = {};
  Object.values(TRANSFORM_MAP).forEach(function(a) {
    if (isBlockedAnnotation(a)) return;
    if (!memeGroups[a.memeName]) {
      memeGroups[a.memeName] = { canonical: a.canonicalImageType, variants: [] };
    }
    memeGroups[a.memeName].variants.push(a);
  });

  // Sort each meme's variants by transformation extent
  Object.values(memeGroups).forEach(function(g) {
    g.variants.sort(function(a, b) {
      return EXTENT_ORDER.indexOf(a.transformationExtent) - EXTENT_ORDER.indexOf(b.transformationExtent);
    });
  });

  var html = '<div class="vg-container">';

  // Legend
  html += '<div class="vg-legend">';
  html += '<span class="vg-legend-title">Transformation extent:</span>';
  EXTENT_ORDER.forEach(function(ext) {
    html += '<span class="vg-legend-item"><span class="vg-legend-dot" style="background:' + EXTENT_COLOR[ext] + '"></span>' + ext + '</span>';
  });
  html += '</div>';

  // One row per meme
  Object.keys(memeGroups).forEach(function(memeName) {
    var g = memeGroups[memeName];
    var seenVariant = {};
    var uniqueVariants = [];
    g.variants.forEach(function(a) {
      var normCaption = String(a.captionText || '').toLowerCase().replace(/\s+/g, ' ').trim();
      var key = normCaption || String(a.imageURL || '') || String(a.photoId || '');
      if (seenVariant[key]) return;
      seenVariant[key] = true;
      uniqueVariants.push(a);
    });

    var slug = ((uniqueVariants[0] && uniqueVariants[0].memeConceptIRI) || '').split('#')[1] || toSlug(memeName);
    var d0Entry = (D0_DATA || []).find(function(entry) {
      return ((entry.meme_url || '').split('/').pop() || '') === slug;
    });
    var originalType = (d0Entry && d0Entry.hasImageType) ? String(d0Entry.hasImageType) : String(g.canonical || 'Unknown');
    var canonColor = CANON_COLOR[originalType] || CANON_COLOR[g.canonical] || '#888';
    var originalHref = d0Entry ? ('#d0/' + encodeURIComponent(String(d0Entry.id))) : ('#meme/' + encodeURIComponent(slug));

    html += '<div class="vg-row">';
    html += '<div class="vg-label">';
    html += '<span class="vg-meme-name">' + escHtml(memeName) + '</span>';
    html += '<span class="vg-canon-badge" style="color:' + canonColor + '">Original: ' + escHtml(originalType) + '</span>';
    html += '</div>';
    html += '<div class="vg-thumbs">';

    // Add original/template image first, next to the variants.
    var originalMeme = DATA && DATA.memes ? DATA.memes[slug] : null;
    var originalImg = originalMeme ? (memeRemoteSrc(originalMeme) || memeLocalSrc(originalMeme)) : '';
    html += '<a class="vg-thumb vg-thumb-original" href="' + escHtml(originalHref) + '" title="Original template · ' + escHtml(originalType) + '">';
    if (originalImg) {
      html += '<img src="' + escHtml(originalImg) + '" alt="' + escHtml(memeName + ' original') + '" loading="lazy" style="border:2px solid ' + canonColor + '">';
    } else {
      html += '<div class="vg-thumb-missing">?</div>';
    }
    html += '<span class="vg-ext-label" style="color:' + canonColor + '">ORIGINAL</span>';
    html += '</a>';

    uniqueVariants.forEach(function(a) {
      var v = varByPhotoId[String(a.photoId)];
      var localImg = (v && v.folder && v.filename)
        ? 'sampled_variants/' + v.folder + '/' + v.filename
        : '';
      var remoteImg = (a && a.imageURL) ? String(a.imageURL) : ((v && v.image_url) ? String(v.image_url) : '');
      var img = remoteImg || localImg;
      var extColor = EXTENT_COLOR[a.transformationExtent] || '#888';
      var variantType = String(a.variantImageType || 'Unknown');
      var dims = Array.isArray(a.transformationDimension)
        ? a.transformationDimension.join(', ')
        : String(a.transformationDimension || '');
      var tipText = 'Variant: ' + variantType + ' · ' + a.transformationExtent + (dims ? ' · ' + dims : '');

      html += '<a class="vg-thumb" href="#variant/' + encodeURIComponent(String(a.photoId)) + '" title="' + escHtml(tipText) + '">';
      if (img) {
        html += '<img src="' + escHtml(img) + '" alt="' + escHtml((a.variantTitle || (v && v.title) || '')) + '" loading="lazy" style="border:2px solid ' + extColor + '"';
        if (remoteImg && localImg) {
          html += ' onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried=\'1\';this.src=\'' + escHtml(localImg) + '\';}"';
        }
        html += '>';
      } else {
        html += '<div class="vg-thumb-missing">?</div>';
      }
      html += '<span class="vg-ext-label" style="color:' + extColor + '">' + escHtml(a.transformationExtent) + '</span>';
      html += '</a>';
    });

    html += '</div></div>';
  });

  html += '</div>';
  wrap.innerHTML = html;
}

/* ── Bubble Chart (Viz C) ─────────────────────────────────────────────────── */
function buildVariantBubble() {
  var wrap = document.getElementById('graph-variant-bubble');
  if (!wrap || !DATA || !D0_DATA) return;

  // One data point per sampled dataset entry (all 50)
  var points = D0_DATA.map(function(d0) {
    var slug = (d0.meme_url || '').split('/').pop();
    var name = slug ? slugToName(slug) : (d0.title || slug || '');
    return {
      id:     d0.id,
      name:   name,
      photos: d0.photos || 0,
      views:  d0.views  || 0,
      imgSrc: d0.image_url || d0.image_path || ''
    };
  });

  if (!points.length) {
    wrap.innerHTML = '<p style="padding:24px;color:var(--muted)">No data available.</p>';
    return;
  }

  // Render largest images first so smaller ones appear on top
  points.sort(function(a, b) { return b.views - a.views; });

  var W = wrap.getBoundingClientRect().width || 900;
  var H = 500;
  var M = { top: 24, right: 40, bottom: 60, left: 82 };
  var w = W - M.left - M.right;
  var h = H - M.top - M.bottom;

  wrap.innerHTML = '';

  var svg = d3.select(wrap).append('svg').attr('width', W).attr('height', H);

  // Clip images to chart bounds
  svg.append('defs').append('clipPath').attr('id', 'bubble-clip')
    .append('rect').attr('width', w).attr('height', h);

  var g = svg.append('g').attr('transform', 'translate(' + M.left + ',' + M.top + ')');

  // Image size proportional to views (popularity)
  var sScale = d3.scaleSqrt()
    .domain([0, d3.max(points, function(p) { return p.views; }) || 1])
    .range([12, 60]);

  // Pad scale ranges by half the max image size so no image is clipped at the edges
  var PAD = 32;

  // X = Number of Views (linear scale)
  var xScale = d3.scaleLinear()
    .domain([d3.min(points, function(p) { return Math.max(1, p.views); }),
             d3.max(points, function(p) { return p.views; })])
    .range([PAD, w - PAD]).nice();

  // Y = Creative Productivity (photos), log scale; photos=0 → y=1
  var yScale = d3.scaleLog()
    .domain([1, d3.max(points, function(p) { return Math.max(1, p.photos); })])
    .range([h - PAD, PAD]).nice();

  // Gridlines
  g.append('g')
    .call(d3.axisLeft(yScale).ticks(5, '.0s').tickSize(-w).tickFormat(''))
    .call(function(sel) {
      sel.selectAll('line').attr('stroke', 'rgba(0,0,0,.07)').attr('stroke-width', 0.6);
      sel.select('.domain').remove();
    });
  g.append('g').attr('transform', 'translate(0,' + h + ')')
    .call(d3.axisBottom(xScale).ticks(6, '.0s').tickSize(-h).tickFormat(''))
    .call(function(sel) {
      sel.selectAll('line').attr('stroke', 'rgba(0,0,0,.07)').attr('stroke-width', 0.6);
      sel.select('.domain').remove();
    });

  // Axes
  g.append('g').call(d3.axisLeft(yScale).ticks(5, '.0s')).attr('color', '#888');
  g.append('g').attr('transform', 'translate(0,' + h + ')')
    .call(d3.axisBottom(xScale).ticks(6, '.0s')).attr('color', '#888');

  // Axis labels
  g.append('text').attr('x', w / 2).attr('y', h + 48)
    .attr('text-anchor', 'middle').attr('fill', '#888').attr('font-size', 11)
    .text('Number of Views');
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -(h / 2)).attr('y', -62)
    .attr('text-anchor', 'middle').attr('fill', '#888').attr('font-size', 11)
    .text('Number of Variants');

  // Meme images — all 50 entries, sized by views
  g.append('g').attr('clip-path', 'url(#bubble-clip)')
    .selectAll('image').data(points).join('image')
      .attr('x', function(p) { var s = sScale(p.views); return xScale(Math.max(1, p.views)) - s / 2; })
      .attr('y', function(p) { var s = sScale(p.views); return yScale(Math.max(1, p.photos)) - s / 2; })
      .attr('width',  function(p) { return sScale(p.views); })
      .attr('height', function(p) { return sScale(p.views); })
      .attr('href', function(p) { return p.imgSrc; })
      .attr('preserveAspectRatio', 'xMidYMid slice')
      .style('cursor', 'pointer')
      .on('mouseover', function(evt, p) {
        showTip('<strong>' + escHtml(p.name) + '</strong><br/>' +
          p.views.toLocaleString() + ' views · ' + p.photos.toLocaleString() + ' photos', evt);
      })
      .on('mousemove', moveTip)
      .on('mouseout', hideTip)
      .on('click', function(evt, p) {
        if (p.id != null) location.hash = '#d0/' + encodeURIComponent(String(p.id));
      });
}

/* ── MediumShift Matrix (Viz D) ──────────────────────────────────────────── */
function buildMediumShiftMatrix() {
  var wrap = document.getElementById('graph-mediumshift');
  if (!wrap || !Object.keys(TRANSFORM_MAP).length || !VARIANTS_DATA) return;

  var EXTENT_ORDER = ['Minimal', 'Moderate', 'Substantial', 'Parody'];
  var CANON_COLOR  = { Photograph: '#4a9eff', Drawing: '#f5a623', Cartoon: '#7ed321' };
  var TYPE_ORDER   = ['Photograph', 'Drawing', 'Cartoon'];

  // Build lookup: photo_id → variant entry
  var varByPhotoId = {};
  VARIANTS_DATA.forEach(function(v) { varByPhotoId[String(v.photo_id)] = v; });

  // Group annotations by meme
  var memeGroups = {};
  Object.values(TRANSFORM_MAP).forEach(function(a) {
    if (isBlockedAnnotation(a)) return;
    if (!memeGroups[a.memeName]) {
      memeGroups[a.memeName] = { canonical: a.canonicalImageType, variants: [] };
    }
    memeGroups[a.memeName].variants.push(a);
  });

  // Sort memes by canonical image type, then sort each meme's variants by extent
  var memeNames = Object.keys(memeGroups).sort(function(a, b) {
    return TYPE_ORDER.indexOf(memeGroups[a].canonical) - TYPE_ORDER.indexOf(memeGroups[b].canonical);
  });
  memeNames.forEach(function(name) {
    memeGroups[name].variants.sort(function(a, b) {
      return EXTENT_ORDER.indexOf(a.transformationExtent) - EXTENT_ORDER.indexOf(b.transformationExtent);
    });
  });

  var html = '<div class="ms-matrix">';

  // Header row showing extent direction
  html += '<div class="ms-header-row">';
  html += '<div class="ms-row-label"></div>';
  html += '<div class="ms-header-cells"><span class="ms-header-dir">\u2190 Minimal \u00b7\u00b7\u00b7 Parody \u2192</span></div>';
  html += '</div>';

  memeNames.forEach(function(memeName) {
    var g = memeGroups[memeName];
    var canonColor = CANON_COLOR[g.canonical] || '#888';
    var shiftCount = g.variants.filter(function(a) { return a.variantImageType !== g.canonical; }).length;

    html += '<div class="ms-row">';
    html += '<div class="ms-row-label">';
    html += '<span class="ms-meme-name">' + escHtml(memeName) + '</span>';
    html += '<span class="ms-canon-badge" style="background:' + canonColor + '22;color:' + canonColor + ';border:1px solid ' + canonColor + '55">' + escHtml(g.canonical) + '</span>';
    if (shiftCount > 0) {
      html += '<span class="ms-shift-count">' + shiftCount + ' \u2260</span>';
    }
    html += '</div>';
    html += '<div class="ms-cells">';

    g.variants.forEach(function(a) {
      var v = varByPhotoId[String(a.photoId)];
      var localImg = (v && v.folder && v.filename)
        ? 'sampled_variants/' + v.folder + '/' + v.filename
        : '';
      var remoteImg = (v && v.image_url) ? String(v.image_url) : '';
      var img = remoteImg || localImg;
      var isShift = a.variantImageType !== g.canonical;
      var varColor = CANON_COLOR[a.variantImageType] || '#888';
      var borderStyle = isShift
        ? '3px solid ' + varColor
        : '2px solid rgba(255,255,255,.12)';
      var tipText = a.transformationExtent + ' \u00b7 ' + a.variantImageType + (isShift ? ' \u2190 MEDIUM SHIFT' : '');

      html += '<div class="ms-cell ' + (isShift ? 'ms-shift' : 'ms-match') + '" title="' + escHtml(tipText) + '">';
      if (img) {
        html += '<img src="' + escHtml(img) + '" alt="" loading="lazy" style="border:' + borderStyle + '"';
        if (remoteImg && localImg) {
          html += ' onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried=\'1\';this.src=\'' + escHtml(localImg) + '\';}"';
        }
        html += '>';
      } else {
        html += '<div class="ms-cell-missing" style="border:' + borderStyle + '">?</div>';
      }
      if (isShift) {
        html += '<span class="ms-shift-badge" style="color:' + varColor + '">\u2260</span>';
      }
      html += '<span class="ms-ext-label">' + escHtml(a.transformationExtent.slice(0, 3).toUpperCase()) + '</span>';
      html += '</div>';
    });

    html += '</div></div>';
  });

  html += '</div>';
  wrap.innerHTML = html;
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
    setMemeImageWithFallback(img, meme);
    img.alt       = slug;
    img.loading   = 'lazy';

    const imgWrap = document.createElement('div');
    imgWrap.className = 'meme-thumb-img';
    imgWrap.appendChild(img);

    const name       = document.createElement('div');
    name.className   = 'meme-thumb-name';
    name.textContent = slugToName(slug);

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

  const title = slugToName(slug);
  const fmts  = (m.hasFormat || []).filter(f => f && f !== 'Unknown').join(', ') || '—';

  document.getElementById('meme-page-content').innerHTML = `
    <button class="meme-page-back" onclick="history.back()">&#8592; Back</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        ${memeImgTag(m, title)}
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

/* ── D0 detail page ────────────────────────────────────────────────────────── */
function showD0Page(id) {
  if (!D0_DATA) { location.hash = '#dataset'; return; }
  const m = D0_DATA.find(x => String(x.id) === String(id));
  if (!m) { location.hash = '#dataset'; return; }

  const slug    = (m.meme_url || '').split('/').pop() || '';
  const title   = slug ? slugToName(slug) : String(m.id);
  const fmts    = (m.hasFormat && m.hasFormat.length)
    ? m.hasFormat.join(', ')
    : (m.type || []).join(', ') || '—';
  const views   = m.views   != null ? Number(m.views).toLocaleString()   : null;
  const videos  = m.videos  != null ? Number(m.videos).toLocaleString()  : null;
  const photos  = m.photos  != null ? Number(m.photos).toLocaleString()  : null;
  const comments = m.comments != null ? Number(m.comments).toLocaleString() : null;
  const crAnnot = CULTURAL_MAP[slug];
  const img     = m.image_url || m.image_path || '';

  document.getElementById('d0-page-content').innerHTML = `
    <button class="meme-page-back" onclick="history.back()">&#8592; Back to Datasets</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        <img src="${escHtml(img)}" alt="${escHtml(title)}"/>
        ${m.meme_url ? `<a href="${escHtml(m.meme_url)}" target="_blank" rel="noopener">Open on Know Your Meme ↗</a>` : ''}
        <div class="ds-detail-stats">
          ${views    ? `<div class="ds-stat-item"><span class="ds-stat-num">${views}</span><span class="ds-stat-lbl">views</span></div>` : ''}
          ${videos   ? `<div class="ds-stat-item"><span class="ds-stat-num">${videos}</span><span class="ds-stat-lbl">videos</span></div>` : ''}
          ${photos   ? `<div class="ds-stat-item"><span class="ds-stat-num">${photos}</span><span class="ds-stat-lbl">photos</span></div>` : ''}
          ${comments ? `<div class="ds-stat-item"><span class="ds-stat-num">${comments}</span><span class="ds-stat-lbl">comments</span></div>` : ''}
        </div>
      </div>
      <div class="meme-page-info">
        <h1>${escHtml(title)}</h1>
        <div class="meme-page-id">D0 Sample · id: ${String(m.id).padStart(4,'0')} · ${escHtml(m.image_filename || '')}</div>

        ${m.description ? `
        <div class="detail-section">
          <div class="detail-section-title">Description</div>
          <p style="font-size:.84rem;color:var(--text);line-height:1.65;margin:0">${escHtml(m.description)}</p>
        </div>` : ''}

        <div class="detail-section">
          <div class="detail-section-title">Visual Analysis — CLIP</div>
          ${row('hasImageType',          m.hasImageType,                  'accent')}
          ${row('clipImageTypeScore',    fmt2(m.clipImageTypeScore),       'score')}
          ${row('hasSubjectMatter',      m.hasSubjectMatter,              'accent')}
          ${row('hasTextPresence',       m.hasTextPresence)}
          ${row('clipTextScore',         fmt2(m.clipTextScore),            'score')}
          ${row('hasColorMode',          m.hasColorMode)}
          ${row('clipPublicFigureScore', fmt2(m.clipPublicFigureScore),    'score')}
          ${m.ocrSnippet ? row('ocrSnippet', '"' + m.ocrSnippet + '"') : ''}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Origin &amp; Distribution</div>
          ${row('hasOriginPlatform', m.hasOriginPlatform || m.origin, 'accent')}
          ${row('hasOriginWork',     m.hasOriginWork)}
          ${row('hasRegion',         m.hasRegion || m.region)}
          ${row('hasTimePeriod',     m.hasTimePeriod)}
          ${row('yearOfOrigin',      m.year)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Meme Format</div>
          ${row('hasFormat',          fmts)}
          ${row('hasFileFormat',      m.hasFileFormat)}
          ${row('hasAnimationStatus', m.hasAnimationStatus)}
          ${row('hasFRBRLevel',       'Manifestation')}
        </div>

        ${crAnnot && crAnnot.references && crAnnot.references.length ? `
        <div class="detail-section">
          <div class="detail-section-title">Cultural References</div>
          ${crAnnot.references.map(ref =>
            `<div class="detail-row">
               <span class="detail-key">${escHtml(ref.class || '')}</span>
               <span class="detail-val accent">${escHtml(ref.label || ref.individual || '')}</span>
             </div>`
          ).join('')}
        </div>` : ''}

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

  showPage('d0', 'dataset');
}

/* ── Variant detail page ────────────────────────────────────────────────────── */
function showVariantPage(photoId) {
  if (!VARIANTS_DATA) { location.hash = '#dataset'; return; }
  const v = VARIANTS_DATA.find(x => x.photo_id === photoId);
  if (!v) { location.hash = '#dataset'; return; }

  const annot    = TRANSFORM_MAP[photoId];
  const memeSlug = annot ? (annot.memeConceptIRI || '').split('#')[1] : '';
  const crAnnot  = memeSlug ? CULTURAL_MAP[memeSlug] : null;
  const title    = v.title || v.meme_name || '';
  const localImg = (v.folder && v.filename)
    ? `sampled_variants/${escHtml(v.folder)}/${escHtml(v.filename)}`
    : '';
  const remoteImg = escHtml(v.image_url || '');
  const img = remoteImg || localImg;
  const onError = (remoteImg && localImg)
    ? ` onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried='1';this.src='${localImg}';}"`
    : '';

  document.getElementById('variant-page-content').innerHTML = `
    <button class="meme-page-back" onclick="history.back()">&#8592; Back to Datasets</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        <img src="${img}" alt="${escHtml(title)}"${onError}/>
        ${v.photo_url ? `<a href="${escHtml(v.photo_url)}" target="_blank" rel="noopener">View on Know Your Meme ↗</a>` : ''}
      </div>
      <div class="meme-page-info">
        <h1>${escHtml(title)}</h1>
        <div class="meme-page-id">Variant · photo_id: ${escHtml(photoId)} · ${escHtml(v.meme_name || '')}</div>

        <div class="detail-section">
          <div class="detail-section-title">Variant Metadata</div>
          ${row('uploader',    v.author)}
          ${row('variantIndex', annot ? String(annot.variantIndex) : null)}
          ${v.img_alt ? row('caption / alt text', v.img_alt) : ''}
        </div>

        ${annot ? `
        <div class="detail-section">
          <div class="detail-section-title">Transformation Annotation</div>
          ${row('meme',                    annot.memeName,                'accent')}
          ${row('transformationDimension', annot.transformationDimension, 'accent')}
          ${row('transformationExtent',    annot.transformationExtent)}
          ${row('originalImageType',       annot.canonicalImageType)}
          ${row('variantImageType',        annot.variantImageType)}
          ${annot.captionText ? row('captionText', annot.captionText) : ''}
          ${annot.notes       ? row('notes',       annot.notes)       : ''}
        </div>` : ''}

        ${crAnnot && crAnnot.references && crAnnot.references.length ? `
        <div class="detail-section">
          <div class="detail-section-title">Cultural References (parent meme)</div>
          ${crAnnot.references.map(ref =>
            `<div class="detail-row">
               <span class="detail-key">${escHtml(ref.class || '')}</span>
               <span class="detail-val accent">${escHtml(ref.label || ref.individual || '')}</span>
             </div>`
          ).join('')}
        </div>` : ''}
      </div>
    </div>
  `;

  showPage('variant', 'dataset');
}

/* ── Dataset scroll helper ──────────────────────────────────────────────────── */
function dsScrollTo(sectionId) {
  const section = document.getElementById(sectionId);
  if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  dsBuilt = true;
  buildGlobalSection();
  buildD0Section();
  buildVariantsSection('annotated');
}

function buildGlobalSection() {
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
      if (q   && !s.toLowerCase().includes(q) && !slugToName(s).toLowerCase().includes(q)) return false;
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

function buildD0Section() {
  if (!D0_DATA) return;
  const grid = document.getElementById('ds-d0-grid');
  grid.innerHTML = D0_DATA.map(m => {
    const slug    = (m.meme_url || '').split('/').pop() || '';
    const label   = slug ? slugToName(slug) : String(m.id);
    const fmtList = Array.isArray(m.hasFormat) ? m.hasFormat : (Array.isArray(m.type) ? m.type : []);
    const fmt     = fmtList.slice(0, 2).join(', ');
    const views   = m.views ? Number(m.views).toLocaleString() : null;
    const desc    = m.description ? m.description.slice(0, 100) + (m.description.length > 100 ? '…' : '') : '';
    const remoteImg = m.image_url  ? escHtml(m.image_url)  : '';
    const localImg  = m.image_path ? escHtml(m.image_path) : '';
    const imgSrc    = remoteImg || localImg;
    const onerr     = (remoteImg && localImg)
      ? ` onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried='1';this.src='${localImg}';}"` : '';
    const href    = `#d0/${encodeURIComponent(String(m.id))}`;
    return `<a class="ds-card ds-d0-card" href="${href}">
      <div class="ds-card-img"><img src="${imgSrc}" alt="${escHtml(label)}" loading="lazy"${onerr}/></div>
      <span class="ds-card-name">${escHtml(label)}</span>
      ${fmt   ? `<span class="ds-d0-meta">${escHtml(fmt)}</span>` : ''}
      ${views ? `<span class="ds-d0-meta ds-d0-views">&#128065; ${views}</span>` : ''}
      ${desc  ? `<span class="ds-d0-desc">${escHtml(desc)}</span>` : ''}
    </a>`;
  }).join('');
}

function buildVariantsSection(mode) {
  dsVariantMode = mode;
  document.querySelectorAll('.ds-vtoggle').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.v === mode);
  });

  const grid = document.getElementById('ds-variants-grid');
  if (!VARIANTS_DATA) {
    grid.innerHTML = '<p style="color:var(--muted);padding:16px 0">Variants data not loaded.</p>';
    return;
  }

  const items = (mode === 'annotated')
    ? VARIANTS_DATA.filter(v => TRANSFORM_MAP[v.photo_id] && !isBlockedVariantMeta(v) && !isBlockedAnnotation(TRANSFORM_MAP[v.photo_id]))
    : VARIANTS_DATA.filter(v => !isBlockedVariantMeta(v));

  grid.innerHTML = items.map(v => {
    const annot  = TRANSFORM_MAP[v.photo_id];
    const localImg = (v.folder && v.filename)
      ? `sampled_variants/${escHtml(v.folder)}/${escHtml(v.filename)}`
      : '';
    const remoteImg = escHtml(v.image_url || '');
    const img = remoteImg || localImg;
    const onError = (remoteImg && localImg)
      ? ` onerror="if(!this.dataset.fallbackTried){this.dataset.fallbackTried='1';this.src='${localImg}';}"`
      : '';
    const dim    = annot ? annot.transformationDimension : null;
    const ext    = annot ? annot.transformationExtent   : null;
    const title  = v.title || v.meme_name || '';
    return `<a class="ds-card ds-var-card" href="#variant/${encodeURIComponent(v.photo_id)}">
      <div class="ds-card-img"><img src="${img}" alt="${escHtml(title)}" loading="lazy"${onError}/></div>
      <span class="ds-card-name">${escHtml(title)}</span>
      <span class="ds-d0-meta">${escHtml(v.meme_name || '')}</span>
      ${dim ? `<span class="ds-d0-meta ds-d0-annot">${escHtml(dim)}${ext ? ' · ' + escHtml(ext) : ''}</span>` : ''}
    </a>`;
  }).join('');
}

function showVariants(mode) {
  buildVariantsSection(mode);
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
    const label = slugToName(slug);
    return `<a class="ds-card" href="#meme/${encodeURIComponent(slug)}">
      <div class="ds-card-img">${memeImgTag(m, label)}</div>
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
}
