"""
fix_axis_structure.py
---------------------
Fixes both meme_ontology.owl and meme_ontology.ttl so that the FRBR and
Panofsky "axis sub-levels" are owl:NamedIndividual instances of the axis
class, NOT owl:Class subclasses of it.

Before (wrong in Protégé):
  meme:Expression  a owl:Class ;
                   rdfs:subClassOf meme:FRBRLevel .
  meme:MemeConcept a owl:Class ;
                   meme:frbrLevel meme:Expression .   ← annotation value is a CLASS
                                                         → Protégé shows spurious
                                                           subClassOf links

After (correct):
  meme:Expression  a owl:NamedIndividual, meme:FRBRLevel .  ← just an individual
  meme:MemeConcept a owl:Class ;
                   meme:frbrLevel meme:Expression .         ← annotation value is
                                                              an INDIVIDUAL ✓
"""

import re
from pathlib import Path

BASE = Path(__file__).parent

# ── Axis items to convert: (localName, parentClass, label, comment) ──────────
FRBR_NS  = "http://www.semanticweb.org/meme-ontology#"
FRBR_ITEMS = [
    ("Work",
     "FRBRLevel",
     "Work",
     "FRBR Work: the distinct intellectual or artistic\ncreation — the underlying"
     " meme idea abstracted from any concrete realisation.\nCorresponds to MemeIdea"
     " individuals."),
    ("Expression",
     "FRBRLevel",
     "Expression",
     "FRBR Expression: a specific realisation of a\nWork — the canonical meme"
     " template with its format, platform and cultural\nassociations. Corresponds to"
     " MemeConcept individuals."),
    ("Manifestation",
     "FRBRLevel",
     "Manifestation",
     "FRBR Manifestation: the physical or digital\nembodiment of an Expression —"
     " characterised by image type, colour mode, file\nformat and animation status."),
    ("Item",
     "FRBRLevel",
     "Item",
     "FRBR Item: a single exemplar — one scraped\nvariant image with its"
     " transformation annotations. Corresponds to\nVariantInstance individuals."),
    ("PreIconographical",
     "SemanticLevel",
     "Pre-Iconographical",
     "Panofsky level I: description of visible forms\n(colours, shapes, image"
     " medium) without symbolic interpretation. Applies to\nproperties describing"
     " the physical appearance of the image."),
    ("Iconographical",
     "SemanticLevel",
     "Iconographical",
     "Panofsky level II: recognition of conventional\nsubjects, formats, cultural"
     " motifs and structural patterns."),
    ("Iconological",
     "SemanticLevel",
     "Iconological",
     "Panofsky level III: interpretation of intrinsic\ncultural meaning, symbolic"
     " significance and ideological value."),
]

# ── Fix OWL file ─────────────────────────────────────────────────────────────

owl_path = BASE / "meme_ontology.owl"
print("Reading OWL file …")
owl = owl_path.read_text(encoding="utf-8")

# For each axis item, find its owl:Class block and replace with NamedIndividual
# Pattern: <owl:Class rdf:about="...#NAME"> ... <rdfs:subClassOf .../> ... </owl:Class>

def owl_class_pattern(name):
    return (
        r'<owl:Class rdf:about="' + re.escape(FRBR_NS + name) + r'">'
        r'.*?'
        r'<rdfs:subClassOf rdf:resource="' + re.escape(FRBR_NS) + r'\w+"'
        r'\s*/>'
        r'\s*</owl:Class>'
    )

def owl_individual_replacement(name, parent, label, comment):
    comment_escaped = comment.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return (
        f'<owl:NamedIndividual rdf:about="{FRBR_NS}{name}">\n'
        f'    <rdf:type rdf:resource="{FRBR_NS}{parent}"/>\n'
        f'    <rdfs:label xml:lang="en">{label}</rdfs:label>\n'
        f'    <rdfs:comment xml:lang="en">{comment_escaped}</rdfs:comment>\n'
        f'  </owl:NamedIndividual>'
    )

