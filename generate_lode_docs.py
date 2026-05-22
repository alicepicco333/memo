"""
Generate LODE-style HTML documentation from meme_ontology.ttl using rdflib.
Writes output to documentation.html.
"""
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, URIRef, Literal

BASE   = Path(__file__).parent
TTL    = BASE / "meme_ontology.ttl"
OUT    = BASE / "documentation.html"

MEME = Namespace("http://www.semanticweb.org/meme-ontology#")

g = Graph()
print("Parsing ontology…")
g.parse(str(TTL), format="turtle")
print(f"  {len(g)} triples loaded")

def local(uri):
    s = str(uri)
    for ns, prefix in [
        ("http://www.semanticweb.org/meme-ontology#", "memo:"),
        ("http://www.w3.org/2002/07/owl#",            "owl:"),
        ("http://www.w3.org/2000/01/rdf-schema#",     "rdfs:"),
        ("http://www.w3.org/2001/XMLSchema#",         "xsd:"),
    ]:
        if s.startswith(ns):
            return prefix + s[len(ns):]
    return s

def label(uri):
    for lbl in g.objects(uri, RDFS.label):
        return str(lbl)
    return local(uri).split(":")[-1]

def comment(uri):
    for c in g.objects(uri, RDFS.comment):
        return str(c)
    return ""

def superclasses(cls):
    return [str(sc) for sc in g.objects(cls, RDFS.subClassOf)
            if isinstance(sc, URIRef)]

def subclasses(cls):
    return [str(sc) for sc in g.subjects(RDFS.subClassOf, cls)
            if isinstance(sc, URIRef)]

def anchor(uri):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", local(uri))

def iri_link(uri):
    lbl = local(uri)
    anc = anchor(uri)
    return f'<a href="#{anc}" class="iri-ref">{esc(lbl)}</a>'

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

# ── Collect schema elements ──────────────────────────────────────────────────

classes = sorted(
    [s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)],
    key=lambda u: label(u).lower()
)
obj_props = sorted(
    [s for s in g.subjects(RDF.type, OWL.ObjectProperty) if isinstance(s, URIRef)],
    key=lambda u: label(u).lower()
)
data_props = sorted(
    [s for s in g.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(s, URIRef)],
    key=lambda u: label(u).lower()
)
ann_props = sorted(
    [s for s in g.subjects(RDF.type, OWL.AnnotationProperty) if isinstance(s, URIRef)],
    key=lambda u: label(u).lower()
)

# Group named individuals by their most specific class
def named_individuals_for_class(cls_uri):
    return sorted(
        [s for s in g.subjects(RDF.type, URIRef(cls_uri))
         if (URIRef(str(s)), RDF.type, OWL.NamedIndividual) in g
         and str(s) != str(cls_uri)],
        key=lambda u: label(u).lower()
    )

# ── Build HTML ───────────────────────────────────────────────────────────────

def section_toc_entry(sec_id, title):
    return f'<li><a href="#{sec_id}">{esc(title)}</a></li>'

