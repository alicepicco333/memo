"""
Populate meme_ontology.ttl with cultural reference, meme idea,
and transformation annotations from the three JSON annotation files.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).parent
TTL_FILE = BASE / "meme_ontology.ttl"
CULTURAL_FILE = BASE / "cultural_reference_annotations(1).json"
IDEA_FILE = BASE / "meme_idea_annotations.json"
TRANSFORM_FILE = BASE / "transformation_annotations.json"

PREFIX = "http://www.semanticweb.org/meme-ontology#"
MEME_NS = "memo:"

def esc_ttl_string(s: str) -> str:
    """Escape a string for use as a Turtle string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

def slug_to_iri(slug: str) -> str:
    """Convert a slug to a safe Turtle local name. Mirrors ontology conventions."""
    return slug

# ── Load annotation files ────────────────────────────────────────────────────

with open(CULTURAL_FILE, encoding="utf-8") as f:
    cultural_data = json.load(f)

with open(IDEA_FILE, encoding="utf-8") as f:
    idea_data = json.load(f)

with open(TRANSFORM_FILE, encoding="utf-8") as f:
    transform_data = json.load(f)

# ── Collect unique transformation dimensions & extents ───────────────────────

all_dimensions = set()
all_extents = set()
for entry in transform_data:
    for dim in entry.get("transformationDimension", []):
        all_dimensions.add(dim)
    extent = entry.get("transformationExtent", "")
    if extent:
        all_extents.add(extent)

print(f"Transformation dimensions: {sorted(all_dimensions)}")
print(f"Transformation extents:    {sorted(all_extents)}")

# ── Collect unique cultural reference individuals ────────────────────────────

# dict: individual_id -> {class, label, note}  (note = last seen, per individual)
ref_individuals: dict[str, dict] = {}
for entry in cultural_data:
    for ref in entry.get("references", []):
        ind = ref["individual"]
        if ind not in ref_individuals:
            ref_individuals[ind] = {
                "class": ref["class"],
                "label": ref["label"],
                "note": ref.get("note", ""),
            }

# ── Read existing TTL ────────────────────────────────────────────────────────

original_ttl = TTL_FILE.read_text(encoding="utf-8")

# Guard: skip if already populated
if "### BEGIN ANNOTATION POPULATION" in original_ttl:
    print("Ontology already populated. Remove the annotation block to re-run.")
    raise SystemExit(0)

# ── Build the TTL block ──────────────────────────────────────────────────────

lines: list[str] = []

lines.append("")
lines.append("### BEGIN ANNOTATION POPULATION")
lines.append("")

# ── 1. New schema elements ────────────────────────────────────────────────────

lines.append("# ── Schema additions ────────────────────────────────────────")
lines.append("")

# TransformationDimension class
lines.append("memo:TransformationDimension a owl:Class ;")
lines.append('    rdfs:label "TransformationDimension" .')
lines.append("")

# TransformationExtent class
lines.append("memo:TransformationExtent a owl:Class ;")
lines.append('    rdfs:label "TransformationExtent" .')
lines.append("")

# conceptDescription datatype property (for MemeIdea)
lines.append("memo:conceptDescription a owl:DatatypeProperty ;")
lines.append('    rdfs:label "conceptDescription" ;')
lines.append("    rdfs:domain memo:MemeIdea ;")
lines.append("    rdfs:range xsd:string .")
lines.append("")

# hasTransformationDimension object property
lines.append("memo:hasTransformationDimension a owl:ObjectProperty ;")
lines.append('    rdfs:label "hasTransformationDimension" ;')
lines.append("    rdfs:domain memo:VariantInstance ;")
lines.append("    rdfs:range memo:TransformationDimension .")
lines.append("")

# hasTransformationExtent object property
lines.append("memo:hasTransformationExtent a owl:ObjectProperty ;")
lines.append('    rdfs:label "hasTransformationExtent" ;')
lines.append("    rdfs:domain memo:VariantInstance ;")
lines.append("    rdfs:range memo:TransformationExtent .")
lines.append("")

# transformationNote datatype property
lines.append("memo:transformationNote a owl:DatatypeProperty ;")
lines.append('    rdfs:label "transformationNote" ;')
lines.append("    rdfs:domain memo:VariantInstance ;")
lines.append("    rdfs:range xsd:string .")
lines.append("")

# variantTitle datatype property
lines.append("memo:variantTitle a owl:DatatypeProperty ;")
lines.append('    rdfs:label "variantTitle" ;')
lines.append("    rdfs:domain memo:VariantInstance ;")
lines.append("    rdfs:range xsd:string .")
lines.append("")

# captionText datatype property
lines.append("memo:captionText a owl:DatatypeProperty ;")
lines.append('    rdfs:label "captionText" ;')
lines.append("    rdfs:domain memo:VariantInstance ;")
lines.append("    rdfs:range xsd:string .")
lines.append("")

# hasIdea inverse link (MemeConcept → MemeIdea)
lines.append("memo:hasIdea a owl:ObjectProperty ;")
lines.append('    rdfs:label "hasIdea" ;')
lines.append("    rdfs:domain memo:MemeConcept ;")
lines.append("    rdfs:range memo:MemeIdea .")
lines.append("")

# ── 2. TransformationDimension individuals ────────────────────────────────────

lines.append("# ── TransformationDimension individuals ─────────────────────")
lines.append("")
for dim in sorted(all_dimensions):
    lines.append(f"memo:{dim} a memo:TransformationDimension,")
    lines.append(f"        owl:NamedIndividual ;")
    lines.append(f'    rdfs:label "{dim}" .')
    lines.append("")

