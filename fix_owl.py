"""
fix_owl.py
----------
Two fixes applied to meme_ontology.owl:

1. Rename the XML prefix meme: → memo: everywhere
   (xmlns:meme → xmlns:memo, all <meme:foo> → <memo:foo>)

2. Convert the 7 axis sub-level classes from owl:Class+subClassOf
   to owl:NamedIndividual+rdf:type so they appear as annotation values,
   NOT as classes in the Protégé hierarchy:
     Work/Expression/Manifestation/Item  (parent: FRBRLevel)
     PreIconographical/Iconographical/Iconological  (parent: SemanticLevel)
"""

import re
from pathlib import Path

OWL = Path("meme_ontology.owl")
NS  = "http://www.semanticweb.org/meme-ontology#"

print("Reading OWL …")
text = OWL.read_text(encoding="utf-8")
original_len = len(text)

# ── 1. Rename prefix meme: → memo: ──────────────────────────────────────────
text = text.replace('xmlns:meme="http://www.semanticweb.org/meme-ontology#"',
                    'xmlns:memo="http://www.semanticweb.org/meme-ontology#"')
# Replace every remaining meme: prefix usage (XML element names and attributes)
text = re.sub(r'\bmeme:', 'memo:', text)
print(f"  Prefix meme: → memo: applied")

# ── 2. Convert axis sub-level classes to NamedIndividuals ────────────────────
AXIS = [
    ("Work",              "FRBRLevel",    "Work",
     "FRBR Work: the distinct intellectual or artistic creation — the underlying "
     "meme idea abstracted from any concrete realisation. "
     "Corresponds to MemeIdea individuals."),
    ("Expression",        "FRBRLevel",    "Expression",
     "FRBR Expression: a specific realisation of a Work — the canonical meme "
     "template with its format, platform and cultural associations. "
     "Corresponds to MemeConcept individuals."),
    ("Manifestation",     "FRBRLevel",    "Manifestation",
     "FRBR Manifestation: the physical or digital embodiment of an Expression — "
     "characterised by image type, colour mode, file format and animation status."),
    ("Item",              "FRBRLevel",    "Item",
     "FRBR Item: a single exemplar — one scraped variant image with its "
     "transformation annotations. Corresponds to VariantInstance individuals."),
    ("PreIconographical", "SemanticLevel","Pre-Iconographical",
     "Panofsky level I: description of visible forms (colours, shapes, image "
     "medium) without symbolic interpretation."),
    ("Iconographical",    "SemanticLevel","Iconographical",
     "Panofsky level II: recognition of conventional subjects, formats, cultural "
     "motifs and structural patterns."),
    ("Iconological",      "SemanticLevel","Iconological",
     "Panofsky level III: interpretation of intrinsic cultural meaning, symbolic "
     "significance and ideological value."),
]

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

for local, parent, label, comment in AXIS:
    # Match the full owl:Class block including its rdfs:subClassOf line
    pat = (
        r'<owl:Class rdf:about="' + re.escape(NS + local) + r'">'
        r'(.*?)'
        r'<rdfs:subClassOf rdf:resource="' + re.escape(NS + parent) + r'"\s*/>'
        r'\s*</owl:Class>'
    )
    replacement = (
        f'<owl:NamedIndividual rdf:about="{NS}{local}">\n'
        f'    <rdf:type rdf:resource="{NS}{parent}"/>\n'
        f'    <rdfs:label xml:lang="en">{esc(label)}</rdfs:label>\n'
        f'    <rdfs:comment xml:lang="en">{esc(comment)}</rdfs:comment>\n'
        f'  </owl:NamedIndividual>'
    )
    new_text, n = re.subn(pat, replacement, text, flags=re.DOTALL)
    if n:
        text = new_text
        print(f"  Converted {local}: owl:Class → owl:NamedIndividual")
    else:
        print(f"  WARNING: pattern not matched for {local} — check manually")

# ── Write back ───────────────────────────────────────────────────────────────
tmp = str(OWL) + ".tmp"
Path(tmp).write_text(text, encoding="utf-8")
Path(tmp).replace(OWL)
print(f"\nWrote {OWL.name}  ({original_len:,} → {len(text):,} chars)")