changes = 0
for name, parent, label, comment in FRBR_ITEMS:
    pat = owl_class_pattern(name)
    rep = owl_individual_replacement(name, parent, label, comment)
    new_owl, n = re.subn(pat, rep, owl, flags=re.DOTALL)
    if n:
        owl = new_owl
        print(f"  OWL: converted {name} (owl:Class → owl:NamedIndividual)")
        changes += 1
    else:
        print(f"  OWL: WARNING — pattern not matched for {name}")

if changes:
    tmp = str(owl_path) + ".tmp"
    Path(tmp).write_text(owl, encoding="utf-8")
    Path(tmp).replace(owl_path)
    print(f"  Wrote {owl_path.name} ({len(owl):,} chars, {changes} changes)")
else:
    print("  OWL: no changes made")

# ── Fix TTL file ─────────────────────────────────────────────────────────────

ttl_path = BASE / "meme_ontology.ttl"
print("\nReading TTL file …")
ttl = ttl_path.read_text(encoding="utf-8")

# Build the schema preamble to insert in the TTL
# Add after the owl:Ontology line
TTL_SCHEMA = """
# ── Annotation properties ────────────────────────────────────────────────────

memo:frbrLevel a owl:AnnotationProperty ;
    rdfs:label "FRBR level"@en ;
    rdfs:comment "Associates a class or property with its FRBR abstraction level."@en ;
    rdfs:range memo:FRBRLevel .

memo:semanticLevel a owl:AnnotationProperty ;
    rdfs:label "semantic level"@en ;
    rdfs:comment "Associates a class or property with a Panofsky level of analysis."@en ;
    rdfs:range memo:SemanticLevel .

memo:documentaryLevel a owl:AnnotationProperty ;
    rdfs:label "documentary level"@en ;
    rdfs:comment "Associates a class or property with the documentary analysis dimension."@en ;
    rdfs:range memo:DocumentaryLevel .

# ── Axis classes ─────────────────────────────────────────────────────────────

memo:FRBRLevel a owl:Class ;
    rdfs:label "FRBR Level"@en ;
    rdfs:comment "Abstract axis class grouping the four FRBR abstraction levels."@en .

memo:SemanticLevel a owl:Class ;
    rdfs:label "Semantic Level"@en ;
    rdfs:comment "Abstract axis class grouping Panofsky's three levels of analysis."@en .

memo:DocumentaryLevel a owl:Class ;
    rdfs:label "Documentary Level"@en ;
    rdfs:comment "Abstract axis class for documentary provenance dimensions."@en .

# ── FRBR level individuals (NOT classes) ─────────────────────────────────────

memo:Work a owl:NamedIndividual, memo:FRBRLevel ;
    rdfs:label "Work"@en ;
    rdfs:comment "FRBR Work: the distinct intellectual or artistic creation."@en .

memo:Expression a owl:NamedIndividual, memo:FRBRLevel ;
    rdfs:label "Expression"@en ;
    rdfs:comment "FRBR Expression: a specific realisation of a Work."@en .

memo:Manifestation a owl:NamedIndividual, memo:FRBRLevel ;
    rdfs:label "Manifestation"@en ;
    rdfs:comment "FRBR Manifestation: the physical or digital embodiment of an Expression."@en .

memo:Item a owl:NamedIndividual, memo:FRBRLevel ;
    rdfs:label "Item"@en ;
    rdfs:comment "FRBR Item: a single scraped variant image exemplar."@en .

# ── Panofsky semantic level individuals (NOT classes) ────────────────────────

memo:PreIconographical a owl:NamedIndividual, memo:SemanticLevel ;
    rdfs:label "Pre-Iconographical"@en ;
    rdfs:comment "Panofsky level I: description of visible forms without symbolic interpretation."@en .

memo:Iconographical a owl:NamedIndividual, memo:SemanticLevel ;
    rdfs:label "Iconographical"@en ;
    rdfs:comment "Panofsky level II: recognition of conventional subjects and cultural motifs."@en .

memo:Iconological a owl:NamedIndividual, memo:SemanticLevel ;
    rdfs:label "Iconological"@en ;
    rdfs:comment "Panofsky level III: interpretation of intrinsic cultural meaning."@en .

# ── Domain classes ───────────────────────────────────────────────────────────

memo:MemeConcept a owl:Class ;
    rdfs:label "Meme Concept"@en ;
    rdfs:comment "A canonical internet meme template (Expression-level)."@en ;
    memo:frbrLevel memo:Expression ;
    memo:semanticLevel memo:Iconographical .

memo:MemeIdea a owl:Class ;
    rdfs:label "Meme Idea"@en ;
    rdfs:comment "The abstract Work-level idea underlying a meme."@en ;
    memo:frbrLevel memo:Work ;
    memo:semanticLevel memo:Iconological .

memo:VariantInstance a owl:Class ;
    rdfs:label "Variant Instance"@en ;
    rdfs:comment "A single scraped variant image (Item-level exemplar of a MemeConcept)."@en ;
    memo:frbrLevel memo:Item ;
    memo:semanticLevel memo:PreIconographical .

# ── Value class grouping ─────────────────────────────────────────────────────

memo:ValueClass a owl:Class ;
    rdfs:label "Value Class"@en ;
    rdfs:comment "Grouping superclass for all controlled-vocabulary term classes."@en .

memo:MemeFormat a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Meme Format"@en ;
    memo:frbrLevel memo:Expression ;
    memo:semanticLevel memo:Iconographical .

memo:OriginPlatform a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Origin Platform"@en ;
    memo:frbrLevel memo:Expression ;
    memo:documentaryLevel memo:DocumentaryLevel .

memo:OriginWork a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Origin Work"@en ;
    memo:frbrLevel memo:Work ;
    memo:semanticLevel memo:Iconological .

memo:CanonicalImageType a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Canonical Image Type"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:ImageType a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Image Type"@en ;
    memo:frbrLevel memo:Item ;
    memo:semanticLevel memo:PreIconographical .

memo:CanonicalColorMode a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Canonical Color Mode"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:CanonicalTextPresence a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Canonical Text Presence"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:CanonicalSubjectMatter a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Canonical Subject Matter"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:GeographicRegion a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Geographic Region"@en ;
    memo:documentaryLevel memo:DocumentaryLevel .

memo:TimePeriod a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Time Period"@en ;
    memo:documentaryLevel memo:DocumentaryLevel .

memo:FileFormat a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "File Format"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:AnimationStatus a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Animation Status"@en ;
    memo:frbrLevel memo:Manifestation ;
    memo:semanticLevel memo:PreIconographical .

memo:TransformationExtent a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Transformation Extent"@en ;
    memo:frbrLevel memo:Item ;
    memo:semanticLevel memo:Iconographical .

memo:TransformationDimension a owl:Class ;
    rdfs:subClassOf memo:ValueClass ;
    rdfs:label "Transformation Dimension"@en ;
    memo:frbrLevel memo:Item ;
    memo:semanticLevel memo:Iconographical .

"""

# Check if schema already injected
if "memo:FRBRLevel a owl:Class" in ttl:
    print("  TTL: schema already present — skipping injection")
else:
    # Insert after the owl:Ontology line
    ontology_line = "<http://www.semanticweb.org/meme-ontology> a owl:Ontology ."
    if ontology_line in ttl:
        ttl = ttl.replace(ontology_line, ontology_line + "\n" + TTL_SCHEMA, 1)
        tmp = str(ttl_path) + ".tmp"
        Path(tmp).write_text(ttl, encoding="utf-8")
        Path(tmp).replace(ttl_path)
        print(f"  TTL: schema block injected ({len(TTL_SCHEMA):,} chars)")
        print(f"  Wrote {ttl_path.name} ({len(ttl):,} chars)")
    else:
        print("  TTL: WARNING — could not find owl:Ontology line")

print("\nDone.")
