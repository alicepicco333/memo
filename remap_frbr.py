"""Remap FRBR levels in meme ontology.

Changes applied
---------------
1. memo:MemeConcept  subClassOf Work  →  subClassOf Expression
   Rationale: MemeConcept is the KnowYourMeme-documented template — the named,
   community-recognised form.  That is FRBR Expression, not Work.

2. Add memo:MemeIdea  subClassOf Work
   Rationale: the abstract Dawkinsian meme — the shared cultural concept that
   exists independently of any specific instantiation — belongs at Work level.

3. Add memo:VariantInstance  subClassOf Manifestation
   Rationale: a specific variant image (particular caption, drawn version,
   localisation) is a concrete physical realisation of the Expression-level
   template.  That is FRBR Manifestation.

4. Add memo:isVariantOf  ObjectProperty  (domain: VariantInstance, range: MemeConcept)

5. Add data properties  memo:photoId, memo:photoURL, memo:variantUploader

6. Load variants_metadata.json and create 391 VariantInstance individuals linked
   to their parent MemeConcept via memo:isVariantOf.

7. Serialise updated ontology as OWL/XML and Turtle.
"""

import json
import re
from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL, XSD

# ── paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
OWL_PATH = BASE_DIR / "meme_ontology.owl"
TTL_PATH = BASE_DIR / "meme_ontology.ttl"
VARIANTS_PATH = BASE_DIR / "variants_metadata.json"

BASE_URI = "http://www.semanticweb.org/meme-ontology#"
MEME = Namespace(BASE_URI)

# ── helpers ───────────────────────────────────────────────────────────────────

def uri_from_slug(slug: str) -> URIRef:
    """Encode a meme-name slug to the IRI used for MemeConcept individuals.

    Slugs that start with a digit are prefixed with '_' in the ontology IRI
    (OWL local names cannot begin with a digit).  Returns the best matching
    IRI found in *memo_concept_iris* (populated after the graph is loaded),
    or a best-guess IRI if no match is found.
    """
    # Try exact match first
    exact = URIRef(BASE_URI + slug)
    if exact in memo_concept_iris:
        return exact
    # Try underscore-prefixed (digit-starting slugs)
    prefixed = URIRef(BASE_URI + "_" + slug)
    if prefixed in memo_concept_iris:
        return prefixed
    # Try prefix match (truncated slugs in metadata)
    for iri in memo_concept_iris:
        local = str(iri)[len(BASE_URI):]
        if local.startswith(slug) or slug.startswith(local):
            return iri
    # Fallback — no match; caller checks parent_exists
    return exact

# ── load ──────────────────────────────────────────────────────────────────────

print("Loading ontology …")
g = Graph()
g.parse(str(OWL_PATH), format="xml")
print(f"  {len(g):,} triples loaded")

# Build a set of all existing MemeConcept individual IRIs for fast lookup
memo_concept_iris: set[URIRef] = {
    s for s, _, o in g.triples((None, RDF.type, MEME.MemeConcept))
    if isinstance(s, URIRef)
}

# ── 1. MemeConcept: move from Work to Expression ──────────────────────────────

old_parent = MEME.Work
new_parent = MEME.Expression

triple_old = (MEME.MemeConcept, RDFS.subClassOf, old_parent)
if triple_old in g:
    g.remove(triple_old)
    g.add((MEME.MemeConcept, RDFS.subClassOf, new_parent))
    print("  MemeConcept subClassOf: Work → Expression")
else:
    # Already updated or wrong parent — just ensure the correct triple exists
    g.add((MEME.MemeConcept, RDFS.subClassOf, new_parent))
    print("  MemeConcept subClassOf Expression (no Work triple found, added)")

# Also fix the misleading rdfs:label ("Meme" → "Meme Template") to reflect
# that this class represents the documented template, not the abstract idea.
g.remove((MEME.MemeConcept, RDFS.label, Literal("Meme")))
g.add((MEME.MemeConcept, RDFS.label, Literal("Meme Template")))

# ── 2. Add memo:MemeIdea  (Work level) ───────────────────────────────────────

if (MEME.MemeIdea, RDF.type, OWL.Class) not in g:
    g.add((MEME.MemeIdea, RDF.type, OWL.Class))
    g.add((MEME.MemeIdea, RDFS.subClassOf, MEME.Work))
    g.add((MEME.MemeIdea, RDFS.label, Literal("Meme Idea")))
    print("  Added memo:MemeIdea  (subClassOf Work)")
else:
    print("  memo:MemeIdea already present — skipped")

# ── 3. Add memo:VariantInstance  (Manifestation level) ───────────────────────

