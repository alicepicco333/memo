/* The MEMO ontology as a 2D graph (Ontology page).
   Data: onto_graph.json, extracted from meme_ontology_unpopulated.ttl: classes, subclass links and
   object properties (inverse properties are left out so each relation is drawn once).

   The graph radiates from the meme: MemeConcept sits in the middle, captioned like a meme and ringed by
   its sample memes; every other class sits on a ring set by how many steps it is from MemeConcept.
   Class squares grow with the number of individuals. The six classes the Knowledge-graph walk uses
   carry the walk's colours (meme_viz_extra.js PROP_FIELDS), so the two views read as one; the rest is ink.
   The layout is worked out once, from a fixed seed, before anything is drawn: every visitor gets the same
   picture, it appears still and fitted to its box, and dragging a class moves only that class. */
(function () {
  var svgEl = document.getElementById('onto-graph-svg');
  if (!svgEl || !window.d3) return;
  var started = false;

  // the walk's property colours, on the classes those properties point to (subclasses inherit them)
  var WALK = {
    MemeFormat: '#c8742a', OriginPlatform: '#3a8fd8', ImageType: '#8e5cc9',
    TimePeriod: '#2a9d6f', SubjectMatter: '#b03a4b', GeographicRegion: '#7a7a2e'
  };
  var HUB = 'memo:MemeConcept';
  var HUB_R = 100;         // the meme ring: caption inside, sample memes on it
  var THUMB_R = 23;        // a sample meme's round thumbnail
  var SEED = 0.42;         // the layout's fixed seed
  // sample memes kept out of the hub's showcase (they stay in the dataset): an adult-site logo on minors
  var NOT_SHOWN = { brazzers: 1 };
  var CH = 7.3;            // IBM Plex Mono 12 px: about 7.3 px a character
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var COARSE = window.matchMedia('(pointer: coarse)').matches;

  function start() {
    if (started || svgEl.getBoundingClientRect().width === 0) return;
    started = true;
    fetch('onto_graph.json').then(function (r) { return r.json(); }).then(draw);
  }

  // the wall's local thumbnail for a meme slug (same naming as build_wall_thumbs.py)
  function thumbFor(slug) { return 'img/wall/m-' + String(slug).toLowerCase().replace(/[^a-z0-9_-]/g, '_') + '.webp'; }
  function nameFor(slug) {
    var s = String(slug || '').replace(/^_+/, '');
    try { s = decodeURIComponent(s); } catch (e) { /* keep as is */ }
    return s.replace(/[-_]+/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); }).trim();
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  function draw(data) {
    var rand = d3.randomLcg(SEED);
    var INVERSE = /^is[A-Z]/;
    var links = data.links.filter(function (l) { return l.type === 'sub' || !INVERSE.test(l.label); });
    var nodes = data.nodes.map(function (n) { return Object.assign({}, n); });
    var byId = {};
    nodes.forEach(function (n) { byId[n.id] = n; });
    links = links.filter(function (l) { return byId[l.source] && byId[l.target]; }).map(function (l) { return Object.assign({}, l); });
    var classNodes = nodes.slice();

    // colour: the walk's classes, then their subclasses
    classNodes.forEach(function (c) { c.color = WALK[c.label] || null; });
    links.forEach(function (l) { if (l.type === 'sub' && !byId[l.source].color && byId[l.target].color) byId[l.source].color = byId[l.target].color; });

    // steps from MemeConcept over subclass and property links, in both directions
    var adj = {};
    links.forEach(function (l) { (adj[l.source] = adj[l.source] || []).push(l.target); (adj[l.target] = adj[l.target] || []).push(l.source); });
    var queue = [HUB], maxHop = 0;
    if (byId[HUB]) byId[HUB].hop = 0;
    while (queue.length) {
      var id = queue.shift();
      (adj[id] || []).forEach(function (nb) {
        if (byId[nb].hop == null) { byId[nb].hop = byId[id].hop + 1; maxHop = Math.max(maxHop, byId[nb].hop); queue.push(nb); }
      });
    }
    classNodes.forEach(function (c) { if (c.hop == null) c.hop = maxHop + 1; });
    maxHop = d3.max(classNodes, function (c) { return c.hop; });

    // individuals: up to six examples per class (from build_onto_individuals.py); MemeConcept's are memes
    classNodes.forEach(function (c) {
      (c.sample || []).forEach(function (ind, i) {
        var lab = String(ind.label || '');
        if (/�/.test(lab)) return;
        var isMeme = c.id === HUB;
        if (isMeme && NOT_SHOWN[lab.replace(/^_+/, '')]) return;
        var n = { id: 'ind:' + c.id + ':' + i, label: isMeme ? nameFor(lab) : lab, slug: isMeme ? lab.replace(/^_+/, '') : null,
          kind: 'individual', meme: isMeme, cls: c, color: c.color };
        nodes.push(n); byId[n.id] = n;
        links.push({ source: c.id, target: n.id, type: 'inst', label: 'rdf:type' });
      });
    });

    var box = document.getElementById('onto-graph');
    var info = document.getElementById('onto-graph-info');
    var W = svgEl.clientWidth, H = svgEl.clientHeight;
    // the layout is computed on a canvas at least 1100 x 640, so a small screen gets the same graph at a
    // readable size and pans across it instead of a squeezed one
    var LW = Math.max(W, 1100), LH = Math.max(H, 640);
    var cx = LW / 2, cy = LH / 2;
    var ax = LW / 2 - 170, ay = LH / 2 - 48;          // the outer ellipse, with room for labels
    // the first ring clears the meme ring; the last one leaves room for individuals and labels outside it
    var R1 = Math.max(0.46, (HUB_R + THUMB_R + 46) / ay);
    var ringR = function (h) { return h <= 0 ? 0 : R1 + (0.9 - R1) * (h - 1) / Math.max(1, maxHop - 1); };

    var size = d3.scaleSqrt().domain([0, 1000]).range([8, 22]).clamp(true);
    classNodes.forEach(function (c) { c.side = size(c.count || 0); });

    // start every class on its ring, near the class it hangs from, so the force step only refines
    var placed = {};
    var hub = byId[HUB];
    if (hub) { hub.x = hub.fx = cx; hub.y = hub.fy = cy; placed[HUB] = 0; }
    for (var h = 1; h <= maxHop; h++) {
      var ring = classNodes.filter(function (c) { return c.hop === h; });
      ring.forEach(function (c, i) {
        var parents = (adj[c.id] || []).filter(function (p) { return placed[p] != null && byId[p].hop === h - 1; });
        var a = parents.length ? placed[parents[0]] + (i % 3 - 1) * 0.22 : (i / ring.length) * Math.PI * 2;
        if (h === 1) a = (i / ring.length) * Math.PI * 2 - Math.PI / 2;
        placed[c.id] = a;
        c.x = cx + Math.cos(a) * ringR(h) * ax; c.y = cy + Math.sin(a) * ringR(h) * ay;
      });
    }
    // MemeConcept's memes sit on the meme ring, fixed
    var memes = nodes.filter(function (n) { return n.meme; });
    memes.forEach(function (m, i) {
      var a = (i / memes.length) * Math.PI * 2 - Math.PI / 2;
      m.x = m.fx = cx + Math.cos(a) * HUB_R; m.y = m.fy = cy + Math.sin(a) * HUB_R;
    });
    nodes.forEach(function (n) {
      if (n.kind === 'individual' && !n.meme) { n.x = n.cls.x + (rand() - 0.5) * 20; n.y = n.cls.y + (rand() - 0.5) * 20; }
    });

    // a soft pull onto each class's ring (an ellipse, to use the wide box)
    function ringForce(alpha) {
      classNodes.forEach(function (d) {
        if (d.id === HUB) return;
        var ux = (d.x - cx) / ax, uy = (d.y - cy) / ay, dist = Math.hypot(ux, uy) || 1e-6;
        var k = (ringR(d.hop) - dist) / dist * alpha * 1.2;
        d.vx += ux * k * ax; d.vy += uy * k * ay;
      });
    }

    var s = Math.max(0.85, Math.min(1.15, Math.sqrt((LW * LH) / (1312 * 720))));
    var sim = d3.forceSimulation(nodes)
      .randomSource(rand)
      .force('link', d3.forceLink(links).id(function (d) { return d.id; })
        .distance(function (l) { return (l.type === 'sub' ? 56 : l.type === 'inst' ? 28 : 150) * s; })
        .strength(function (l) { return l.type === 'sub' ? 0.5 : l.type === 'inst' ? 1 : 0.06; }))
      .force('charge', d3.forceManyBody().strength(function (d) { return d.kind === 'individual' ? -18 : -200 * s; }).distanceMax(300))
      // labels point outward, so a class needs room for part of its label, not all of it
      .force('collide', d3.forceCollide().radius(function (d) {
        return d.meme ? THUMB_R + 2 : d.kind === 'individual' ? 6 : d.id === HUB ? HUB_R + THUMB_R + 8 : d.side / 2 + 10 + Math.min(d.label.length * 2.2, 36);
      }).strength(0.9))
      .force('ring', ringForce)
      .stop();
    for (var i = 0, n = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay())); i < n; i++) sim.tick();

    // every class exactly on its ring (keeping its angle), so the ring says how far it is from the meme
    classNodes.forEach(function (d) {
      if (d.id === HUB) return;
      var a = Math.atan2((d.y - cy) / ay, (d.x - cx) / ax);
      d.x = cx + Math.cos(a) * ringR(d.hop) * ax; d.y = cy + Math.sin(a) * ringR(d.hop) * ay;
    });

    // individuals hang as a small fan, above their class on the upper half and below it on the lower half
    var fans = {};
    nodes.forEach(function (n) { if (n.kind === 'individual' && !n.meme) (fans[n.cls.id] = fans[n.cls.id] || []).push(n); });
    function placeFan(c) {
      var g = fans[c.id]; if (!g) return;
      var base = c.y < cy ? -Math.PI / 2 : Math.PI / 2, spread = Math.min(1.9, 0.38 * (g.length - 1)), r = c.side / 2 + 16;
      g.forEach(function (m, j) {
        var a = base + (g.length === 1 ? 0 : -spread / 2 + spread * j / (g.length - 1));
        m.x = c.x + Math.cos(a) * r; m.y = c.y + Math.sin(a) * r;
      });
    }
    function labelWidth(d) { return (d.label.length + (d.count ? d.count.toLocaleString().length + 1 : 0)) * CH; }

    // labels are wide and the forces see round nodes, so a last pass treats each label (with the fan it
    // carries) as the box it is: overlapping classes move apart up and down, never into the meme ring
    (function relaxLabels() {
      var HALF = 9, movable = classNodes.filter(function (c) { return c.id !== HUB; });
      function boxOf(d) {
        var w = labelWidth(d), off = d.side / 2 + 6, left = d.x < cx - 4;
        var fan = fans[d.id] ? d.side / 2 + 22 : HALF, up = d.y < cy;
        var y0 = d.y - (up ? Math.max(HALF, fan) : HALF), y1 = d.y + (up ? HALF : Math.max(HALF, fan));
        return left ? { x0: d.x - off - w - 3, x1: d.x + d.side / 2 + 3, y0: y0, y1: y1 }
                    : { x0: d.x - d.side / 2 - 3, x1: d.x + off + w + 3, y0: y0, y1: y1 };
      }
      var clear = HUB_R + THUMB_R + 10;
      for (var it = 0; it < 160; it++) {
        var moved = false;
        for (var a = 0; a < movable.length; a++) {
          for (var b = a + 1; b < movable.length; b++) {
            var p = movable[a], q = movable[b], A = boxOf(p), B = boxOf(q);
            if (A.x1 <= B.x0 || B.x1 <= A.x0 || A.y1 <= B.y0 || B.y1 <= A.y0) continue;
            var push = Math.min(A.y1 - B.y0, B.y1 - A.y0) / 2 + 1;
            if (p.y <= q.y) { p.y -= push; q.y += push; } else { p.y += push; q.y -= push; }
            moved = true;
          }
        }
        movable.forEach(function (d) {
          var B = boxOf(d), nx = Math.max(B.x0, Math.min(cx, B.x1)), ny = Math.max(B.y0, Math.min(cy, B.y1));
          var dist = Math.hypot(nx - cx, ny - cy);
          if (dist < clear) { d.y += (d.y >= cy ? 1 : -1) * (clear - dist + 1); moved = true; }
        });
        if (!moved) break;
      }
    })();
    classNodes.forEach(placeFan);
    nodes.forEach(function (n) { n.hx = n.x; n.hy = n.y; });   // the layout, for Reset

    // ── drawing ──────────────────────────────────────────────────────────
    var svg = d3.select(svgEl).attr('viewBox', [0, 0, W, H]);
    var defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'og-arrow').attr('viewBox', '0 -4 8 8').attr('refX', 8).attr('refY', 0)
      .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#8a8378');
    defs.append('clipPath').attr('id', 'og-thumb-clip').attr('clipPathUnits', 'objectBoundingBox')
      .append('circle').attr('cx', 0.5).attr('cy', 0.5).attr('r', 0.5);
    var root = svg.append('g').attr('class', 'og-root');
    // plain wheel scrolls the page; Ctrl/Cmd + wheel (or pinch) zooms, drag pans
    var zoom = d3.zoom().scaleExtent([0.4, 3])
      .filter(function (e) { return e.type === 'wheel' ? (e.ctrlKey || e.metaKey) : !e.button; })
      .on('zoom', function (e) { root.attr('transform', e.transform); });
    svg.call(zoom).on('dblclick.zoom', null);

    // controls: zoom, reset, the individuals toggle and a hint, on one row above the graph
    var home = d3.zoomIdentity;
    var tools = document.createElement('div');
    tools.className = 'onto-graph-zoom';
    tools.innerHTML = '<button type="button" data-z="in" aria-label="Zoom in">+</button>' +
      '<button type="button" data-z="out" aria-label="Zoom out">−</button>' +
      '<button type="button" data-z="reset">Reset</button>';
    var toggleLabel = document.querySelector('#onto-graph .onto-graph-toggle');
    if (toggleLabel) tools.appendChild(toggleLabel);
    var hint = document.createElement('span');
    hint.className = 'onto-graph-hint';
    hint.textContent = COARSE ? 'Drag sideways to move, pinch to zoom, tap a class to read it.'
      : 'Ctrl/⌘ + scroll to zoom. Drag to pan or to move a class.';
    tools.appendChild(hint);
    tools.addEventListener('click', function (e) {
      var z = e.target.getAttribute && e.target.getAttribute('data-z'); if (!z) return;
      var t = svg.transition().duration(REDUCED ? 0 : 240).ease(d3.easeCubicOut);
      if (z === 'in') zoom.scaleBy(t, 1.5);
      else if (z === 'out') zoom.scaleBy(t, 1 / 1.5);
      else { nodes.forEach(function (d) { d.x = d.hx; d.y = d.hy; }); render(); zoom.transform(t, home); }
    });
    svgEl.parentNode.insertBefore(tools, svgEl);

    // the rings: faint guides, because a class's ring says how far it is from the meme
    root.append('g').attr('class', 'og-rings').attr('aria-hidden', 'true').selectAll('ellipse')
      .data(d3.range(1, maxHop + 1)).join('ellipse')
      .attr('cx', cx).attr('cy', cy)
      .attr('rx', function (h) { return ringR(h) * ax; }).attr('ry', function (h) { return ringR(h) * ay; });

    var link = root.append('g').attr('aria-hidden', 'true').selectAll('path').data(links).join('path')
      .attr('class', function (l) { return 'og-link ' + l.type; })
      .attr('fill', 'none')
      .attr('marker-end', function (l) { return l.type === 'prop' ? 'url(#og-arrow)' : null; });

    // MemeConcept: a paper disc inside the meme ring (the lines end on the ring), the caption, the count
    var hubG = root.append('g').attr('class', 'og-hub');
    if (hub) {
      hubG.append('circle').attr('class', 'og-halo').attr('cx', cx).attr('cy', cy).attr('r', HUB_R);
      hubG.append('circle').attr('class', 'og-hub-ring').attr('cx', cx).attr('cy', cy).attr('r', HUB_R);
    }

    // classes, in reading order for the keyboard: ring by ring, clockwise from the top
    function clockwise(d) { var a = Math.atan2(d.y - cy, d.x - cx) + Math.PI / 2; return a < 0 ? a + Math.PI * 2 : a; }
    var classData = classNodes.filter(function (d) { return d.id !== HUB; })
      .sort(function (a, b) { return a.hop - b.hop || clockwise(a) - clockwise(b); });
    var dotData = nodes.filter(function (d) { return d.kind === 'individual' && !d.meme; });

    var dot = root.append('g').attr('class', 'og-dots').selectAll('g').data(dotData).join('g')
      .attr('class', function (d) { return 'og-node individual' + (d.color ? ' tinted' : ''); })
      .style('--c', function (d) { return d.color; });
    dot.append('circle').attr('r', 3.5);
    dot.append('text').attr('y', 4).text(function (d) { return d.label; });

    var node = root.append('g').attr('class', 'og-classes').selectAll('g').data(classData).join('g')
      .attr('class', function (d) { return 'og-node ' + (d.kind === 'external' ? 'external' : 'memo') + (d.color ? ' tinted' : ''); })
      .attr('tabindex', 0).attr('role', 'button')
      .attr('aria-label', function (d) { return d.label + (d.count ? ', ' + d.count.toLocaleString() + ' individuals' : ''); })
      .style('--c', function (d) { return d.color; })
      .call(d3.drag()
        .on('drag', function (e, d) {
          d.x += e.dx; d.y += e.dy;
          (fans[d.id] || []).forEach(function (m) { m.x += e.dx; m.y += e.dy; });
          render();
        }));
    // a hit area over the square and its name (44 px tall on touch screens), then the focus ring
    node.append('rect').attr('class', 'og-hit');
    node.append('rect').attr('class', 'og-focus')
      .attr('x', function (d) { return -d.side / 2 - 5; }).attr('y', function (d) { return -d.side / 2 - 5; })
      .attr('width', function (d) { return d.side + 10; }).attr('height', function (d) { return d.side + 10; });
    node.append('rect').attr('class', 'og-mark')
      .attr('x', function (d) { return -d.side / 2; }).attr('y', function (d) { return -d.side / 2; })
      .attr('width', function (d) { return d.side; }).attr('height', function (d) { return d.side; });
    var label = node.append('text').attr('y', 4).text(function (d) { return d.label; });
    label.filter(function (d) { return d.count; }).append('tspan')
      .attr('class', 'og-count').text(function (d) { return ' ' + d.count.toLocaleString(); });

    // the caption in the middle (top text, bottom text) and the memes on the ring
    var cap = null;
    if (hub) {
      cap = hubG.append('g').attr('class', 'og-node memo og-hub-node').datum(hub)
        .attr('tabindex', 0).attr('role', 'button')
        .attr('aria-label', 'MemeConcept, ' + (hub.count || 0).toLocaleString() + ' individuals');
      cap.append('circle').attr('class', 'og-hub-hit').attr('cx', cx).attr('cy', cy).attr('r', HUB_R - THUMB_R - 4);
      cap.append('text').attr('class', 'og-caption').attr('x', cx).attr('y', cy - 6).attr('text-anchor', 'middle').text('MEME');
      cap.append('text').attr('class', 'og-caption').attr('x', cx).attr('y', cy + 20).attr('text-anchor', 'middle').text('CONCEPT');
      cap.append('text').attr('class', 'og-hub-count').attr('x', cx).attr('y', cy + 40).attr('text-anchor', 'middle')
        .text((hub.count || 0).toLocaleString());
    }
    var thumb = hubG.append('g').attr('class', 'og-memes').selectAll('a').data(memes).join('a')
      .attr('class', 'og-node individual og-meme')
      .attr('href', function (d) { return '#meme/' + encodeURIComponent(d.slug); })
      .attr('aria-label', function (d) { return 'Open ' + d.label; });
    thumb.append('circle').attr('class', 'og-meme-focus').attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; }).attr('r', THUMB_R + 4);
    thumb.append('circle').attr('class', 'og-meme-bg').attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; }).attr('r', THUMB_R);
    thumb.append('image')
      .attr('href', function (d) { return thumbFor(d.slug); })
      .attr('x', function (d) { return d.x - THUMB_R; }).attr('y', function (d) { return d.y - THUMB_R; })
      .attr('width', THUMB_R * 2).attr('height', THUMB_R * 2)
      .attr('preserveAspectRatio', 'xMidYMid slice').attr('clip-path', 'url(#og-thumb-clip)')
      .on('error', function () { this.remove(); });
    thumb.append('circle').attr('class', 'og-meme-ring').attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; }).attr('r', THUMB_R);

    // property names sit on the visible part of each line, above the meme disc
    var plabel = root.append('g').attr('aria-hidden', 'true').selectAll('text').data(links.filter(function (l) { return l.type === 'prop'; })).join('text')
      .attr('class', 'og-plabel').attr('text-anchor', 'middle').text(function (l) { return l.label; });

    var toggle = document.getElementById('onto-graph-individuals');
    if (toggle) toggle.addEventListener('change', function () { box.classList.toggle('no-individuals', !toggle.checked); });

    var DEFAULT_INFO = 'Select a class to see its description and properties.';
    function focus(d) {
      if (!d) { box.classList.remove('focus'); info.textContent = DEFAULT_INFO; return; }
      var meme = d.meme ? d : null;
      if (d.kind === 'individual') d = d.cls;
      var near = new Set([d.id]);
      links.forEach(function (l) { if (l.source.id === d.id || l.target.id === d.id) { near.add(l.source.id); near.add(l.target.id); } });
      box.classList.add('focus');
      root.selectAll('.og-node').classed('on', function (m) { return m && near.has(m.id); });
      link.classed('on', function (l) { return l.source.id === d.id || l.target.id === d.id; });
      plabel.classed('on', function (l) { return l.source.id === d.id || l.target.id === d.id; });
      if (meme) { info.innerHTML = '<b>' + esc(meme.label) + '</b>. Opens the meme page.'; return; }
      var props = links.filter(function (l) { return l.type === 'prop' && l.source.id === d.id; }).map(function (l) { return l.label; });
      var examples = (d.sample || []).filter(function (x) { return !(d.id === HUB && NOT_SHOWN[String(x.label).replace(/^_+/, '')]); })
        .map(function (x) { return d.id === HUB ? nameFor(x.label) : x.label; }).filter(function (x) { return !/�/.test(x); });
      info.innerHTML = '<b>' + esc(d.label) + '</b> <span class="og-info-iri">' + esc(d.id) + '</span>' +
        (d.comment ? '<br>' + esc(d.comment) : '') +
        (props.length ? '<br><span class="og-info-more">Properties: ' + esc(props.join(', ')) + '</span>' : '') +
        (d.count ? '<br><span class="og-info-more">' + d.count.toLocaleString() + ' individual' + (d.count === 1 ? '' : 's') +
          (examples.length ? ', e.g. ' + esc(examples.slice(0, 4).join(', ')) : '') + '</span>' : '');
    }
    // pointer: classes, the caption and the dots; keyboard: classes, the caption and the memes only
    node.on('mouseenter focus', function (e, d) { focus(d); }).on('mouseleave blur', function () { focus(null); })
      .on('click', function (e, d) { focus(d); });
    if (cap) cap.on('mouseenter focus', function (e, d) { focus(d); }).on('mouseleave blur', function () { focus(null); });
    dot.on('mouseenter', function (e, d) { focus(d); }).on('mouseleave', function () { focus(null); });
    thumb.on('mouseenter focus', function (e, d) { focus(d); }).on('mouseleave blur', function () { focus(null); });

    // a point at distance r from a node's centre towards another point (lines end on shapes, not inside)
    function edgePoint(n, toward, r) {
      var dx = toward.x - n.x, dy = toward.y - n.y, dist = Math.hypot(dx, dy) || 1;
      return { x: n.x + dx / dist * r, y: n.y + dy / dist * r };
    }
    function radiusOf(n, isTarget) {
      if (n.id === HUB) return HUB_R + 2;
      if (n.kind === 'individual') return 3.5;
      return isTarget ? n.side / 2 + 3 : 0;
    }
    function render() {
      link.each(function (l) {
        var a = edgePoint(l.source, l.target, radiusOf(l.source, false)), b = edgePoint(l.target, l.source, radiusOf(l.target, true));
        l.a = a; l.b = b;
        var d;
        if (l.type !== 'prop') d = 'M' + a.x + ',' + a.y + 'L' + b.x + ',' + b.y;
        else {
          var dx = b.x - a.x, dy = b.y - a.y;
          l.mx = (a.x + b.x) / 2 - dy * 0.06; l.my = (a.y + b.y) / 2 + dx * 0.06;
          d = 'M' + a.x + ',' + a.y + 'Q' + ((a.x + b.x) / 2 - dy * 0.12) + ',' + ((a.y + b.y) / 2 + dx * 0.12) + ' ' + b.x + ',' + b.y;
        }
        this.setAttribute('d', d);
      });
      plabel.attr('x', function (l) { return l.mx; }).attr('y', function (l) { return l.my; });
      node.attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; });
      dot.attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; });
      // names point away from the meme: right of the class on the right half, left of it on the left half
      label.attr('text-anchor', function (d) { return d.x < cx - 4 ? 'end' : 'start'; })
        .attr('x', function (d) { var off = d.side / 2 + 6; return d.x < cx - 4 ? -off : off; });
      dot.select('text').attr('x', 7);
      node.select('.og-hit').each(function (d) {
        var w = labelWidth(d), off = d.side / 2 + 6, left = d.x < cx - 4, hh = COARSE ? 44 : 26;
        var x0 = left ? -off - w - 4 : -d.side / 2 - 4, x1 = left ? d.side / 2 + 4 : off + w + 4;
        this.setAttribute('x', x0); this.setAttribute('width', x1 - x0);
        this.setAttribute('y', -hh / 2); this.setAttribute('height', hh);
      });
    }
    render();

    // fit the finished drawing (labels included) into the box, centred, never enlarged; Reset returns here.
    // Where it would have to shrink below 80 % it opens at full size on MemeConcept instead, and people pan
    var bb = root.node().getBBox(), pad = 24;
    var k = Math.min(1, (W - pad * 2) / bb.width, (H - pad * 2) / bb.height);
    var fx = bb.x + bb.width / 2, fy = bb.y + bb.height / 2;
    if (k < 0.8) { k = 1; fx = cx; fy = cy; }
    home = d3.zoomIdentity.translate(W / 2 - k * fx, H / 2 - k * fy).scale(k);
    svg.call(zoom.transform, home);
    svgEl.dataset.fit = k.toFixed(2);
    box.classList.add('og-ready');
  }

  // the ontology page is hidden until opened; draw once it is visible
  new ResizeObserver(start).observe(svgEl);
  start();
})();
