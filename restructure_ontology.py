"""Restructure meme_ontology.owl to proper FRBR class hierarchy.

Changes:
- Add memo:Work, memo:Expression, memo:Manifestation, memo:Item as top-level classes
- Make value classes subclasses of the right FRBR level
- Remove old FRBRWork / FRBRExpression / FRBRManifestation / FRBRItem classes
- Remove hasFRBRLevel property and all its usages on meme individuals
- Add hasReference object property
- Add new data properties (memeURL, yearOfOrigin, tags, description, views,
  imageURL, imageFilename, imageFilePath, scrapedAt)
"""

from rdflib import Graph, Namespace, Literal, RDF, RDFS, OWL, XSD

INPUT  = 'meme_ontology.owl'
OUTPUT = 'meme_ontology.owl'

BASE = "http://www.semanticweb.org/meme-ontology#"
MEME = Namespace(BASE)

print("Loading ontology...")
g = Graph()
g.parse(INPUT, format='xml')
print(f"  Loaded {len(g)} triples")

# ── helpers ──────────────────────────────────────────────────────────────────

def remove_all(node):
    """Remove every triple that mentions node as subject or object."""
    for s, p, o in list(g.triples((node, None, None))):
        g.remove((s, p, o))
    for s, p, o in list(g.triples((None, None, node))):
        g.remove((s, p, o))

def remove_predicate(pred):
    """Remove every triple with the given predicate."""
    for s, p, o in list(g.triples((None, pred, None))):
        g.remove((s, p, o))

# ── 1. Add the 4 FRBR-level classes ──────────────────────────────────────────

FRBR_CLASSES = {
    'Work':         MEME.Work,
    'Expression':   MEME.Expression,
    'Manifestation':MEME.Manifestation,
    'Item':         MEME.Item,
}

for label, cls in FRBR_CLASSES.items():
    g.add((cls, RDF.type,    OWL.Class))
    g.add((cls, RDFS.label,  Literal(label)))

print("  Added Work / Expression / Manifestation / Item classes")

# ── 2. Make value classes subclasses of the right FRBR level ─────────────────

VALUE_CLASS_PARENTS = {
    MEME.MemeFormat:      [MEME.Work],
    MEME.OriginPlatform:  [MEME.Work],
    MEME.OriginWork:      [MEME.Work],
    MEME.GeographicRegion:[MEME.Work],
    MEME.TimePeriod:      [MEME.Work],
    MEME.CulturalReference:[MEME.Work, MEME.Expression],   # multiple inheritance
    MEME.ImageType:       [MEME.Manifestation],
    MEME.TextPresence:    [MEME.Manifestation],
    MEME.ColorMode:       [MEME.Manifestation],
    MEME.SubjectMatter:   [MEME.Manifestation],
    MEME.FileFormat:      [MEME.Item],
    MEME.AnimationStatus: [MEME.Item],
}

for cls, parents in VALUE_CLASS_PARENTS.items():
    for parent in parents:
        g.add((cls, RDFS.subClassOf, parent))

print("  Set rdfs:subClassOf for all value classes")

# ── 3. Remove old FRBRWork / FRBRExpression / FRBRManifestation / FRBRItem ────
# Also remove the NamedIndividuals named Work/Expression/Manifestation/Item
# that were previously used as hasFRBRLevel targets.

OLD_FRBR = [
    MEME.FRBRWork, MEME.FRBRExpression, MEME.FRBRManifestation, MEME.FRBRItem,
]
for node in OLD_FRBR:
    remove_all(node)

# Remove the NamedIndividual type from Work/Expression/Manifestation/Item
# (they should only be Classes now)
for cls in FRBR_CLASSES.values():
    g.remove((cls, RDF.type, OWL.NamedIndividual))

print("  Removed old FRBR* classes")

# ── 4. Remove hasFRBRLevel property and all its usages ───────────────────────

hasFRBRLevel = MEME.hasFRBRLevel
# Remove every assertion (e.g. memo:sadopopulism memo:hasFRBRLevel memo:Manifestation)
remove_predicate(hasFRBRLevel)
# Remove the property declaration itself
remove_all(hasFRBRLevel)

print("  Removed hasFRBRLevel property and all usages")

# ── 5. Add hasReference object property ──────────────────────────────────────

hasRef = MEME.hasReference
g.add((hasRef, RDF.type,       OWL.ObjectProperty))
g.add((hasRef, RDFS.domain,    MEME.Meme))
g.add((hasRef, RDFS.range,     MEME.CulturalReference))
g.add((hasRef, RDFS.label,     Literal("hasReference")))

print("  Added hasReference object property")

# ── 6. Add new data properties ────────────────────────────────────────────────
# (existing ones like clipImageTypeScore are kept unchanged)

NEW_DATA_PROPS = [
    # (property, xsd type, label)
    (MEME.memeURL,       XSD.string,  "memeURL"),
    (MEME.yearOfOrigin,  XSD.integer, "yearOfOrigin"),
    (MEME.tags,          XSD.string,  "tags"),
    (MEME.description,   XSD.string,  "description"),
    (MEME.views,         XSD.integer, "views"),
    (MEME.imageURL,      XSD.string,  "imageURL"),
    (MEME.imageFilename, XSD.string,  "imageFilename"),
    (MEME.imageFilePath, XSD.string,  "imageFilePath"),
    (MEME.scrapedAt,     XSD.string,  "scrapedAt"),
]

for prop, dtype, label in NEW_DATA_PROPS:
    if (prop, RDF.type, OWL.DatatypeProperty) not in g:
        g.add((prop, RDF.type,      OWL.DatatypeProperty))
        g.add((prop, RDFS.domain,   MEME.Meme))
        g.add((prop, RDFS.range,    dtype))
        g.add((prop, RDFS.label,    Literal(label)))

print("  Added new data properties")

# ── 7. Serialize ──────────────────────────────────────────────────────────────

print(f"\nSerializing ({len(g)} triples) -> {OUTPUT} ...")
g.serialize(OUTPUT, format='xml')
print("Done.")