def class_block(cls_uri):
    cls = URIRef(cls_uri)
    anc = anchor(cls)
    lbl = label(cls)
    cmt = comment(cls)
    sups = superclasses(cls)
    subs = subclasses(cls)

    # Find object properties where this class is domain or range
    as_domain = [(p, list(g.objects(p, URIRef(MEME+"range"))) or list(g.objects(p, RDFS.range)))
                 for p in obj_props + data_props
                 if (p, URIRef(MEME+"domain"), cls) in g or (p, RDFS.domain, cls) in g]
    # Find object properties where this class is range
    as_range  = [p for p in obj_props
                 if (p, URIRef(MEME+"range"), cls) in g or (p, RDFS.range, cls) in g]

    inds = named_individuals_for_class(cls_uri)

    html = f'<div class="entity-block" id="{anc}">\n'
    html += f'  <h3 class="entity-title"><span class="entity-kind kind-class">Class</span>{esc(lbl)}</h3>\n'
    html += f'  <div class="entity-iri">{esc(str(cls))}</div>\n'
    if cmt:
        html += f'  <p class="entity-desc">{esc(cmt)}</p>\n'

    if sups:
        html += '  <table class="entity-table"><tbody>\n'
        html += '    <tr><th>Super-classes</th><td>' + " · ".join(iri_link(s) for s in sups) + '</td></tr>\n'
        if subs:
            html += '    <tr><th>Sub-classes</th><td>' + " · ".join(iri_link(s) for s in subs) + '</td></tr>\n'
        if inds:
            html += f'    <tr><th>Individuals</th><td>{len(inds)} named individual{"s" if len(inds)!=1 else ""}</td></tr>\n'
        html += '  </tbody></table>\n'

    if inds and len(inds) <= 40:
        html += '  <details class="ind-list"><summary>Named individuals</summary><ul>\n'
        for ind in inds:
            ilbl = label(ind)
            icmt = comment(ind)
            html += f'    <li><code>{esc(local(ind))}</code>'
            if ilbl and ilbl != local(ind).split(":")[-1]:
                html += f' — {esc(ilbl)}'
            if icmt:
                html += f'<br><span class="ind-note">{esc(icmt)}</span>'
            html += '</li>\n'
        html += '  </ul></details>\n'
    elif inds:
        html += f'  <p class="ind-count">{len(inds)} named individuals (too many to list inline).</p>\n'

    html += '</div>\n'
    return html

def prop_block(prop_uri, kind):
    prop = URIRef(prop_uri)
    anc  = anchor(prop)
    lbl  = label(prop)
    cmt  = comment(prop)

    domain_vals = list(g.objects(prop, RDFS.domain)) or list(g.objects(prop, URIRef(str(MEME)+"domain")))
    range_vals  = list(g.objects(prop, RDFS.range))  or list(g.objects(prop, URIRef(str(MEME)+"range")))

    html  = f'<div class="entity-block" id="{anc}">\n'
    html += f'  <h3 class="entity-title"><span class="entity-kind kind-prop">{esc(kind)}</span>{esc(lbl)}</h3>\n'
    html += f'  <div class="entity-iri">{esc(str(prop))}</div>\n'
    if cmt:
        html += f'  <p class="entity-desc">{esc(cmt)}</p>\n'

    rows = []
    if domain_vals:
        rows.append(("Domain", " · ".join(iri_link(d) for d in domain_vals if isinstance(d, URIRef))))
    if range_vals:
        rows.append(("Range", " · ".join(
            iri_link(r) if isinstance(r, URIRef) else f'<code>{esc(local(r))}</code>'
            for r in range_vals
        )))
    if rows:
        html += '  <table class="entity-table"><tbody>\n'
        for th, td in rows:
            html += f'    <tr><th>{esc(th)}</th><td>{td}</td></tr>\n'
        html += '  </tbody></table>\n'

    html += '</div>\n'
    return html

