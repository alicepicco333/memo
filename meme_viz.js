/* ── Constants ─────────────────────────────────────────────────────────────── */
// Platforms that post-date 2009 — used to suppress impossible Pre2010 data artifacts.
const MODERN_PLATFORMS = new Set(['TikTok', 'Instagram', 'Snapchat', 'Twitch', 'Discord']);
// Platforms that post-date 2015 — suppress from Pre2010 and 2010-2015 bars (TikTok launched Sep 2016).
const POST2015_PLATFORMS = new Set(['TikTok']);
const LODE_TARGET_BASE = 'http://150.146.207.114/lode/extract';
const RAW_OWL_URL = 'https://raw.githubusercontent.com/alicepicco333/memo/refs/heads/main/meme_ontology_unpopulated.owl';
const RAW_OWL_URL_CANONICAL = 'https://raw.githubusercontent.com/alicepicco333/memo/main/meme_ontology_unpopulated.owl';

/* ── State ─────────────────────────────────────────────────────────────────── */
let isMobile = () => window.innerWidth <= 768;
let isSmallMobile = () => window.innerWidth <= 480;
let DATA        = null;
let D0_DATA     = null;
let VARIANTS_DATA = null;
let TRANSFORM_MAP = {};   /* photoId  → transformation annotation */
let CULTURAL_MAP  = {};   /* slug     → cultural reference annotation */
let prevVizHash   = 'sec-variant-gallery'; /* last viz section before entering a detail page */
let panelSlugs  = [];
let panelShown  = 0;
let dsPage      = 0;
let dsFiltered  = [];
let dsBuilt     = false;
let dsVariantMode = 'annotated';
const PAGE_SIZE = 30;
const DS_PER_PAGE = 60;

function slugToName(slug) {
  // some slugs keep the URL encoding of their title ("super-idol-%E7%9A%84..."): decode it, and leave
  // out emoji, so names read as words
  var s = String(slug || '');
  try { s = decodeURIComponent(s); } catch (e) { /* not encoded: keep as is */ }
  s = s.replace(/[\p{Extended_Pictographic}‍️]/gu, '');
  return s.split('-').filter(Boolean).map(function(w) {
    return w.charAt(0).toUpperCase() + w.slice(1);
  }).join(' ');
}

/* Platform names as people write them; the data keeps its own values (TwitterX) for filters and queries. */
const PLATFORM_LABEL = { TwitterX: 'Twitter/X' };
function platformLabel(p) { return PLATFORM_LABEL[p] || p; }

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
  // the file in the repo is "cultural_reference_annotations(1).json": ask for that name first (no 404)
  fetchJsonWithFallback([
    'cultural_reference_annotations(1).json',
    'cultural_reference_annotations%281%29.json',
    'cultural_reference_annotations.json'
  ]).catch(function() { return []; }),
  // the charts measure their labels to fit them, so they draw with the page's fonts in place
  document.fonts ? document.fonts.ready.catch(function() {}) : null
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

/* ── Responsive chart redraw on resize ──────────────────────────────────── */
// The charts take their size from their box when they draw, so a new width redraws them
// (height-only changes are ignored: on phones the URL bar resizes the window while scrolling).
let resizeTimeout;
let lastChartWidth = window.innerWidth;
window.addEventListener('resize', function() {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(function() {
    syncScrollBoxes();
    if (!DATA || Math.abs(window.innerWidth - lastChartWidth) < 40) return;
    lastChartWidth = window.innerWidth;
    if (document.getElementById('app').classList.contains('hidden')) { chartsStale = true; return; }
    buildTimeline();
    buildPopularityByFormat();
    buildPlatformTimeStacked();
    buildVariantBubble();
  }, 250);
});

/* The three sideways boxes (.viz-hscroll) only scroll on phones, where their charts draw at 640 px:
   only there are they a tab stop and a labelled region. */
function syncScrollBoxes() {
  const phone = isMobile();
  document.querySelectorAll('.viz-hscroll').forEach(box => {
    if (phone) {
      box.tabIndex = 0;
      box.setAttribute('role', 'region');
      box.setAttribute('aria-label', 'Chart, scrolls sideways');
    } else {
      box.removeAttribute('tabindex');
      box.removeAttribute('role');
      box.removeAttribute('aria-label');
    }
  });
}
document.addEventListener('DOMContentLoaded', syncScrollBoxes);

/* ── Live reload (polls while scraper runs) ──────────────────────────────── */
let _lastDataSize = 0;
function startLiveReload() {
  if (!/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) return;
  setInterval(() => {
    fetch('meme_data.json', { cache: 'no-store' })
      .then(r => {
        const size = parseInt(r.headers.get('content-length') || '0', 10);
        return r.json().then(d => ({ d, size }));
      })
      .then(({ d, size }) => {
        if (!size || size === _lastDataSize) return;
        const first = _lastDataSize === 0;
        _lastDataSize = size;
        if (first) return;
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
  } else if (hash === 'disclaimer') {
    showPage('disclaimer');
    if (!document.getElementById('disclaimer-content').hasChildNodes()) buildDisclaimerPage();
  } else if (hash === 'dataset') {
    showPage('dataset');
    if (!dsBuilt) buildDatasetPage();
  } else if (hash === 'ontology') {
    showPage('ontology');
    initOntoPage();
  } else {
    showViz();
    // a section link from the top bar (#sec-flow): charts building on the way can move the section,
    // so finish the trip the way the contents links do
    const section = hash && document.getElementById(hash);
    if (section && section.classList.contains('viz-section')) scrollToSection(section, 3);
  }
}
window.addEventListener('hashchange', function(e) {
  const oldHash = (e.oldURL || '').split('#')[1] || '';
  const isDetailPage = oldHash.startsWith('variant/') || oldHash.startsWith('d0/') || oldHash.startsWith('meme/');
  if (!isDetailPage && oldHash) prevVizHash = oldHash;
  route();
});

function showPage(name, navPage) {
  var app = document.getElementById('app');
  var dotNav = document.getElementById('dot-nav');
  var nodePanel = document.getElementById('node-panel');
  if (app) {
    app.classList.add('hidden');
    app.classList.remove('panel-open');
  }
  if (dotNav) dotNav.classList.add('hidden');
  if (nodePanel) nodePanel.classList.add('hidden');

  ['about', 'disclaimer', 'dataset', 'ontology', 'meme', 'd0', 'variant'].forEach(function(p) {
    var page = document.getElementById('page-' + p);
    if (page) page.classList.add('hidden');
  });

  var target = document.getElementById('page-' + name);
  if (target) target.classList.remove('hidden');
  setActiveNav(navPage || name);
}

/* ── Ontology page: in-page LODE-like documentation ─────────────────────── */
var ontoInited = false;
function xmlAttr(node, ns, name, fallbackName) {
  return node.getAttributeNS(ns, name) || node.getAttribute(fallbackName) || '';
}

function textByTag(node, ns, name) {
  var el = node.getElementsByTagNameNS(ns, name)[0];
  return el ? String(el.textContent || '').trim() : '';
}

function shortIri(iri) {
  if (!iri) return '';
  var prefixes = [
    ['http://www.semanticweb.org/meme-ontology#', 'memo:'],
    ['http://www.w3.org/2002/07/owl#', 'owl:'],
    ['http://www.w3.org/2000/01/rdf-schema#', 'rdfs:'],
    ['http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'rdf:'],
    ['http://www.w3.org/2001/XMLSchema#', 'xsd:'],
    ['http://purl.org/vocab/frbr/core#', 'frbrer:'],
    ['https://schema.org/', 'schema:'],
    ['http://www.wikidata.org/entity/', 'wd:']
  ];
  for (var i = 0; i < prefixes.length; i++) {
    var base = prefixes[i][0];
    if (iri.indexOf(base) === 0) return prefixes[i][1] + iri.slice(base.length);
  }
  return iri;
}

function safeEntityId(iri) {
  return 'onto-entity-' + String(iri || '').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function hasRdfType(node, rdfNs, typeIri) {
  var typeNodes = node.getElementsByTagNameNS(rdfNs, 'type');
  for (var i = 0; i < typeNodes.length; i++) {
    var t = xmlAttr(typeNodes[i], rdfNs, 'resource', 'rdf:resource');
    if (t === typeIri) return true;
  }
  return false;
}

function getTypedDescriptionNodes(doc, rdfNs, typeIri) {
  var descNodes = Array.prototype.slice.call(doc.getElementsByTagNameNS(rdfNs, 'Description'));
  return descNodes.filter(function(node) {
    return hasRdfType(node, rdfNs, typeIri);
  });
}

function collectOwlEntityNodes(doc, owlNs, rdfNs, elementName, typeIri) {
  var explicitNodes = Array.prototype.slice.call(doc.getElementsByTagNameNS(owlNs, elementName));
  var typedNodes = getTypedDescriptionNodes(doc, rdfNs, typeIri);
  var merged = [];
  var seen = {};

  explicitNodes.concat(typedNodes).forEach(function(node) {
    var iri = xmlAttr(node, rdfNs, 'about', 'rdf:about');
    var key = iri || ('_blank_' + merged.length);
    if (seen[key]) return;
    seen[key] = true;
    merged.push(node);
  });

  return merged;
}

function buildLodeTargetUrl() {
  var owlUrl = RAW_OWL_URL;
  return LODE_TARGET_BASE + '?url=' + encodeURIComponent(owlUrl) + '&owlapi=true&imported=true&closure=true&reasoner=true&lang=en';
}

function fetchOntologyXmlFromCandidates(candidates) {
  var i = 0;
  function tryNext() {
    if (i >= candidates.length) {
      throw new Error('Unable to load ontology from known paths');
    }
    var path = candidates[i++];
    return fetch(path, { cache: 'no-store' })
      .then(function(res) {
        if (!res.ok) throw new Error('HTTP ' + res.status + ' for ' + path);
        return res.text();
      })
      .then(function(xmlText) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(xmlText, 'application/xml');
        if (doc.getElementsByTagName('parsererror').length) {
          throw new Error('Cannot parse ontology XML from ' + path);
        }

        var OWL_NS = 'http://www.w3.org/2002/07/owl#';
        var RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';
        var hasOntology =
          doc.getElementsByTagNameNS(OWL_NS, 'Ontology').length > 0 ||
          getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'Ontology').length > 0;
        var hasSchemaEntities =
          doc.getElementsByTagNameNS(OWL_NS, 'Class').length > 0 ||
          doc.getElementsByTagNameNS(OWL_NS, 'ObjectProperty').length > 0 ||
          doc.getElementsByTagNameNS(OWL_NS, 'DatatypeProperty').length > 0 ||
          doc.getElementsByTagNameNS(OWL_NS, 'AnnotationProperty').length > 0 ||
          getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'Class').length > 0 ||
          getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'ObjectProperty').length > 0 ||
          getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'DatatypeProperty').length > 0 ||
          getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'AnnotationProperty').length > 0;

        if (!hasOntology && !hasSchemaEntities) {
          throw new Error('Response is not OWL ontology at ' + path);
        }
        return doc;
      })
      .catch(function() {
        return tryNext();
      });
  }
  return tryNext();
}