# ── 3. TransformationExtent individuals ──────────────────────────────────────

lines.append("# ── TransformationExtent individuals ────────────────────────")
lines.append("")
for extent in sorted(all_extents):
    lines.append(f"memo:{extent} a memo:TransformationExtent,")
    lines.append(f"        owl:NamedIndividual ;")
    lines.append(f'    rdfs:label "{extent}" .')
    lines.append("")

# ── 4. CulturalReference individuals ─────────────────────────────────────────

lines.append("# ── CulturalReference individuals ───────────────────────────")
lines.append("")
for ind_id, meta in sorted(ref_individuals.items()):
    cls = meta["class"]
    label = esc_ttl_string(meta["label"])
    note = esc_ttl_string(meta["note"])
    lines.append(f"memo:{ind_id} a memo:{cls},")
    lines.append(f"        owl:NamedIndividual ;")
    lines.append(f'    rdfs:label "{label}" ;')
    lines.append(f'    rdfs:comment "{note}" .')
    lines.append("")

# ── 5. hasReference links on MemeConcepts ────────────────────────────────────

lines.append("# ── hasReference links ──────────────────────────────────────")
lines.append("")
for entry in cultural_data:
    concept_iri = entry["memeConceptIRI"].replace(PREFIX, "memo:")
    refs = entry.get("references", [])
    if not refs:
        continue
    ref_iris = ", ".join(f"memo:{r['individual']}" for r in refs)
    lines.append(f"{concept_iri} memo:hasReference {ref_iris} .")
    lines.append("")

# ── 6. MemeIdea individuals ───────────────────────────────────────────────────

lines.append("# ── MemeIdea individuals ────────────────────────────────────")
lines.append("")
for entry in idea_data:
    ind_id = entry["individual"]
    label = esc_ttl_string(entry["label"])
    desc = esc_ttl_string(entry["conceptDescription"])
    concept_iri = entry["memeConceptIRI"].replace(PREFIX, "memo:")
    lines.append(f"memo:{ind_id} a memo:MemeIdea,")
    lines.append(f"        owl:NamedIndividual ;")
    lines.append(f'    rdfs:label "{label}" ;')
    lines.append(f'    memo:conceptDescription "{desc}"^^xsd:string ;')
    lines.append(f"    memo:isConceptualizedAs {concept_iri} .")
    lines.append("")

# ── 7. hasIdea back-links on MemeConcepts ────────────────────────────────────

lines.append("# ── hasIdea back-links ──────────────────────────────────────")
lines.append("")
for entry in idea_data:
    concept_iri = entry["memeConceptIRI"].replace(PREFIX, "memo:")
    ind_id = entry["individual"]
    lines.append(f"{concept_iri} memo:hasIdea memo:{ind_id} .")
    lines.append("")

# ── 8. Transformation VariantInstance individuals ────────────────────────────

lines.append("# ── Transformation VariantInstance individuals ───────────────")
lines.append("")
for entry in transform_data:
    photo_id = entry["photoId"]
    local_name = f"photo_{photo_id}"
    concept_iri = entry["memeConceptIRI"].replace(PREFIX, "memo:")
    title = esc_ttl_string(entry.get("variantTitle", ""))
    uploader = esc_ttl_string(entry.get("variantUploader", ""))
    caption = esc_ttl_string(entry.get("captionText", ""))
    dims = entry.get("transformationDimension", [])
    extent = entry.get("transformationExtent", "")
    note = esc_ttl_string(entry.get("notes", ""))

    lines.append(f"memo:{local_name} a memo:VariantInstance,")
    lines.append(f"        owl:NamedIndividual ;")
    if title:
        lines.append(f'    rdfs:label "{title}" ;')
    lines.append(f"    memo:isVariantOf {concept_iri} ;")
    lines.append(f'    memo:photoId "{photo_id}"^^xsd:string ;')
    if uploader:
        lines.append(f'    memo:variantUploader "{uploader}"^^xsd:string ;')
    if title:
        lines.append(f'    memo:variantTitle "{title}"^^xsd:string ;')
    if caption:
        lines.append(f'    memo:captionText "{caption}"^^xsd:string ;')
    if dims:
        dim_iris = ", ".join(f"memo:{d}" for d in dims)
        lines.append(f"    memo:hasTransformationDimension {dim_iris} ;")
    if extent:
        lines.append(f"    memo:hasTransformationExtent memo:{extent} ;")
    if note:
        lines.append(f'    memo:transformationNote "{note}"^^xsd:string .')
    else:
        # Remove trailing semicolon from last property if no note
        if lines[-1].endswith(" ;"):
            lines[-1] = lines[-1][:-2] + " ."
        elif lines[-1].endswith(";"):
            lines[-1] = lines[-1][:-1] + "."
    lines.append("")

lines.append("### END ANNOTATION POPULATION")
lines.append("")

# ── Append to TTL ─────────────────────────────────────────────────────────────

addition = "\n".join(lines)
TTL_FILE.write_text(original_ttl + "\n" + addition, encoding="utf-8")

print(f"\nDone. Appended {len(lines)} lines to {TTL_FILE.name}")
print(f"  Cultural reference individuals: {len(ref_individuals)}")
print(f"  Meme idea individuals:          {len(idea_data)}")
print(f"  Transformation variant instances: {len(transform_data)}")
