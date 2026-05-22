"""
restructure_owl.py
==================
Converts the OWL ontology from the "axis-as-class" pattern to the
"axis-as-annotation-string" pattern:

  BEFORE:
    memo:frbrLevel  rdf:resource="...#Expression"
    memo:semanticLevel  rdf:resource="...#Iconographical"
    memo:documentaryLevel  rdf:resource="...#DocumentaryLevel"

  AFTER:
    memo:frbrLevel>Expression</memo:frbrLevel
    memo:semanticLevel>Iconographical</memo:semanticLevel
    memo:documentaryLevel>true</memo:documentaryLevel

Also removes:
  - owl:Class blocks for FRBRLevel / SemanticLevel / DocumentaryLevel
  - owl:NamedIndividual blocks for Work / Expression / Manifestation / Item
    / PreIconographical / Iconographical / Iconological
  - rdfs:range assertions from the three annotation properties

And fixes:
  - VariantInstance frbrLevel:  Item  ->  Manifestation  (per spec)
"""

import re
from pathlib import Path

OWL = Path("meme_ontology.owl")
NS  = "http://www.semanticweb.org/meme-ontology#"

print("Reading", OWL, "...")
text = OWL.read_text(encoding="utf-8")
orig_len = len(text)


# ── helper: remove one XML element block ─────────────────────────────────────

def remove_block(text, element_type, local_name):
    """Remove a single <element_type rdf:about="NS+local_name">...</element_type> block."""
    pat = (
        r'\n  <' + re.escape(element_type) + r' rdf:about="'
        + re.escape(NS + local_name) + r'">.*?</' + re.escape(element_type) + r'>\n'
    )
    new_text, n = re.subn(pat, '\n', text, flags=re.DOTALL)
    return new_text, n


# ── Step 1: remove section comment headers for axis sections ──────────────────
# These are the <!-- ════ ... ════ --> comments that label the axis blocks.

axis_comment_patterns = [
    r'\n  <!-- [═]+\n       Axis classes — FRBR\n       [═]+ -->\n',
    r'\n  <!-- [═]+\n       Axis classes — Panofsky semantic levels\n       [═]+ -->\n',
    r'\n  <!-- [═]+\n       Axis class — Documentary level\n       [═]+ -->\n',
]
for pat in axis_comment_patterns:
    text, n = re.subn(pat, '\n', text)
    print(f"  Removed axis section comment: {n}")


# ── Step 2: remove axis owl:Class blocks ──────────────────────────────────────

for name in ["FRBRLevel", "SemanticLevel", "DocumentaryLevel"]:
    text, n = remove_block(text, "owl:Class", name)
    print(f"  Removed owl:Class {name}: {n} block(s)")


# ── Step 3: remove axis owl:NamedIndividual blocks ────────────────────────────

for name in ["Work", "Expression", "Manifestation", "Item",
             "PreIconographical", "Iconographical", "Iconological"]:
    text, n = remove_block(text, "owl:NamedIndividual", name)
    print(f"  Removed owl:NamedIndividual {name}: {n} block(s)")


# ── Step 4: remove rdfs:range from the three annotation properties ─────────────

for axis in ["FRBRLevel", "SemanticLevel", "DocumentaryLevel"]:
    pat = r'\n    <rdfs:range rdf:resource="' + re.escape(NS + axis) + r'"\s*/>'
    text, n = re.subn(pat, '', text)
    print(f"  Removed rdfs:range -> {axis}: {n} occurrence(s)")


# ── Step 5: convert memo:frbrLevel IRI reference → string literal ─────────────

frbr_labels = ["Work", "Expression", "Manifestation", "Item"]
for label in frbr_labels:
    old = f'<memo:frbrLevel rdf:resource="{NS}{label}"/>'
    new = f'<memo:frbrLevel>{label}</memo:frbrLevel>'
    count = text.count(old)
    text = text.replace(old, new)
    print(f"  frbrLevel {label} -> string literal: {count}")


# ── Step 6: convert memo:semanticLevel IRI reference → string literal ─────────

sem_labels = ["PreIconographical", "Iconographical", "Iconological"]
for label in sem_labels:
    old = f'<memo:semanticLevel rdf:resource="{NS}{label}"/>'
    new = f'<memo:semanticLevel>{label}</memo:semanticLevel>'
    count = text.count(old)
    text = text.replace(old, new)
    print(f"  semanticLevel {label} -> string literal: {count}")


# ── Step 7: convert memo:documentaryLevel IRI reference → "true" ──────────────

old = f'<memo:documentaryLevel rdf:resource="{NS}DocumentaryLevel"/>'
new = '<memo:documentaryLevel>true</memo:documentaryLevel>'
count = text.count(old)
text = text.replace(old, new)
print(f"  documentaryLevel -> 'true': {count}")


# ── Step 8: fix VariantInstance frbrLevel Item -> Manifestation ───────────────
# The user spec assigns VariantInstance to the Manifestation level.
# After step 5 it will read <memo:frbrLevel>Item</memo:frbrLevel> inside that block.

def fix_in_class_block(text, class_name, old_str, new_str):
    pat = (
        r'(<owl:Class rdf:about="' + re.escape(NS + class_name) + r'">.*?</owl:Class>)'
    )
    def replacer(m):
        return m.group(0).replace(old_str, new_str)
    new_text, n = re.subn(pat, replacer, text, flags=re.DOTALL)
    return new_text, n

text, n = fix_in_class_block(
    text, "VariantInstance",
    "<memo:frbrLevel>Item</memo:frbrLevel>",
    "<memo:frbrLevel>Manifestation</memo:frbrLevel>",
)
print(f"  VariantInstance frbrLevel Item -> Manifestation: {n} block(s)")


# ── Save ───────────────────────────────────────────────────────────────────────

tmp = Path(str(OWL) + ".tmp")
tmp.write_text(text, encoding="utf-8")
tmp.replace(OWL)
print(f"\nDone. {OWL}  ({orig_len:,} -> {len(text):,} chars)")