function toEntity(node, rdfNs, rdfsNs, kind) {
  var iri = xmlAttr(node, rdfNs, 'about', 'rdf:about');
  if (!iri) return null;
  var item = {
    iri: iri,
    label: textByTag(node, rdfsNs, 'label') || shortIri(iri).split(':').pop(),
    comment: textByTag(node, rdfsNs, 'comment') || '',
    kind: kind,
    superClasses: [],
    domains: [],
    ranges: [],
    types: []
  };

  var subNodes = node.getElementsByTagNameNS(rdfsNs, 'subClassOf');
  for (var i = 0; i < subNodes.length; i++) {
    var sup = xmlAttr(subNodes[i], rdfNs, 'resource', 'rdf:resource');
    if (sup) item.superClasses.push(sup);
  }

  var domainNodes = node.getElementsByTagNameNS(rdfsNs, 'domain');
  for (var j = 0; j < domainNodes.length; j++) {
    var d = xmlAttr(domainNodes[j], rdfNs, 'resource', 'rdf:resource');
    if (d) item.domains.push(d);
  }

  var rangeNodes = node.getElementsByTagNameNS(rdfsNs, 'range');
  for (var k = 0; k < rangeNodes.length; k++) {
    var r = xmlAttr(rangeNodes[k], rdfNs, 'resource', 'rdf:resource');
    if (r) item.ranges.push(r);
  }

  var typeNodes = node.getElementsByTagNameNS(rdfNs, 'type');
  for (var t = 0; t < typeNodes.length; t++) {
    var typeIri = xmlAttr(typeNodes[t], rdfNs, 'resource', 'rdf:resource');
    if (typeIri) item.types.push(typeIri);
  }

  return item;
}

function renderEntityList(title, items, typeLabel) {
  if (!items.length) {
    return '<section class="onto-doc-sec"><h2>' + escHtml(title) + '</h2><p class="onto-doc-empty">No entities found.</p></section>';
  }

  var html = '<section class="onto-doc-sec" id="' + escHtml(typeLabel) + '">';
  html += '<h2>' + escHtml(title) + ' <span>' + items.length + '</span></h2>';
  items.forEach(function(item) {
    html += '<article class="onto-entity-block" id="' + escHtml(safeEntityId(item.iri)) + '">';
    html += '<h3 class="onto-entity-title">' + escHtml(item.label) + '</h3>';
    html += '<div class="onto-entity-iri">' + escHtml(item.iri) + '</div>';
    if (item.comment) {
      html += '<p class="onto-entity-comment">' + escHtml(item.comment) + '</p>';
    }

    if (item.superClasses.length || item.domains.length || item.ranges.length || item.types.length) {
      html += '<table class="onto-entity-table"><tbody>';
      if (item.superClasses.length) {
        html += '<tr><th>Super-classes</th><td>' + escHtml(item.superClasses.map(shortIri).join(', ')) + '</td></tr>';
      }
      if (item.domains.length) {
        html += '<tr><th>Domain</th><td>' + escHtml(item.domains.map(shortIri).join(', ')) + '</td></tr>';
      }
      if (item.ranges.length) {
        html += '<tr><th>Range</th><td>' + escHtml(item.ranges.map(shortIri).join(', ')) + '</td></tr>';
      }
      if (item.types.length && typeLabel === 'onto-sec-individuals') {
        html += '<tr><th>Types</th><td>' + escHtml(item.types.map(shortIri).join(', ')) + '</td></tr>';
      }
      html += '</tbody></table>';
    }
    html += '</article>';
  });
  html += '</section>';
  return html;
}

