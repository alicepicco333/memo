"""
fix_schema.py
=============
1. Remove owl:Class ValueClass + section comment
2. Remove every rdfs:subClassOf #ValueClass line
3. Set exactly correct annotation values on every class per the spec
"""

import re
from pathlib import Path

OWL = Path("meme_ontology.owl")
NS  = "http://www.semanticweb.org/meme-ontology#"

print("Reading", OWL, "...")
text = OWL.read_text(encoding="utf-8")
orig_len = len(text)

ANNO_PROPS = ["frbrLevel", "semanticLevel", "documentaryLevel"]

# ── helpers ──────────────────────────────────────────────────────────────────

def strip_memo_annos(block):
    """Remove all existing memo:frbrLevel / semanticLevel / documentaryLevel elements."""
    for prop in ANNO_PROPS:
        block = re.sub(
            r'\n    <memo:' + prop + r'>.*?</memo:' + prop + r'>',
            '', block
        )
    return block

def add_memo_annos(block, annotations):
    """Insert the desired annotations just before the closing </owl:Class>."""
    insert = ''
    for prop, value in annotations.items():
        insert += f'\n    <memo:{prop}>{value}</memo:{prop}>'
    # Replace only the last </owl:Class> in the block
    return block[::-1].replace('>ssalC:lwo/<', (insert + '\n  </owl:Class>')[::-1], 1)[::-1]

def set_class_annotations(text, class_name, annotations):
    pat = re.compile(
        r'  <owl:Class rdf:about="' + re.escape(NS + class_name) + r'">.*?</owl:Class>',
        re.DOTALL
    )
    def replacer(m):
        block = strip_memo_annos(m.group(0))
        return add_memo_annos(block, annotations)
    new_text, n = pat.subn(replacer, text)
    status = "OK" if n == 1 else f"WARNING: {n} matches"
    print(f"  {class_name}: {annotations}  [{status}]")
    return new_text

# ── 1. Remove ValueClass section comment ─────────────────────────────────────

comment_pat = (
    r'\n  <!-- [═]{10,}\n'
    r'       ValueClass grouping[^\-]*?\n'
    r'       [═]{10,} -->\n'
)
text, n = re.subn(comment_pat, '\n', text, flags=re.DOTALL)
print(f"Removed ValueClass section comment: {n}")

# ── 2. Remove ValueClass class block ─────────────────────────────────────────

vc_pat = re.compile(
    r'\n  <owl:Class rdf:about="' + re.escape(NS + "ValueClass") + r'">.*?</owl:Class>\n',
    re.DOTALL
)
text, n = vc_pat.subn('\n', text)
print(f"Removed ValueClass class block: {n}")

# ── 3. Remove all rdfs:subClassOf → #ValueClass ───────────────────────────────

sub_pat = (
    r'\n    <rdfs:subClassOf rdf:resource="'
    + re.escape(NS + "ValueClass")
    + r'"\s*/>'
)
text, n = re.subn(sub_pat, '', text)
print(f"Removed rdfs:subClassOf #ValueClass: {n} lines")

# ── 4. Set correct annotations on every class ─────────────────────────────────
#
# Explicit table from spec + pattern-inferred values for unlisted classes.
# "And so on for every class" — Canonical* → Expression/PreIconographical;
# their item-level counterparts → Manifestation/PreIconographical;
# file-level → Item; documentary provenance → documentaryLevel=true.

print("\nSetting class annotations:")

CLASS_ANNOTATIONS = {
    # ── Core domain classes ───────────────────────────────────────────────────
    # (no semanticLevel — user spec lists only frbrLevel here)
    "MemeConcept":             {"frbrLevel": "Expression"},
    "MemeIdea":                {"frbrLevel": "Work"},
    "VariantInstance":         {"frbrLevel": "Manifestation"},

    # ── Expression-level canonical classifiers ────────────────────────────────
    "MemeFormat":              {"frbrLevel": "Expression",            "semanticLevel": "Iconographical"},
    "OriginPlatform":          {"frbrLevel": "Expression",            "documentaryLevel": "true"},
    "OriginWork":              {"frbrLevel": "Work",                  "semanticLevel": "Iconological"},
    "CanonicalImageType":      {"frbrLevel": "Expression",            "semanticLevel": "PreIconographical"},
    "CanonicalColorMode":      {"frbrLevel": "Expression",            "semanticLevel": "PreIconographical"},
    "CanonicalTextPresence":   {"frbrLevel": "Expression",            "semanticLevel": "PreIconographical"},
    "CanonicalSubjectMatter":  {"frbrLevel": "Expression",            "semanticLevel": "PreIconographical"},

    # ── Manifestation-level variant classifiers ───────────────────────────────
    "ImageType":               {"frbrLevel": "Manifestation",         "semanticLevel": "PreIconographical"},

    # ── Item-level ────────────────────────────────────────────────────────────
    "FileFormat":              {"frbrLevel": "Item",                  "documentaryLevel": "true"},
    "AnimationStatus":         {"frbrLevel": "Item",                  "semanticLevel": "PreIconographical"},
    "TransformationExtent":    {"frbrLevel": "Item",                  "semanticLevel": "Iconographical"},
    "TransformationDimension": {"frbrLevel": "Item",                  "semanticLevel": "Iconographical"},

    # ── Documentary provenance ────────────────────────────────────────────────
    "GeographicRegion":        {"documentaryLevel": "true"},
    "TimePeriod":              {"documentaryLevel": "true"},

    # ── Cultural reference ────────────────────────────────────────────────────
    "CulturalReference":       {"frbrLevel": "Expression Manifestation", "semanticLevel": "Iconological"},
}

for class_name, annotations in CLASS_ANNOTATIONS.items():
    text = set_class_annotations(text, class_name, annotations)

# ── 5. Save ───────────────────────────────────────────────────────────────────

tmp = Path(str(OWL) + ".tmp")
tmp.write_text(text, encoding="utf-8")
tmp.replace(OWL)
print(f"\nDone.  {OWL}  ({orig_len:,} -> {len(text):,} chars)")
