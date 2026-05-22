"""Fix FRBR-level subClassOf assignments to match the target hierarchy.

Changes
-------
Move Work → Expression  (5 classes):
    MemeFormat, OriginPlatform, OriginWork, GeographicRegion, TimePeriod

Move Manifestation → Expression  (4 classes):
    ImageType, TextPresence, ColorMode, SubjectMatter

CulturalReference: remove Work, add Manifestation
    (retains Expression + Iconological — multiple inheritance)

Unchanged / already correct:
    MemeIdea          subClassOf Work
    MemeConcept       subClassOf Expression
    VariantInstance   subClassOf Manifestation
    FileFormat        subClassOf Item
    AnimationStatus   subClassOf Item
"""

from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL

BASE_DIR = Path(__file__).parent
OWL_PATH = BASE_DIR / "meme_ontology.owl"
TTL_PATH = BASE_DIR / "meme_ontology.ttl"

BASE = "http://www.semanticweb.org/meme-ontology#"
MEME = Namespace(BASE)

print("Loading ontology …")
g = Graph()
g.parse(str(OWL_PATH), format="xml")
print(f"  {len(g):,} triples loaded")

# ── helpers ───────────────────────────────────────────────────────────────────

def move_parent(cls, old_parent, new_parent):
    """Swap one subClassOf triple; skip if old triple absent or new already present."""
    old = (MEME[cls], RDFS.subClassOf, MEME[old_parent])
    new = (MEME[cls], RDFS.subClassOf, MEME[new_parent])
    if old in g:
        g.remove(old)
        g.add(new)
        print(f"  {cls:20s}  subClassOf  {old_parent} → {new_parent}")
    elif new in g:
        print(f"  {cls:20s}  already subClassOf {new_parent}  (skipped)")
    else:
        print(f"  WARNING: {cls} had no subClassOf {old_parent} — adding {new_parent} anyway")
        g.add(new)

def add_parent(cls, new_parent):
    """Add a subClassOf triple if not already present."""
    triple = (MEME[cls], RDFS.subClassOf, MEME[new_parent])
    if triple not in g:
        g.add(triple)
        print(f"  {cls:20s}  +subClassOf {new_parent}")

def remove_parent(cls, old_parent):
    """Remove a subClassOf triple if present."""
    triple = (MEME[cls], RDFS.subClassOf, MEME[old_parent])
    if triple in g:
        g.remove(triple)
        print(f"  {cls:20s}  -subClassOf {old_parent}")

# ── 1. Move Work → Expression ─────────────────────────────────────────────────

print("\nMoving Work → Expression:")
for cls in ("MemeFormat", "OriginPlatform", "OriginWork", "GeographicRegion", "TimePeriod"):
    move_parent(cls, "Work", "Expression")

# ── 2. Move Manifestation → Expression ───────────────────────────────────────

print("\nMoving Manifestation → Expression:")
for cls in ("ImageType", "TextPresence", "ColorMode", "SubjectMatter"):
    move_parent(cls, "Manifestation", "Expression")

# ── 3. CulturalReference: Work → Manifestation (keep Expression + Iconological)

print("\nFixing CulturalReference:")
remove_parent("CulturalReference", "Work")
add_parent("CulturalReference", "Manifestation")

# ── verify ────────────────────────────────────────────────────────────────────

print("\nVerification:")
check = [
    "MemeIdea", "MemeConcept", "MemeFormat", "OriginPlatform", "OriginWork",
    "GeographicRegion", "TimePeriod", "ImageType", "TextPresence", "ColorMode",
    "SubjectMatter", "CulturalReference", "VariantInstance", "FileFormat",
    "AnimationStatus",
]
for c in check:
    parents = sorted(str(o)[len(BASE):] for _, _, o in g.triples((MEME[c], RDFS.subClassOf, None)))
    print(f"  {c:22s}  {parents}")

# ── serialise ─────────────────────────────────────────────────────────────────

print(f"\nTotal triples: {len(g):,}")
print(f"Serialising OWL/XML → {OWL_PATH.name} …")
g.serialize(str(OWL_PATH), format="xml")
print("  Done.")
print(f"Serialising Turtle  → {TTL_PATH.name} …")
g.bind("meme", MEME)
g.serialize(str(TTL_PATH), format="turtle")
print("  Done.")