function wireOntoNavScroll() {
  var buttons = document.querySelectorAll('.onto-doc-nav button[data-target]');
  buttons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var target = document.getElementById(btn.getAttribute('data-target'));
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

function initOntoPage() {
  if (ontoInited) return;
  ontoInited = true;

  var nav = document.getElementById('onto-doc-nav');
  var main = document.getElementById('onto-doc-main');
  var lodeTop = document.getElementById('onto-open-lode-top');
  var lodeBottom = document.getElementById('onto-open-lode-bottom');
  var lodeUrl = buildLodeTargetUrl();
  if (lodeTop) lodeTop.href = lodeUrl;
  if (lodeBottom) lodeBottom.href = lodeUrl;

  fetchOntologyXmlFromCandidates([
    'meme_ontology_unpopulated.owl',
    '/meme_ontology_unpopulated.owl',
    'meme_ontology.owl',
    '/meme_ontology.owl',
    '/ontology',
    RAW_OWL_URL_CANONICAL,
    RAW_OWL_URL
  ])
    .then(function(doc) {

      var RDF_NS = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';
      var RDFS_NS = 'http://www.w3.org/2000/01/rdf-schema#';
      var OWL_NS = 'http://www.w3.org/2002/07/owl#';

      var classes = collectOwlEntityNodes(doc, OWL_NS, RDF_NS, 'Class', OWL_NS + 'Class')
        .map(function(n) { return toEntity(n, RDF_NS, RDFS_NS, 'Class'); })
        .filter(Boolean)
        .sort(function(a, b) { return a.label.localeCompare(b.label); });

      var objectProps = collectOwlEntityNodes(doc, OWL_NS, RDF_NS, 'ObjectProperty', OWL_NS + 'ObjectProperty')
        .map(function(n) { return toEntity(n, RDF_NS, RDFS_NS, 'Object property'); })
        .filter(Boolean)
        .sort(function(a, b) { return a.label.localeCompare(b.label); });

      var datatypeProps = collectOwlEntityNodes(doc, OWL_NS, RDF_NS, 'DatatypeProperty', OWL_NS + 'DatatypeProperty')
        .map(function(n) { return toEntity(n, RDF_NS, RDFS_NS, 'Datatype property'); })
        .filter(Boolean)
        .sort(function(a, b) { return a.label.localeCompare(b.label); });

      var annotationProps = collectOwlEntityNodes(doc, OWL_NS, RDF_NS, 'AnnotationProperty', OWL_NS + 'AnnotationProperty')
        .map(function(n) { return toEntity(n, RDF_NS, RDFS_NS, 'Annotation property'); })
        .filter(Boolean)
        .sort(function(a, b) { return a.label.localeCompare(b.label); });

      var individuals = collectOwlEntityNodes(doc, OWL_NS, RDF_NS, 'NamedIndividual', OWL_NS + 'NamedIndividual')
        .map(function(n) { return toEntity(n, RDF_NS, RDFS_NS, 'Named individual'); })
        .filter(Boolean)
        .sort(function(a, b) { return a.label.localeCompare(b.label); });

      var ontologyNode =
        doc.getElementsByTagNameNS(OWL_NS, 'Ontology')[0] ||
        getTypedDescriptionNodes(doc, RDF_NS, OWL_NS + 'Ontology')[0];
      var ontologyIri = ontologyNode ? xmlAttr(ontologyNode, RDF_NS, 'about', 'rdf:about') : '';

      nav.innerHTML = '' +
        '<h3>Documentation</h3>' +
        '<button data-target="onto-sec-overview">Overview</button>' +
        '<button data-target="onto-sec-classes">Classes (' + classes.length + ')</button>' +
        '<button data-target="onto-sec-objprops">Object properties (' + objectProps.length + ')</button>' +
        '<button data-target="onto-sec-dataprops">Datatype properties (' + datatypeProps.length + ')</button>' +
        '<button data-target="onto-sec-annprops">Annotation properties (' + annotationProps.length + ')</button>' +
        '<button data-target="onto-sec-individuals">Named individuals (' + individuals.length + ')</button>';

      var html = '<section class="onto-doc-sec" id="onto-sec-overview">';
      html += '<h2>Ontology overview</h2>';
      if (ontologyIri) {
        html += '<p class="onto-overview-iri">Ontology IRI: ' + escHtml(ontologyIri) + '</p>';
      }
      html += '<div class="onto-stats-grid">';
      html += '<div class="onto-stat-card"><span>' + classes.length + '</span><label>Classes</label></div>';
      html += '<div class="onto-stat-card"><span>' + objectProps.length + '</span><label>Object properties</label></div>';
      html += '<div class="onto-stat-card"><span>' + datatypeProps.length + '</span><label>Datatype properties</label></div>';
      html += '<div class="onto-stat-card"><span>' + annotationProps.length + '</span><label>Annotation properties</label></div>';
      html += '<div class="onto-stat-card"><span>' + individuals.length + '</span><label>Named individuals</label></div>';
      html += '</div>';
      html += '</section>';

      html += renderEntityList('Classes', classes, 'onto-sec-classes');
      html += renderEntityList('Object properties', objectProps, 'onto-sec-objprops');
      html += renderEntityList('Datatype properties', datatypeProps, 'onto-sec-dataprops');
      html += renderEntityList('Annotation properties', annotationProps, 'onto-sec-annprops');
      html += renderEntityList('Named individuals', individuals, 'onto-sec-individuals');

      main.innerHTML = html;
      wireOntoNavScroll();
    })
    .catch(function(err) {
      main.innerHTML = '<div class="onto-doc-error">Unable to load ontology documentation here (' + escHtml(err.message) + '). Use Open in LODE.</div>';
      nav.innerHTML = '<h3>Documentation</h3><p class="onto-doc-empty">Navigation unavailable while data fails to load.</p>';
    });
}

function showViz() {
  ['about', 'disclaimer', 'dataset', 'ontology', 'meme', 'd0', 'variant'].forEach(function(p) {
    var page = document.getElementById('page-' + p);
    if (page) page.classList.add('hidden');
  });

  var app = document.getElementById('app');
  var dotNav = document.getElementById('dot-nav');
  var wasHidden = app && app.classList.contains('hidden');
  if (app) app.classList.remove('hidden');
  if (dotNav) dotNav.classList.remove('hidden');
  setActiveNav('viz');
  // charts drawn while another view was open had no box to measure: draw them again now
  if (wasHidden && chartsStale) {
    chartsStale = false;
    buildTimeline();
    buildPopularityByFormat();
    buildPlatformTimeStacked();
    buildVariantBubble();
  }
}

function setActiveNav(page) {
  document.querySelectorAll('.topnav-link').forEach(l => {
    const on = l.dataset.page === page;
    l.classList.toggle('active', on);
    if (on) l.setAttribute('aria-current', 'page'); else l.removeAttribute('aria-current');
  });
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

/* Run fn once, the first time el scrolls into view (entrance animations). */
function revealOnView(el, fn) {
  if (!el || !('IntersectionObserver' in window)) { fn(); return; }
  const obs = new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) { obs.disconnect(); fn(); }
  }, { threshold: 0.2 });
  obs.observe(el);
}

/* ── Chart text and layout ─────────────────────────────────────────────────── */
// Axis ticks 13 px, every other chart label at least 12 px; grey text in the site's muted ink
// (#67625a, 5.6:1 on paper) instead of #888 / #aaa / #bbb.
const TICK_PX = 13;
const LABEL_PX = 12;
const MUTED_INK = '#67625a';
// Transformation extent: the bright colours mark frames and rings, the darker ones are for text (4.6:1 and up).
const EXTENT_COLOR = { Minimal: '#4caf50', Moderate: '#ff9800', Substantial: '#f44336', Parody: '#9c27b0' };
const EXTENT_TEXT  = { Minimal: '#2e7d32', Moderate: '#b45309', Substantial: '#c62828', Parody: '#7b1fa2' };

/* How far the section title starts inside a chart's box, so the chart's first text can start on the
   same edge. 0 when the title sits beside the chart (the split sections) or above a box edge. */
function titleInset(wrap) {
  const section = wrap.closest('.viz-section');
  const h2 = section && section.querySelector('.sec-header h2');
  if (!h2) return 0;
  const d = h2.getBoundingClientRect().left - wrap.getBoundingClientRect().left;
  return d > 0 && d < 160 ? Math.round(d) : 0;
}

/* Width of the widest of `strings` set at `px` inside this svg (the chart's own font). */
function textWidth(svgEl, strings, px) {
  const t = d3.select(svgEl).append('text').style('font-size', px + 'px');
  let w = 0;
  strings.forEach(s => { t.text(String(s)); w = Math.max(w, t.node().getComputedTextLength()); });
  t.remove();
  return Math.ceil(w);
}

/* Slant for x labels under a band axis: none if they fit side by side, 40° if a slanted line still
   clears its neighbour, otherwise upright (90°). */
function labelSlant(step, labelW) {
  if (step >= labelW + 8) return 0;
  if (step * Math.sin(40 * Math.PI / 180) >= TICK_PX + 2) return 40;
  return 90;
}
function slantLabels(sel, deg) {
  sel.style('font-size', TICK_PX + 'px').style('fill', '#1a1a3a');
  if (deg === 90) {
    sel.attr('transform', 'rotate(-90)').attr('x', -9).attr('y', 0).attr('dy', '.35em').style('text-anchor', 'end');
  } else if (deg) {
    sel.attr('transform', `rotate(-${deg})`).attr('dx', '-.5em').attr('dy', '.2em').style('text-anchor', 'end');
  }
}
/* Room the labels need under the axis line (tick 6 + gap 3, then the slanted text). */
function slantDepth(labelW, deg) {
  const a = deg * Math.PI / 180;
  return Math.ceil(9 + labelW * Math.sin(a) + TICK_PX * Math.cos(a));
}

