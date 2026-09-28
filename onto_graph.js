/* The MEMO ontology as a 2D graph (Ontology page).
   Data: onto_graph.json, extracted from meme_ontology_unpopulated.ttl — classes, subclass links and
   object properties (inverse properties are left out so each relation is drawn once). */
(function () {
  var svgEl = document.getElementById('onto-graph-svg');
  if (!svgEl || !window.d3) return;
  var started = false;

  function start() {
    if (started || svgEl.getBoundingClientRect().width === 0) return;
    started = true;
    fetch('onto_graph.json').then(function (r) { return r.json(); }).then(draw);
  }

  function draw(data) {
    var INVERSE = /^is[A-Z]/;
    var links = data.links.filter(function (l) { return l.type === 'sub' || !INVERSE.test(l.label); });
    var nodes = data.nodes.map(function (n) { return Object.assign({}, n); });
    var byId = {};
    nodes.forEach(function (n) { byId[n.id] = n; n.deg = 0; });
    links = links.filter(function (l) { return byId[l.source] && byId[l.target]; }).map(function (l) { return Object.assign({}, l); });
    links.forEach(function (l) { byId[l.source].deg++; byId[l.target].deg++; });

    var box = document.getElementById('onto-graph');
    var info = document.getElementById('onto-graph-info');
    var W = svgEl.clientWidth, H = svgEl.clientHeight;
    var svg = d3.select(svgEl).attr('viewBox', [0, 0, W, H]);
    svg.append('defs').append('marker')
      .attr('id', 'og-arrow').attr('viewBox', '0 -4 8 8').attr('refX', 8).attr('refY', 0)
      .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#8a8378');
    var root = svg.append('g');
    svg.call(d3.zoom().scaleExtent([0.4, 3]).on('zoom', function (e) { root.attr('transform', e.transform); }));

    var sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(function (d) { return d.id; })
        .distance(function (l) { return l.type === 'sub' ? 60 : 130; }).strength(function (l) { return l.type === 'sub' ? 0.9 : 0.25; }))
      .force('charge', d3.forceManyBody().strength(-520))
      .force('collide', d3.forceCollide().radius(function (d) { return 10 + d.label.length * 3.4; }))
      .force('x', d3.forceX(W / 2).strength(0.04))
      .force('y', d3.forceY(H / 2).strength(0.06));

    var link = root.append('g').selectAll('path').data(links).join('path')
      .attr('class', function (l) { return 'og-link ' + l.type; })
      .attr('fill', 'none')
      .attr('marker-end', function (l) { return l.type === 'prop' ? 'url(#og-arrow)' : null; });
    var plabel = root.append('g').selectAll('text').data(links.filter(function (l) { return l.type === 'prop'; })).join('text')
      .attr('class', 'og-plabel').attr('text-anchor', 'middle').text(function (l) { return l.label; });

    var node = root.append('g').selectAll('g').data(nodes).join('g')
      .attr('class', function (d) { return 'og-node ' + (d.kind === 'external' ? 'external' : 'memo'); })
      .attr('tabindex', 0).attr('role', 'button')
      .attr('aria-label', function (d) { return d.label; })
      .call(d3.drag()
        .on('start', function (e, d) { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', function (e, d) { d.fx = e.x; d.fy = e.y; })
        .on('end', function (e, d) { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    node.append('rect').attr('x', -6).attr('y', -6).attr('width', 12).attr('height', 12);
    node.append('text').attr('x', 10).attr('y', 4).text(function (d) { return d.label; });

    function focus(d) {
      if (!d) { box.classList.remove('focus'); info.textContent = 'Select a class to see its description and properties.'; return; }
      var near = new Set([d.id]);
      links.forEach(function (l) { if (l.source.id === d.id || l.target.id === d.id) { near.add(l.source.id); near.add(l.target.id); } });
      box.classList.add('focus');
      node.classed('on', function (n) { return near.has(n.id); });
      link.classed('on', function (l) { return l.source.id === d.id || l.target.id === d.id; });
      plabel.classed('on', function (l) { return l.source.id === d.id || l.target.id === d.id; });
      var props = links.filter(function (l) { return l.type === 'prop' && l.source.id === d.id; }).map(function (l) { return l.label; });
      info.innerHTML = '<b>' + d.id + '</b> ' + (d.comment ? '— ' + d.comment.replace(/</g, '&lt;') : '') +
        (props.length ? '<br><span style="color:var(--muted)">Properties: ' + props.join(', ') + '</span>' : '');
    }
    node.on('mouseenter focus', function (e, d) { focus(d); })
      .on('mouseleave blur', function () { focus(null); })
      .on('click', function (e, d) { focus(d); });

    sim.on('tick', function () {
      nodes.forEach(function (d) { d.x = Math.max(20, Math.min(W - 140, d.x)); d.y = Math.max(20, Math.min(H - 20, d.y)); });
      link.attr('d', function (l) {
        var sx = l.source.x, sy = l.source.y, tx = l.target.x, ty = l.target.y;
        if (l.type === 'sub') return 'M' + sx + ',' + sy + 'L' + tx + ',' + ty;
        var dx = tx - sx, dy = ty - sy, dist = Math.hypot(dx, dy) || 1;
        var ex = tx - (dx / dist) * 9, ey = ty - (dy / dist) * 9; // stop at the target's edge
        return 'M' + sx + ',' + sy + 'Q' + ((sx + ex) / 2 - dy * 0.12) + ',' + ((sy + ey) / 2 + dx * 0.12) + ' ' + ex + ',' + ey;
      });
      plabel.attr('x', function (l) { return (l.source.x + l.target.x) / 2 - (l.target.y - l.source.y) * 0.06; })
        .attr('y', function (l) { return (l.source.y + l.target.y) / 2 + (l.target.x - l.source.x) * 0.06; });
      node.attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; });
    });
  }

  // the ontology page is hidden until opened; draw once it is visible
  new ResizeObserver(start).observe(svgEl);
  start();
})();