# Build class count stats
stats = {
    "Classes":              len(classes),
    "Object properties":    len(obj_props),
    "Datatype properties":  len(data_props),
    "Named individuals":    sum(1 for _ in g.subjects(RDF.type, OWL.NamedIndividual)),
    "Total triples":        len(g),
}

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
  :root {
    --bg:#f7f7f5; --surface:#fff; --border:#e0e0dc; --text:#111;
    --muted:#666; --accent:#1a1a1a; --accent2:#1a3d6b;
    --nav-w:270px; --prop:#2e6b3e; --cls:#1a3d6b; --ind:#7b3b00;
    font-size:14px;
  }
  *, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
  html { scroll-behavior:smooth; }
  body { font-family:'Segoe UI',system-ui,sans-serif; color:var(--text);
         background:var(--bg); line-height:1.7; display:flex; min-height:100vh; }

  /* sidebar */
  nav.lode-nav {
    position:fixed; top:0; left:0; width:var(--nav-w);
    height:100vh; overflow-y:auto;
    background:var(--surface); border-right:1px solid var(--border);
    padding:0 0 48px; display:flex; flex-direction:column;
  }
  .nav-brand {
    padding:20px 20px 16px; font-size:.75rem; font-weight:900;
    letter-spacing:.14em; text-transform:uppercase;
    border-bottom:1px solid var(--border);
  }
  .nav-brand a { color:var(--accent); text-decoration:none; }
  .nav-section {
    padding:14px 20px 4px; font-size:.6rem; font-weight:700;
    letter-spacing:.14em; text-transform:uppercase; color:var(--muted);
  }
  nav.lode-nav a.nav-item {
    display:block; padding:4px 20px 4px 24px; font-size:.78rem;
    color:var(--muted); text-decoration:none;
    border-left:3px solid transparent;
    transition:color .12s, border-color .12s;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  }
  nav.lode-nav a.nav-item:hover { color:var(--accent); border-left-color:var(--border); }
  nav.lode-nav a.nav-item.active { color:var(--accent2); border-left-color:var(--accent2); font-weight:600; }

  /* main */
  main.lode-main {
    margin-left:var(--nav-w); padding:52px 56px 120px;
    max-width:calc(var(--nav-w) + 820px); width:100%;
  }

  .lode-hero { margin-bottom:40px; }
  .lode-hero h1 { font-size:2rem; font-weight:900; letter-spacing:.04em; margin-bottom:8px; }
  .lode-hero p  { color:var(--muted); font-size:.88rem; }
  .lode-meta { display:flex; flex-wrap:wrap; gap:16px; margin-top:18px; }
  .lode-meta-item { background:var(--surface); border:1px solid var(--border);
    border-radius:4px; padding:10px 18px; }
  .lode-meta-item .meta-num { font-size:1.3rem; font-weight:900; display:block; }
  .lode-meta-item .meta-lbl { font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }

  /* section headings */
  h2.lode-section {
    font-size:1rem; font-weight:800; text-transform:uppercase; letter-spacing:.1em;
    border-bottom:2px solid var(--border); padding-bottom:6px;
    margin:52px 0 18px; color:var(--accent);
    scroll-margin-top:20px;
  }

  /* entity blocks */
  .entity-block {
    background:var(--surface); border:1px solid var(--border);
    border-radius:4px; padding:20px 24px 18px; margin-bottom:16px;
    scroll-margin-top:20px;
  }
  .entity-title {
    font-size:.92rem; font-weight:700; margin-bottom:4px;
    display:flex; align-items:center; gap:8px;
  }
  .entity-kind {
    font-size:.62rem; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; border-radius:3px;
    padding:2px 7px; flex-shrink:0;
  }
  .kind-class { background:#dce8f7; color:var(--cls); }
  .kind-prop  { background:#dceee3; color:var(--prop); }
  .kind-ann   { background:#f5e6d0; color:var(--ind); }
  .entity-iri {
    font-family:'Consolas',monospace; font-size:.72rem; color:var(--muted);
    word-break:break-all; margin-bottom:8px;
  }
  .entity-desc { font-size:.82rem; color:#444; margin-bottom:10px; }
  .entity-table { border-collapse:collapse; font-size:.78rem; width:100%; }
  .entity-table th {
    text-align:left; padding:4px 12px 4px 0; font-weight:600; color:var(--muted);
    width:140px; vertical-align:top; white-space:nowrap;
  }
  .entity-table td { padding:4px 0; color:#333; }
  .iri-ref { color:var(--accent2); text-decoration:none; font-family:'Consolas',monospace; font-size:.78rem; }
  .iri-ref:hover { text-decoration:underline; }

  /* individuals list */
  details.ind-list { margin-top:10px; font-size:.78rem; }
  details.ind-list summary { cursor:pointer; color:var(--muted); font-weight:600; padding:4px 0; }
  details.ind-list ul { padding-left:18px; margin-top:6px; }
  details.ind-list li { margin-bottom:3px; color:#333; }
  .ind-note { color:var(--muted); font-size:.72rem; }
  .ind-count { font-size:.78rem; color:var(--muted); margin-top:6px; }
"""

# ── Build ToC entries ─────────────────────────────────────────────────────────
def toc_entries(items, prefix=""):
    parts = []
    for uri in items:
        lbl = label(URIRef(uri) if isinstance(uri, str) else uri)
        anc = anchor(URIRef(uri) if isinstance(uri, str) else uri)
        parts.append(f'<a class="nav-item" href="#{anc}">{esc(lbl)}</a>')
    return "\n".join(parts)

# ── Assemble page ─────────────────────────────────────────────────────────────
nav_html = f"""
<nav class="lode-nav">
  <div class="nav-brand"><a href="meme_viz.html">← The Meme Ontology</a></div>
  <div class="nav-section">Overview</div>
  <a class="nav-item" href="#overview">Ontology summary</a>
  <div class="nav-section">Classes ({len(classes)})</div>
  {toc_entries(classes)}
  <div class="nav-section">Object Properties ({len(obj_props)})</div>
  {toc_entries(obj_props)}
  <div class="nav-section">Datatype Properties ({len(data_props)})</div>
  {toc_entries(data_props)}
"""
if ann_props:
    nav_html += f"""
  <div class="nav-section">Annotation Properties ({len(ann_props)})</div>
  {toc_entries(ann_props)}
"""
nav_html += "</nav>\n"

meta_items = "".join(
    f'<div class="lode-meta-item"><span class="meta-num">{v:,}</span>'
    f'<span class="meta-lbl">{k}</span></div>'
    for k, v in stats.items()
)

classes_html  = "\n".join(class_block(str(c)) for c in classes)
obj_html      = "\n".join(prop_block(str(p), "Object Property")   for p in obj_props)
data_html     = "\n".join(prop_block(str(p), "Datatype Property")  for p in data_props)
ann_html      = "\n".join(prop_block(str(p), "Annotation Property") for p in ann_props) if ann_props else ""

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>The Meme Ontology — Documentation</title>
  <style>{CSS}</style>
</head>
<body>
{nav_html}
<main class="lode-main">
  <div class="lode-hero" id="overview">
    <h1>The Meme Ontology</h1>
    <p>Namespace: <code>http://www.semanticweb.org/meme-ontology#</code> · OWL 2 DL · Turtle serialisation</p>
    <p style="margin-top:6px;color:#444;font-size:.85rem;">
      A formal knowledge representation of 5,000 internet memes combining large-scale image classification
      with semantic ontology design. Includes CLIP-based visual annotations, cultural reference links,
      meme idea descriptions, and transformation annotations on variant instances.
    </p>
    <div class="lode-meta">{meta_items}</div>
  </div>

  <h2 class="lode-section" id="sec-classes">Classes</h2>
  {classes_html}

  <h2 class="lode-section" id="sec-obj">Object Properties</h2>
  {obj_html}

  <h2 class="lode-section" id="sec-data">Datatype Properties</h2>
  {data_html}
{"<h2 class='lode-section' id='sec-ann'>Annotation Properties</h2>" + ann_html if ann_html else ""}
</main>
<script>
  // Highlight active nav item on scroll
  const items = document.querySelectorAll('.entity-block, .lode-hero');
  const navLinks = document.querySelectorAll('nav.lode-nav a.nav-item');
  const io = new IntersectionObserver(entries => {{
    entries.forEach(e => {{
      if (e.isIntersecting) {{
        navLinks.forEach(l => l.classList.remove('active'));
        const link = document.querySelector('nav.lode-nav a[href="#' + e.target.id + '"]');
        if (link) link.classList.add('active');
      }}
    }});
  }}, {{ rootMargin:'-10% 0px -80% 0px' }});
  items.forEach(el => io.observe(el));
</script>
</body>
</html>
"""

OUT.write_text(page, encoding="utf-8")
print(f"\nWrote {OUT.name} ({len(page)//1024} KB)")
print(f"  Classes:             {len(classes)}")
print(f"  Object properties:   {len(obj_props)}")
print(f"  Datatype properties: {len(data_props)}")
print(f"  Annotation props:    {len(ann_props)}")