/* Platforms toggled off in the Platform × TimePeriod legend */
const hiddenPlatforms = new Set();

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
  const mobile = isMobile();

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);

  // Margins from the labels themselves: the axis title starts on the section title's edge, then the
  // ticks; under the axis only as much room as the format names need.
  const yMax = d3.max(points, d => d.avgViews || 0) || 1;
  const yFormat = d3.format('~s');   // 0, 20k, 140k: no trailing ".0"
  const yTickW = textWidth(svgEl, d3.scaleLinear().domain([0, yMax * 1.08]).ticks(6).map(yFormat), TICK_PX);
  const fmtW = textWidth(svgEl, points.map(d => d.format), TICK_PX);
  const inset = titleInset(wrap);
  const left = inset + LABEL_PX + 16 + yTickW + 9;
  const slant = labelSlant((W - left - 24) / points.length, fmtW);
  const margin = { top: 24, right: mobile ? 8 : 24, bottom: slantDepth(fmtW, slant) + 8, left };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top - margin.bottom;

  const x = d3.scaleBand()
    .domain(points.map(d => d.format))
    .range([0, iW])
    .padding(0.22);

  const y = d3.scaleLinear()
    .domain([0, yMax * 1.08])
    .range([iH, 0]);

  const maxEntries = d3.max(points, d => d.entries || 0) || 1;
  // rMax grows with chart width; bandwidth cap is removed — bubbles may overlap, which is fine.
  // range starts at 4 so the smallest formats are always a visible dot.
  const rMax = Math.min(28, Math.max(18, iW / 28));
  const r = d3.scaleSqrt()
    .domain([0, maxEntries])
    .range([4, rMax]);

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  g.append('g')
    .attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .call(slantLabels, slant);

  g.append('g')
    .call(d3.axisLeft(y).ticks(6).tickFormat(yFormat))
    .selectAll('text')
    .style('font-size', TICK_PX + 'px')
    .style('fill', '#1a1a3a');

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');

  g.append('text')
    .attr('x', -iH / 2)
    .attr('y', inset - margin.left)
    .attr('dy', '.71em')
    .attr('transform', 'rotate(-90)')
    .attr('text-anchor', 'middle')
    .attr('fill', '#444')
    .style('font-size', LABEL_PX + 'px')
    .text('Average views');

  const color = d3.scaleSequential(d3.interpolateYlOrRd)
    .domain([0, yMax]);

  g.selectAll('circle.pop')
    .data(points)
    .join('circle')
    .attr('class', 'pop')
    .attr('cx', d => x(d.format) + x.bandwidth() / 2)
    .attr('cy', iH)
    .attr('r', 0)
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
        '<br><small>Click to browse memes</small>',
        e
      );
    })
    .on('mousemove', moveTip)
    .on('mouseout', hideTip)
    .on('click', (e, d) => {
      openPanel(d.format, nodeToMemes[d.format] || [], 'popularity', 'format');
    })
    .call(sel => revealOnView(wrap, () => sel.transition()
      .delay((d, i) => i * 28).duration(650).ease(d3.easeCubicOut)
      .attr('cy', d => y(d.avgViews || 0))
      .attr('r', d => r(d.entries || 0))));

  // ── Size legend ──────────────────────────────────────────────────────────
  // Vertical stack in top-right: largest circle first, count labels to the left.
  const legendSteps = [200, 600, 1200].filter(v => v <= maxEntries * 1.05);
  if (!mobile && legendSteps.length) {
    const lg = g.append('g').attr('transform', `translate(${iW - 6}, 8)`);

    lg.append('text')
      .attr('x', 0).attr('y', 0)
      .attr('text-anchor', 'end')
      .style('font-size', LABEL_PX + 'px').style('fill', MUTED_INK).style('font-style', 'italic')
      .text('entries');

    let lyOff = 16;
    [...legendSteps].reverse().forEach(val => {
      const rad = r(val);
      lyOff += rad;
      // semi-transparent backing so circle shows over any stray data
      lg.append('circle')
        .attr('cx', -rad - 4).attr('cy', lyOff)
        .attr('r', rad + 2)
        .attr('fill', 'var(--surface)').attr('opacity', 0.75);
      lg.append('circle')
        .attr('cx', -rad - 4).attr('cy', lyOff)
        .attr('r', rad)
        .attr('fill', 'none').attr('stroke', '#8a8378').attr('stroke-width', 1.2);
      lg.append('text')
        .attr('x', -rad * 2 - 14).attr('y', lyOff + 4)
        .attr('text-anchor', 'end')
        .style('font-size', LABEL_PX + 'px').style('fill', MUTED_INK)
        .text(val >= 1000 ? (val / 1000) + 'k' : val);
      lyOff += rad + 8;
    });
  }
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
  const mobile = isMobile();

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);

  // The longest format name starts on the section title's edge; under the axis only the room the
  // slanted years need.
  const fmtW = textWidth(svgEl, fmts, TICK_PX);
  const yearW = textWidth(svgEl, years, TICK_PX);
  const margin = { top: 12, right: mobile ? 8 : 24, bottom: slantDepth(yearW, 45) + 8, left: titleInset(wrap) + fmtW + 9 };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top  - margin.bottom;
  // label every year if the slanted years clear each other, else every 2nd, 5th or 10th
  const yearStep = iW / Math.max(1, years.length);
  const every = [1, 2, 5, 10].find(n => n * yearStep * Math.SQRT1_2 >= TICK_PX + 3) || 10;

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

  const bubbleSel = g.selectAll('circle.bubble').data(bubbles).join('circle')
    .attr('class', 'bubble')
    .attr('cx', d => xScale(d.year) + xScale.bandwidth() / 2)
    .attr('cy', d => yScale(d.fmt)  + yScale.bandwidth() / 2)
    .attr('r',  0)
    .attr('fill', d => color(d.fmt))
    .attr('opacity', .82)
    .attr('stroke', 'white').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('mouseover', (e, d) =>
      showTip(`<b>${d.fmt}</b><br>${d.year}: <b>${d.count}</b> entries<br><small>Click to browse</small>`, e))
    .on('mousemove', moveTip).on('mouseout', hideTip)
    .on('click', (e, d) => {
      const fmtSlugs = nodeToMemes[d.fmt] || [];
      const yearSet  = new Set(nodeToMemes[String(d.year)] || []);
      const filtered = fmtSlugs.filter(s => yearSet.has(s));
      openPanel(`${d.fmt} in ${d.year}`, filtered.length ? filtered : fmtSlugs, 'time', d.fmt);
    });

  g.append('g').attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(xScale).tickFormat(d3.format('d'))
      .tickValues(years.filter(y => y % every === 0)))
    .selectAll('text')
    .attr('transform', 'rotate(-45)').style('text-anchor', 'end')
    .attr('dy', '.15em').attr('dx', '-.4em')
    .style('font-size', TICK_PX + 'px').style('fill', '#1a1a3a');

  function formatAxis(sel) {
    sel.call(d3.axisLeft(yScale))
      .selectAll('text').style('font-size', TICK_PX + 'px').style('fill', '#1a1a3a')
      .style('cursor', 'pointer')
      .on('mouseenter', (e, fmt) => bubbleSel.transition().duration(150).attr('opacity', d => d.fmt === fmt ? .95 : .08))
      .on('mouseleave', () => bubbleSel.transition().duration(150).attr('opacity', .82))
      .on('click', (e, fmt) => openPanel(fmt, nodeToMemes[fmt] || [], 'time', 'format'));
  }
  g.append('g').call(formatAxis);

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');

  // Phones: the chart scrolls sideways in its box. The format names stay in a column on the left (a
  // copy of the axis that sticks to the box's edge) and the box opens on the most recent years.
  const box = wrap.parentElement;
  const sideways = mobile && box.classList.contains('viz-hscroll');
  wrap.style.overflow = sideways ? 'visible' : '';   // the sticky column needs the box as its scroller
  if (sideways) {
    const colW = margin.left + 1, colH = H;
    const column = document.createElement('div');
    column.className = 'viz-hscroll-labels';
    column.setAttribute('aria-hidden', 'true');
    column.style.cssText = `position:sticky;left:0;z-index:1;width:${colW}px;height:${colH}px;margin-top:${-H}px;background:var(--bg)`;
    wrap.appendChild(column);
    d3.select(column).append('svg').attr('viewBox', `0 0 ${colW} ${colH}`)
      .append('g').attr('transform', `translate(${margin.left},${margin.top})`).call(formatAxis)
      .selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');
    box.scrollLeft = box.scrollWidth;
  }

  revealOnView(wrap, () => bubbleSel.transition()
    .delay(d => years.indexOf(d.year) * 22).duration(450).ease(d3.easeBackOut)
    .attr('r', d => rScale(d.count)));
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

  // Trova tutte le piattaforme presenti
  const platforms = [];
  periods.forEach(p => {
    (p.segments || []).forEach(s => {
      if (!platforms.includes(s.platform))
        platforms.push(s.platform);
    });
  });

  // Ordina le piattaforme in base alla somma delle proporzioni decrescenti (così la più presente è sempre in fondo)
  // Per ogni periodo, la piattaforma con la percentuale massima sarà in fondo
  // Calcola la somma delle proporzioni per ogni piattaforma
  const platformTotals = {};
  periods.forEach(periodRow => {
    (periodRow.segments || []).forEach(seg => {
      if (!platformTotals[seg.platform]) platformTotals[seg.platform] = 0;
      platformTotals[seg.platform] += seg.ratio || 0;
    });
  });
  // Ordina le piattaforme per somma decrescente
  const sortedPlatforms = [...platforms].sort((a, b) => (platformTotals[b] || 0) - (platformTotals[a] || 0));

  const rect = wrap.getBoundingClientRect();
  const W = rect.width || (window.innerWidth - 48);
  const H = rect.height || (window.innerHeight - 72);

  wrap.innerHTML = '';
  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  wrap.appendChild(svgEl);
  const svg = d3.select(svgEl);

  // The percentages start on the section title's edge (on the chart's own edge when the title sits
  // beside it); the legend on the right is as wide as its longest line.
  const legendNote = hiddenPlatforms.size
    ? ['Shares re-normalised.', 'Click to show or hide.']
    : ['Click a platform', 'to hide it.'];
  const legendW = Math.max(18 + textWidth(svgEl, platforms.map(platformLabel), TICK_PX), textWidth(svgEl, legendNote, LABEL_PX));
  const periodW = textWidth(svgEl, periods.map(p => p.period), TICK_PX);
  const left = titleInset(wrap) + textWidth(svgEl, ['100%'], TICK_PX) + 9;
  const right = legendW + 24;
  const slant = labelSlant((W - left - right) / periods.length * 0.78, periodW);
  const margin = { top: 16, right, bottom: slantDepth(periodW, slant) + 8, left };
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top - margin.bottom;

  const rows = periods.map(periodRow => {
    const row = { period: periodRow.period };
    sortedPlatforms.forEach(p => { row[p] = 0; });
    (periodRow.segments || []).forEach(seg => {
      if (periodRow.period === 'Pre2010' && MODERN_PLATFORMS.has(seg.platform)) return;
      if (periodRow.period === '2010-2015' && POST2015_PLATFORMS.has(seg.platform)) return;
      if (hiddenPlatforms.has(seg.platform)) return;
      row[seg.platform] = seg.ratio || 0;
    });
    if (hiddenPlatforms.size) {
      const sum = sortedPlatforms.reduce((acc, p) => acc + row[p], 0);
      if (sum > 0) sortedPlatforms.forEach(p => { row[p] /= sum; });
    }
    return row;
  });

  const x = d3.scaleBand()
    .domain(rows.map(d => d.period))
    .range([0, iW])
    .padding(0.22);

  const platformColorMap = {
    '4chan':     '#6b9a4b',  // medium green  — 4chan green
    'Facebook':  '#8aa5d6',  // cornflower    — Facebook blue
    'Instagram': '#9d4e8c',  // rose pink     — Instagram gradient
    'Reddit':    '#eda03a',  // warm orange   — Reddit orange
    'TikTok':    '#1f9e8f',  // teal          — TikTok cyan
    'Tumblr':    '#2c3a57',  // steel blue    — Tumblr navy
    'TwitterX':  '#2f5f98',  // sky blue      — Twitter classic
    'YouTube':   '#d1543a',  // coral red     — YouTube red
    'Other':     '#cbc3b3',  // neutral       — grey-blue
  };
  const color = platform =>
    platformColorMap[platform] || '#b0b8c8';


  // Stack manuale per ogni periodo: per ogni barra, ordina le piattaforme per percentuale decrescente
  // Costruisci dati per ogni periodo
  const stacked = {};
  let yMax = 0;
  rows.forEach((row, periodIdx) => {
    // Ordina piattaforme per valore decrescente in questo periodo
    const order = Object.keys(row)
      .filter(k => k !== 'period' && k !== '_order')
      .map(platform => ({ platform, value: row[platform] }))
      .sort((a, b) => b.value - a.value)
      .map(obj => obj.platform);
    let y0 = 0;
    order.forEach(platform => {
      const value = row[platform];
      const y1 = y0 + value;
      if (!stacked[platform]) stacked[platform] = [];
      stacked[platform].push({ y0, y1, period: row.period, platform, value });
      y0 = y1;
      if (y1 > yMax) yMax = y1;
    });
    // Assicura che tutte le piattaforme abbiano una entry anche se 0
    sortedPlatforms.forEach(platform => {
      if (!order.includes(platform)) {
        if (!stacked[platform]) stacked[platform] = [];
        const y1 = y0;
        stacked[platform].push({ y0: y1, y1: y1, period: row.period, platform, value: 0 });
      }
    });
  });

  const y = d3.scaleLinear().domain([0, yMax]).range([iH, 0]);

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // Per ogni piattaforma, disegna i rettangoli in ogni periodo
  Object.keys(stacked).forEach(platform => {
    g.append('g')
      .attr('class', 'layer')
      .attr('fill', color(platform))
      .selectAll('rect')
      .data(stacked[platform].map((d, i) => ({ ...d, key: platform, data: rows[i] })))
      .join('rect')
      .attr('x', d => x(d.period))
      .attr('y', iH)
      .attr('height', 0)
      .attr('width', x.bandwidth())
      .attr('stroke', '#fff')
      .attr('stroke-width', 1)
      .attr('pointer-events', d => (d.y1 - d.y0) < 0.001 ? 'none' : 'all')
      .style('cursor', 'pointer')
      .on('mouseover', (e, d) => {
        const proportion = (d.y1 - d.y0) * 100;
        showTip(`<b>${platformLabel(d.platform)}</b><br>${d.period}: <b>${proportion.toFixed(1)}%</b><br><small>Click to browse</small>`, e);
      })
      .on('mousemove', moveTip)
      .on('mouseout', hideTip)
      .on('click', (e, d) => {
        const key = `${d.period}||${d.platform}`;
        let slugs = comboToMemes[key] || [];
        if (!slugs.length && DATA && DATA.memes) {
          const PERIOD_MAP = {
            'Pre2010':      'Pre2010',
            '2010-2015':    'Period2010to2015',
            '2016-2020':    'Period2016to2020',
            '2021-present': 'Period2021toPresent'
          };
          const storedPeriod = PERIOD_MAP[d.period] || d.period;
          const namedPlatforms = new Set(platforms.filter(p => p !== 'Other'));
          slugs = Object.keys(DATA.memes).filter(slug => {
            const m = DATA.memes[slug];
            if (m.hasTimePeriod !== storedPeriod) return false;
            // Suppress impossible platform/period combinations from click-through panels.
            if (storedPeriod === 'Pre2010' && MODERN_PLATFORMS.has(m.hasOriginPlatform)) return false;
            if (storedPeriod === 'Period2010to2015' && POST2015_PLATFORMS.has(m.hasOriginPlatform)) return false;
            if (d.key === 'Other') return !m.hasOriginPlatform || !namedPlatforms.has(m.hasOriginPlatform);
            return m.hasOriginPlatform === d.key;
          });
        }
        openPanel(`${platformLabel(d.platform)} in ${d.period}`, slugs, 'platformTime', 'segment');
      });
  });

  revealOnView(wrap, () => g.selectAll('.layer rect').transition()
    .delay(d => x.domain().indexOf(d.period) * 90).duration(600).ease(d3.easeCubicOut)
    .attr('y', d => y(d.y1))
    .attr('height', d => Math.max(0, y(d.y0) - y(d.y1))));

  g.append('g')
    .attr('transform', `translate(0,${iH})`)
    .call(d3.axisBottom(x))
    .selectAll('text')
    .call(slantLabels, slant);

  g.append('g')
    .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${Math.round(d * 100)}%`))
    .selectAll('text')
    .style('font-size', TICK_PX + 'px')
    .style('fill', '#1a1a3a');

  g.selectAll('.domain, .tick line').attr('stroke', '#d0d0e0');

  // Each platform is a toggle: rows up to 44 px tall when the chart has the height for it
  const pitch = Math.max(24, Math.min(44, Math.floor((iH - 2 * 18) / platforms.length)));
  const legend = svg.append('g').attr('transform', `translate(${W - margin.right + 24},${margin.top})`);
  platforms.forEach((platform, i) => {
    const y0 = i * pitch;
    const off = hiddenPlatforms.has(platform);
    const item = legend.append('g')
      .attr('class', 'legend-toggle' + (off ? ' off' : ''))
      .attr('tabindex', 0)
      .attr('role', 'button')
      .attr('aria-pressed', String(!off))
      .attr('aria-label', `${off ? 'Show' : 'Hide'} ${platformLabel(platform)}`)
      .style('cursor', 'pointer')
      .on('click', () => togglePlatform(platform))
      .on('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePlatform(platform); } });
    item.append('rect')   // the whole row is the target
      .attr('x', -4).attr('y', y0)
      .attr('width', legendW + 8).attr('height', pitch)
      .attr('fill', 'transparent');
    item.append('rect')
      .attr('x', 0)
      .attr('y', y0 + pitch / 2 - 6)
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', off ? 'none' : color(platform))
      .attr('stroke', color(platform));
    item.append('text')
      .attr('x', 18)
      .attr('y', y0 + pitch / 2)
      .attr('dy', '.35em')
      .attr('fill', '#1a1a3a')
      .style('font-size', TICK_PX + 'px')
      .text(platformLabel(platform));
  });
  legend.append('text')
    .attr('y', platforms.length * pitch + 12)
    .attr('fill', MUTED_INK).style('font-size', LABEL_PX + 'px').attr('font-style', 'italic')
    .selectAll('tspan').data(legendNote).join('tspan')
    .attr('x', 0).attr('dy', (d, i) => i ? '1.3em' : '.71em')
    .text(d => d);
}

function togglePlatform(platform) {
  if (hiddenPlatforms.has(platform)) hiddenPlatforms.delete(platform);
  else hiddenPlatforms.add(platform);
  buildPlatformTimeStacked();
}

/* ═══════════════════════════════════════════════════════════════════════════
   Build all graphs
   ═══════════════════════════════════════════════════════════════════════════ */
let chartsStale = false;
function buildGraphs() {
  const app = document.getElementById('app');
  chartsStale = !!(app && app.classList.contains('hidden'));
  buildTimeline();
  buildPopularityByFormat();
  buildPlatformTimeStacked();
  buildVariantGallery();
  buildVariantBubble();
  if (typeof buildExtraGraphs === 'function') buildExtraGraphs();
}

/* ── Variant Gallery (Viz B) ─────────────────────────────────────────────── */
function buildVariantGallery() {
  var wrap = document.getElementById('graph-variant-gallery');
  if (!wrap || !Object.keys(TRANSFORM_MAP).length || !VARIANTS_DATA) return;

  var EXTENT_ORDER = ['Minimal', 'Moderate', 'Substantial', 'Parody'];
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
    html += '</div>';
    html += '<div class="vg-thumbs">';

    // Add original/template image first, next to the variants.
    var originalMeme = DATA && DATA.memes ? DATA.memes[slug] : null;
    var originalImg = originalMeme ? (memeRemoteSrc(originalMeme) || memeLocalSrc(originalMeme)) : '';
    html += '<a class="vg-thumb vg-thumb-original" href="' + escHtml(originalHref) + '" title="Original template (' + escHtml(originalType) + ')">';
    if (originalImg) {
      html += '<img src="' + escHtml(originalImg) + '" alt="' + escHtml(memeName + ' original') + '" loading="lazy" style="border:2px solid #222">';
    } else {
      html += '<div class="vg-thumb-missing">?</div>';
    }
    html += '<span class="vg-ext-label" style="color:#222">Original</span>';
    html += '</a>';

    uniqueVariants.forEach(function(a) {
      var v = varByPhotoId[String(a.photoId)];
      var localImg = (v && v.folder && v.filename)
        ? 'sampled_variants/' + v.folder + '/' + v.filename
        : '';
      var remoteImg = (a && a.imageURL) ? String(a.imageURL) : ((v && v.image_url) ? String(v.image_url) : '');
      var img = remoteImg || localImg;
      var extColor = EXTENT_COLOR[a.transformationExtent] || '#888';
      var extText = EXTENT_TEXT[a.transformationExtent] || MUTED_INK;
      var variantType = String(a.variantImageType || 'Unknown');
      var dims = Array.isArray(a.transformationDimension)
        ? a.transformationDimension.join(', ')
        : String(a.transformationDimension || '');
      var tipText = variantType + ' variant. Extent: ' + a.transformationExtent + '.' + (dims ? ' Dimensions: ' + dims + '.' : '');

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
      html += '<span class="vg-ext-label" style="color:' + extText + '">' + escHtml(a.transformationExtent) + '</span>';
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

  var rect = wrap.getBoundingClientRect();
  var W = rect.width || 900;
  var H = rect.height || 500;
  var mobile = isMobile();

  wrap.innerHTML = '';

  var svg = d3.select(wrap).append('svg')
    .attr('viewBox', '0 0 ' + W + ' ' + H)
    .attr('preserveAspectRatio', 'xMidYMid meet');

  // Fixed image size — popularity is already encoded by the X axis, not image size.
  var IMG_SIZE = mobile ? 28 : 64;

  // Pad scale ranges by half the image size so no image is clipped at the edges
  var PAD = IMG_SIZE / 2 + 4;

  // X = Number of Views (log scale)
  var xScale = d3.scaleLog()
    .domain([d3.min(points, function(p) { return Math.max(1, p.views); }),
             d3.max(points, function(p) { return p.views; })])
    .nice();

  // Y = Creative Productivity (photos), log scale; photos=0 → y=1
  var yScale = d3.scaleLog()
    .domain([1, d3.max(points, function(p) { return Math.max(1, p.photos); })])
    .nice();

  // Margins from the labels: the axis title starts on the section title's edge, then the ticks;
  // the top leaves room for the zoom buttons, the bottom only what the x ticks and title need.
  var inset = titleInset(wrap);
  var yTickW = textWidth(svg.node(), yScale.ticks(5).map(yScale.tickFormat(5, '.0s')).filter(Boolean), TICK_PX);
  var M = {
    top: mobile ? 56 : 64,
    right: mobile ? 8 : 24,
    bottom: 9 + TICK_PX + 16 + LABEL_PX + 8,
    left: inset + LABEL_PX + 16 + yTickW + 9
  };
  var w = W - M.left - M.right;
  var h = H - M.top - M.bottom;
  xScale.range([PAD, w - PAD]);
  yScale.range([h - PAD, PAD]);

  // Clip images to chart bounds
  svg.append('defs').append('clipPath').attr('id', 'bubble-clip')
    .append('rect').attr('width', w).attr('height', h);

  var g = svg.append('g').attr('transform', 'translate(' + M.left + ',' + M.top + ')');

  // Gridlines + axes (redrawn on zoom)
  var gridY = g.append('g');
  var gridX = g.append('g').attr('transform', 'translate(0,' + h + ')');
  var axY = g.append('g').attr('color', MUTED_INK);
  var axX = g.append('g').attr('transform', 'translate(0,' + h + ')').attr('color', MUTED_INK);
  function drawAxes(zx, zy) {
    var gridStyle = function(sel) {
      sel.selectAll('line').attr('stroke', 'rgba(0,0,0,.07)').attr('stroke-width', 0.6);
      sel.select('.domain').remove();
    };
    gridY.call(d3.axisLeft(zy).ticks(5, '.0s').tickSize(-w).tickFormat('')).call(gridStyle);
    gridX.call(d3.axisBottom(zx).ticks(6, '.0s').tickSize(-h).tickFormat('')).call(gridStyle);
    axY.call(d3.axisLeft(zy).ticks(5, '.0s')).selectAll('text').style('font-size', TICK_PX + 'px');
    // on phones only the decades in view are labelled (10k, 100k, 1M, 10M), so the labels do not collide
    var decades = zx.ticks().filter(function(v) { return Math.abs(Math.log10(v) % 1) < 1e-9; });
    var xAxis = d3.axisBottom(zx).ticks(6, '.0s');
    if (mobile && decades.length >= 2) xAxis.tickValues(decades).tickFormat(d3.format('.0s'));
    axX.call(xAxis).selectAll('text').style('font-size', TICK_PX + 'px');
  }
  drawAxes(xScale, yScale);

  // Axis labels
  g.append('text').attr('x', w / 2).attr('y', h + 9 + TICK_PX + 16).attr('dy', '.71em')
    .attr('text-anchor', 'middle').attr('fill', MUTED_INK).style('font-size', LABEL_PX + 'px')
    .text('Number of views');
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -(h / 2)).attr('y', inset - M.left).attr('dy', '.71em')
    .attr('text-anchor', 'middle').attr('fill', MUTED_INK).style('font-size', LABEL_PX + 'px')
    .text('Number of variants');

  // Bigger memes need room: where neighbours overlap, an image is nudged aside and keeps a thin line
  // to a dot on its exact value (under the images; hovering a meme brings both to the front).
  // Recomputed from the current positions after every zoom step.
  function place(zx, zy, ticks) {
    points.forEach(function(p) {
      p.tx = zx(Math.max(1, p.views));
      p.ty = zy(Math.max(1, p.photos));
      if (p.x == null) { p.x = p.tx; p.y = p.ty; }
    });
    var half = IMG_SIZE / 2;
    var sim = d3.forceSimulation(points)
      .force('x', d3.forceX(function(p) { return p.tx; }).strength(0.25))
      .force('y', d3.forceY(function(p) { return p.ty; }).strength(0.25))
      .force('collide', d3.forceCollide(half * 0.9).strength(0.8))
      .stop();
    for (var i = 0; i < ticks; i++) {
      sim.tick();
      points.forEach(function(p) {   // memes whose value is on screen stay inside the plot
        if (p.tx < 0 || p.tx > w || p.ty < 0 || p.ty > h) return;
        p.x = Math.max(half, Math.min(w - half, p.x));
        p.y = Math.max(half, Math.min(h - half, p.y));
      });
    }
    points.forEach(function(p) { p.moved = Math.hypot(p.x - p.tx, p.y - p.ty) > 6; });
  }
  function lineTo(sel) {
    sel.attr('x1', function(p) { return p.tx; }).attr('y1', function(p) { return p.ty; })
      .attr('x2', function(p) { return p.x; }).attr('y2', function(p) { return p.y; });
  }
  function drawMemes() {
    leaders.call(lineTo).attr('display', function(p) { return p.moved ? null : 'none'; });
    anchors.attr('cx', function(p) { return p.tx; }).attr('cy', function(p) { return p.ty; })
      .attr('display', function(p) { return p.moved ? null : 'none'; });
    imgs.attr('x', function(p) { return p.x - IMG_SIZE / 2; })
      .attr('y', function(p) { return p.y - IMG_SIZE / 2; });
    if (hot) showExact(hot);
  }
  var hot = null;
  function showExact(p) {
    hot = p;
    focusG.attr('display', p && p.moved ? null : 'none');
    if (!p) return;
    focusLine.datum(p).call(lineTo);
    focusDot.attr('cx', p.tx).attr('cy', p.ty);
  }

  // Meme images — all 50 entries, uniform size (popularity on X axis, variants on Y axis)
  var memeG = g.append('g').attr('clip-path', 'url(#bubble-clip)');
  var leaders = memeG.append('g').selectAll('line').data(points).join('line')
    .attr('stroke', '#8a8378').attr('stroke-width', 1);
  var anchors = memeG.append('g').selectAll('circle').data(points).join('circle')
    .attr('r', 3).attr('fill', '#141414');
  var imgs = memeG.append('g').selectAll('image').data(points).join('image')
      .attr('width',  IMG_SIZE)
      .attr('height', IMG_SIZE)
      .attr('href', function(p) { return p.imgSrc; })
      .attr('preserveAspectRatio', 'xMidYMid slice')
      .style('cursor', 'pointer')
      .on('mouseover', function(evt, p) {
        this.parentNode.appendChild(this);   // the hovered meme on top, with its exact point
        showExact(p);
        showTip('<strong>' + escHtml(p.name) + '</strong><br/>' +
          p.views.toLocaleString() + ' views, ' + p.photos.toLocaleString() + ' photos', evt);
      })
      .on('mousemove', moveTip)
      .on('mouseout', function() { showExact(null); hideTip(); })
      .on('click', function(evt, p) {
        if (p.id != null) location.hash = '#d0/' + encodeURIComponent(String(p.id));
      });
  var focusG = memeG.append('g').style('pointer-events', 'none').attr('display', 'none');
  var focusLine = focusG.append('line').attr('stroke', '#141414').attr('stroke-width', 1.5);
  var focusDot = focusG.append('circle').attr('r', 4).attr('fill', '#141414')
    .attr('stroke', '#fff').attr('stroke-width', 1.5);
  points.forEach(function(p) { p.x = p.y = null; });
  place(xScale, yScale, 160);
  drawMemes();

  // Zoom & pan: drag to pan, Ctrl/⌘ + wheel or the buttons to zoom (plain wheel keeps scrolling the page)
  var zoom = d3.zoom()
    .scaleExtent([1, 16])
    .extent([[0, 0], [w, h]])
    .translateExtent([[0, 0], [w, h]])
    .filter(function(e) { return e.type === 'wheel' ? (e.ctrlKey || e.metaKey) : !e.button; })
    .on('zoom', function(e) {
      var zx = e.transform.rescaleX(xScale);
      var zy = e.transform.rescaleY(yScale);
      drawAxes(zx, zy);
      place(zx, zy, 40);
      drawMemes();
    });
  var zoomRect = g.insert('rect', ':first-child').attr('width', w).attr('height', h)
    .attr('fill', 'transparent').style('cursor', 'grab');
  svg.call(zoom).on('dblclick.zoom', null);
  zoomRect.lower();

  var tools = document.createElement('div');
  tools.className = 'zoom-tools';
  tools.innerHTML = '<button type="button" data-z="in" aria-label="Zoom in">+</button>' +
    '<button type="button" data-z="out" aria-label="Zoom out">−</button>' +
    '<button type="button" data-z="reset" aria-label="Reset zoom">Reset</button>' +
    '<span>Drag to pan. Ctrl/⌘ + scroll to zoom.</span>';
  tools.addEventListener('click', function(e) {
    var z = e.target.getAttribute('data-z');
    if (!z) return;
    var t = svg.transition().duration(350);
    if (z === 'in') zoom.scaleBy(t, 1.8);
    else if (z === 'out') zoom.scaleBy(t, 1 / 1.8);
    else zoom.transform(t, d3.zoomIdentity);
  });
  wrap.appendChild(tools);
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

  document.getElementById('panel-label').textContent = graphKey + (group ? ', ' + group : '');
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
  const fmts  = (m.hasFormat || []).filter(f => f && f !== 'Unknown').join(', ') || 'none';

  document.getElementById('meme-page-content').innerHTML = `
    <button class="meme-page-back" onclick="history.back()">&#8592; Back</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        ${memeImgTag(m, title)}
        ${m.memeUrl ? `<a href="${escHtml(m.memeUrl)}" target="_blank" rel="noopener">Open on Know Your Meme ↗</a>` : ''}
      </div>
      <div class="meme-page-info">
        <h1>${escHtml(title)}</h1>
        <div class="meme-page-id">id ${String(m.id).padStart(4,'0')}, ${escHtml(m.imageFilename)}</div>

        <div class="detail-section">
          <div class="detail-section-title">Visual analysis (CLIP)</div>
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
          <div class="detail-section-title">Origin and distribution</div>
          ${row('hasOriginPlatform', m.hasOriginPlatform, 'accent')}
          ${row('hasOriginWork',     m.hasOriginWork)}
          ${row('hasRegion',         m.hasRegion)}
          ${row('hasTimePeriod',     m.hasTimePeriod)}
          ${row('yearOfOrigin',      m.year)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Meme format</div>
          ${row('hasFormat', fmts)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">File and FRBR</div>
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
    : (m.type || []).join(', ') || 'none';
  const views   = m.views   != null ? Number(m.views).toLocaleString()   : null;
  const videos  = m.videos  != null ? Number(m.videos).toLocaleString()  : null;
  const photos  = m.photos  != null ? Number(m.photos).toLocaleString()  : null;
  const comments = m.comments != null ? Number(m.comments).toLocaleString() : null;
  const crAnnot = CULTURAL_MAP[slug];
  const img     = m.image_url || m.image_path || '';

  document.getElementById('d0-page-content').innerHTML = `
    <button class="meme-page-back" onclick="location.hash='#'+prevVizHash">&#8592; Back to Visualizations</button>
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
        <div class="meme-page-id">D0 sample, id ${String(m.id).padStart(4,'0')}, ${escHtml(m.image_filename || '')}</div>

        ${m.description ? `
        <div class="detail-section">
          <div class="detail-section-title">Description</div>
          <p style="font-size:.84rem;color:var(--text);line-height:1.65;margin:0">${escHtml(m.description)}</p>
        </div>` : ''}

        <div class="detail-section">
          <div class="detail-section-title">Visual analysis (CLIP)</div>
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
          <div class="detail-section-title">Origin and distribution</div>
          ${row('hasOriginPlatform', m.hasOriginPlatform || m.origin, 'accent')}
          ${row('hasOriginWork',     m.hasOriginWork)}
          ${row('hasRegion',         m.hasRegion || m.region)}
          ${row('hasTimePeriod',     m.hasTimePeriod)}
          ${row('yearOfOrigin',      m.year)}
        </div>

        <div class="detail-section">
          <div class="detail-section-title">Meme format</div>
          ${row('hasFormat',          fmts)}
          ${row('hasFileFormat',      m.hasFileFormat)}
          ${row('hasAnimationStatus', m.hasAnimationStatus)}
          ${row('hasFRBRLevel',       'Manifestation')}
        </div>

        ${crAnnot && crAnnot.references && crAnnot.references.length ? `
        <div class="detail-section">
          <div class="detail-section-title">Cultural references</div>
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
    <button class="meme-page-back" onclick="location.hash='#'+prevVizHash">&#8592; Back to Visualizations</button>
    <div class="meme-page-layout">
      <div class="meme-page-img-col">
        <img src="${img}" alt="${escHtml(title)}"${onError}/>
        ${v.photo_url ? `<a href="${escHtml(v.photo_url)}" target="_blank" rel="noopener">View on Know Your Meme ↗</a>` : ''}
      </div>
      <div class="meme-page-info">
        <h1>${escHtml(title)}</h1>
        <div class="meme-page-id">Variant of ${escHtml(v.meme_name || '')}, photo_id ${escHtml(photoId)}</div>

        <div class="detail-section">
          <div class="detail-section-title">Variant metadata</div>
          ${row('uploader',    v.author)}
          ${row('variantIndex', annot ? String(annot.variantIndex) : null)}
          ${v.img_alt ? row('caption / alt text', v.img_alt) : ''}
        </div>

        ${annot ? `
        <div class="detail-section">
          <div class="detail-section-title">Transformation annotation</div>
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
          <div class="detail-section-title">Cultural references (parent meme)</div>
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
      <h2>At a glance</h2>
      <div class="about-stats">
        <div class="stat-card"><span class="stat-num">${memeCount.toLocaleString()}</span><span class="stat-label">Memes</span></div>
        <div class="stat-card"><span class="stat-num">OWL 2 DL</span><span class="stat-label">Ontology format</span></div>
        <div class="stat-card"><span class="stat-num">CLIP</span><span class="stat-label">Image classifier</span></div>
        <div class="stat-card"><span class="stat-num">KYM</span><span class="stat-label">Data source</span></div>
      </div>
    </div>

    <div class="about-section">
      <h2>Project</h2>
      <p>The Meme Ontology is a research project that applies formal knowledge representation to internet culture. Each meme in the dataset is represented as an OWL 2 DL individual with properties covering its visual content, cultural context, origin, and format classification.</p>
      <p>The dataset is sourced from <a href="https://knowyourmeme.com" target="_blank" rel="noopener" style="color:var(--accent2)">Know Your Meme</a>, enriched with automated CLIP-based image classification and structured using a custom OWL 2 DL ontology with classes for image type, subject matter, meme format, origin platform, geographic region, and temporal period.</p>
    </div>

    <div class="about-section">
      <h2>Pipeline</h2>
      <ol class="about-pipeline">
        <li class="pipeline-step">
          <div class="pipeline-label">Data collection</div>
          <div class="pipeline-desc">Metadata and images scraped from Know Your Meme via the public API and image archives with rate-limiting compliance.</div>
        </li>
        <li class="pipeline-step">
          <div class="pipeline-label">CLIP classification</div>
          <div class="pipeline-desc">Each image is classified across six ontology dimensions using OpenAI CLIP zero-shot inference.</div>
        </li>
        <li class="pipeline-step">
          <div class="pipeline-label">OWL generation</div>
          <div class="pipeline-desc">Classifications are serialised into an OWL 2 DL/RDF ontology using rdflib with FRBR-aligned hierarchy.</div>
        </li>
        <li class="pipeline-step">
          <div class="pipeline-label">Visualisation</div>
          <div class="pipeline-desc">Interactive D3.js visualisations expose co-occurrence patterns across tags, formats, and platforms on mobile and desktop.</div>
        </li>
      </ol>
    </div>

    <div class="about-section">
      <h2>Ontology structure</h2>
      <p>The ontology uses the MEME namespace and defines properties including <code style="font-family:monospace;color:var(--accent2)">hasImageType</code>, <code style="font-family:monospace;color:var(--accent2)">hasSubjectMatter</code>, <code style="font-family:monospace;color:var(--accent2)">hasFormat</code>, <code style="font-family:monospace;color:var(--accent2)">hasOriginPlatform</code>, <code style="font-family:monospace;color:var(--accent2)">hasRegion</code>, and <code style="font-family:monospace;color:var(--accent2)">hasTimePeriod</code>. FRBR levels (Work → Expression → Manifestation → Item) are used to model the abstraction hierarchy of meme instances.</p>
    </div>

    <div class="about-section">
      <h2>Semantic interoperability</h2>
      <p>The ontology aligns with established external vocabularies to improve data interoperability and semantic clarity:</p>
      <ul style="margin-left:20px;color:var(--text-alt)">
        <li><code style="color:var(--accent2)">hasOriginWork</code> → <code>schema:isBasedOn</code> (schema.org)</li>
        <li><code style="color:var(--accent2)">yearOfOrigin</code> → <code>dcterms:created</code> (Dublin Core Terms)</li>
        <li><code style="color:var(--accent2)">hasRegion</code> → <code>dcterms:spatial</code> (Dublin Core Terms)</li>
        <li><code style="color:var(--accent2)">memeURL</code> → <code>schema:url</code> (schema.org)</li>
        <li><code style="color:var(--accent2)">description</code> → <code>dcterms:description</code> (Dublin Core Terms)</li>
        <li><code style="color:var(--accent2)">tags</code> → <code>schema:keywords</code> (schema.org)</li>
        <li><code style="color:var(--accent2)">views</code> → <code>schema:interactionCount</code> (schema.org)</li>
      </ul>
    </div>

    <div class="about-section">
      <h2>Design principles</h2>
      <ul style="margin-left:20px;color:var(--text-alt)">
        <li><strong>FRBR-aligned hierarchy:</strong> Properties are annotated with FRBR levels to distinguish between abstract works, expressions, physical manifestations, and item-level variants.</li>
        <li><strong>Panofsky framework:</strong> Semantic levels (PreIconographical, Iconographical, Iconological) applied to properties capturing visual form, cultural meaning, and ideological context.</li>
        <li><strong>OWL 2 DL compliance:</strong> The ontology is designed to be decidable and reasonably expressible within OWL 2 DL semantics, enabling computational reasoning and validation.</li>
        <li><strong>Responsive design:</strong> Interactive visualisations adapt dynamically to mobile, tablet, and desktop viewports through CSS media queries and JavaScript event handlers.</li>
        <li><strong>Property symmetry:</strong> Canonical and variant properties maintain inverse declarations (e.g., <code>hasVariantSubjectMatter</code> ↔ <code>isVariantSubjectMatterOf</code>) to ensure complete bidirectional traversal.</li>
      </ul>
    </div>
  `;
}

/* ── Disclaimer page ───────────────────────────────────────────────────────────── */
function buildDisclaimerPage() {
  document.getElementById('disclaimer-content').innerHTML = `
    <h1>Legal and ethical disclaimer</h1>
    <p class="page-sub">A note on the status of this data collection.</p>

    <div class="about-section">
      <h2>Data collection practices</h2>
      <p>KnowYourMeme's Terms of Service, maintained by Literally Media Ltd., prohibit automated access that sends more requests to its servers than a human user could reasonably produce in the same period. This research respects the spirit of this restriction through a polite crawl delay of 0.5 to 2 seconds between requests, keeping the total request rate well within what a human user could produce.</p>
    </div>

    <div class="about-section">
      <h2>Data access</h2>
      <p>All data collected is publicly accessible without authentication, login or subscription as KnowYourMeme's confirmed entry pages are indexed by search engines and freely readable by any browser without account registration. The scraping targets no private, user-specific or authenticated content.</p>
    </div>

    <div class="about-section">
      <h2>Research purpose</h2>
      <p>The dataset is collected exclusively for non-commercial academic research purposes under academic supervision at the University of Bologna and is not redistributed commercially. No personal data about KnowYourMeme contributors or users was collected at any stage.</p>
    </div>

    <div class="about-section">
      <h2>Academic precedent</h2>
      <p>This practice follows established precedent in digital humanities and internet studies scholarship, where KnowYourMeme has been treated as a legitimate primary source for meme research and used as a data source for computational analysis (Zannettou et al. 2018, 2; Shifman 2014, 89).</p>
    </div>

    <div class="about-section">
      <h2>Legal position</h2>
      <p>Academic research scraping of publicly accessible web content occupies a legally and ethically defensible position, particularly where the research is non-commercial, rate-limited and does not target personal data, conditions this research satisfies in full.</p>
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
    const o = document.createElement('option'); o.value = p; o.textContent = platformLabel(p); platSel.appendChild(o);
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
      ${dim ? `<span class="ds-d0-meta ds-d0-annot">${ext ? escHtml(ext) + ': ' : ''}${escHtml([].concat(dim).join(', '))}</span>` : ''}
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
      if (en.isIntersecting) {
        dots.forEach(d => { d.classList.remove('active'); d.removeAttribute('aria-current'); });
        const dot = document.querySelector(`.dot[href="#${en.target.id}"]`);
        if (dot) { dot.classList.add('active'); dot.setAttribute('aria-current', 'location'); }
      }
    });
  }, { rootMargin: '-50% 0px -50% 0px' });

  document.querySelectorAll('.viz-section').forEach(s => obs.observe(s));
  dots.forEach(dot => dot.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(dot.getAttribute('href'));
    if (target) scrollToSection(target, 3);
  }));
}

/* Charts build as they come near the screen and can change the page height while a smooth scroll is
   on its way, which stops it short: once scrolling ends, finish the trip if the section is not there.
   The section's scroll-margin-top (the bar's height) is applied here: scrollIntoView leaves it out. */
function scrollToSection(target, tries) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const offset = () => target.getBoundingClientRect().top - (parseFloat(getComputedStyle(target).scrollMarginTop) || 0);
  window.scrollTo({ top: window.scrollY + offset(), behavior: reduce ? 'auto' : 'smooth' });
  let timer;
  const settle = () => {
    window.removeEventListener('scrollend', settle);
    clearTimeout(timer);
    if (Math.abs(offset()) > 4 && tries > 1) scrollToSection(target, tries - 1);
  };
  window.addEventListener('scrollend', settle);
  timer = setTimeout(settle, 1500);
}