if (MEME.VariantInstance, RDF.type, OWL.Class) not in g:
    g.add((MEME.VariantInstance, RDF.type, OWL.Class))
    g.add((MEME.VariantInstance, RDFS.subClassOf, MEME.Manifestation))
    g.add((MEME.VariantInstance, RDFS.label, Literal("Variant Instance")))
    print("  Added memo:VariantInstance  (subClassOf Manifestation)")
else:
    print("  memo:VariantInstance already present — skipped")

# ── 4. Add memo:isVariantOf  ObjectProperty ───────────────────────────────────

if (MEME.isVariantOf, RDF.type, OWL.ObjectProperty) not in g:
    g.add((MEME.isVariantOf, RDF.type, OWL.ObjectProperty))
    g.add((MEME.isVariantOf, RDFS.domain, MEME.VariantInstance))
    g.add((MEME.isVariantOf, RDFS.range, MEME.MemeConcept))
    g.add((MEME.isVariantOf, RDFS.label, Literal("isVariantOf")))
    print("  Added memo:isVariantOf  ObjectProperty")
else:
    print("  memo:isVariantOf already present — skipped")

# ── 5. Add new data properties ────────────────────────────────────────────────

NEW_PROPS = [
    (MEME.photoId,       XSD.string,  "photoId"),
    (MEME.photoURL,      XSD.string,  "photoURL"),
    (MEME.variantUploader, XSD.string,  "variantUploader"),
]

for prop, dtype, label in NEW_PROPS:
    if (prop, RDF.type, OWL.DatatypeProperty) not in g:
        g.add((prop, RDF.type, OWL.DatatypeProperty))
        g.add((prop, RDFS.domain, MEME.VariantInstance))
        g.add((prop, RDFS.range, dtype))
        g.add((prop, RDFS.label, Literal(label)))
        print(f"  Added data property  memo:{label}")

# ── 6. Load variants and create VariantInstance individuals ───────────────────

print("\nLoading variants …")
with open(VARIANTS_PATH, encoding="utf-8") as fh:
    variants = json.load(fh)

print(f"  {len(variants)} variant entries")

added = 0
skipped = 0
fixed_links = 0
missing_parent = []

for entry in variants:
    photo_id   = str(entry.get("photo_id", ""))
    photo_url  = entry.get("photo_url", "")
    title      = entry.get("title", "")
    author     = entry.get("author", "")
    image_url  = entry.get("image_url", "")
    filename   = entry.get("filename", "")
    folder     = entry.get("folder", "")

    # Build a stable IRI: memo:variant_{photo_id}
    ind = URIRef(BASE_URI + f"variant_{photo_id}")

    # Look up the parent MemeConcept by folder slug
    parent = uri_from_slug(folder)
    parent_exists = parent in memo_concept_iris

    if (ind, RDF.type, MEME.VariantInstance) in g:
        # Individual already exists — only backfill missing isVariantOf link
        if parent_exists and (ind, MEME.isVariantOf, parent) not in g:
            g.add((ind, MEME.isVariantOf, parent))
            fixed_links += 1
        skipped += 1
        continue

    # Assert the individual
    g.add((ind, RDF.type, OWL.NamedIndividual))
    g.add((ind, RDF.type, MEME.VariantInstance))

    if title:
        g.add((ind, RDFS.label, Literal(title)))

    if photo_id:
        g.add((ind, MEME.photoId, Literal(photo_id, datatype=XSD.string)))

    if photo_url:
        g.add((ind, MEME.photoURL, Literal(photo_url, datatype=XSD.string)))

    if image_url:
        g.add((ind, MEME.imageURL, Literal(image_url, datatype=XSD.string)))

    if filename:
        g.add((ind, MEME.imageFilename, Literal(filename, datatype=XSD.string)))

    if author:
        g.add((ind, MEME.variantUploader, Literal(author, datatype=XSD.string)))

    # Link to parent MemeConcept
    if parent_exists:
        g.add((ind, MEME.isVariantOf, parent))
    else:
        missing_parent.append(folder)

    added += 1

print(f"  Added:        {added} new VariantInstance individuals")
print(f"  Skipped:      {skipped} (already existed)")
print(f"  Fixed links:  {fixed_links} missing isVariantOf triples backfilled")
if missing_parent:
    unique_missing = sorted(set(missing_parent))
    print(f"  WARNING: {len(unique_missing)} parent MemeConcept(s) not found in ontology:")
    for m in unique_missing:
        print(f"    - {m}")

# ── 7. Serialise ──────────────────────────────────────────────────────────────

print(f"\nTotal triples: {len(g):,}")

print(f"Serialising OWL/XML → {OWL_PATH.name} …")
g.serialize(str(OWL_PATH), format="xml")
print("  Done.")

print(f"Serialising Turtle  → {TTL_PATH.name} …")
g.bind("meme", MEME)
g.serialize(str(TTL_PATH), format="turtle")
print("  Done.")

print("\nAll changes applied successfully.")
