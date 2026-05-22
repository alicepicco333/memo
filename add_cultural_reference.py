"""
add_cultural_reference.py
=========================
Inject the missing owl:Class declaration for CulturalReference into the
schema section of meme_ontology.owl, just before the Object properties block.
"""

from pathlib import Path

OWL = Path("meme_ontology.owl")
NS  = "http://www.semanticweb.org/meme-ontology#"

INSERTION_MARKER = (
    '  <!-- ════════════════════════════════════════════════════════════════════════\n'
    '       Object properties\n'
    '       ════════════════════════════════════════════════════════════════════════ -->'
)

NEW_CLASS_BLOCK = (
    '  <owl:Class rdf:about="http://www.semanticweb.org/meme-ontology#CulturalReference">\n'
    '    <rdfs:label xml:lang="en">Cultural Reference</rdfs:label>\n'
    '    <rdfs:comment xml:lang="en">A cultural entity referenced by a meme — a historical\n'
    'event, media property, political event, public figure, social phenomenon, or web\n'
    'culture artefact. Subclasses: HistoricalEvent, MediaProperty, PoliticalEvent,\n'
    'PublicFigure, SocialPhenomenon, WebCulture.</rdfs:comment>\n'
    '    <memo:frbrLevel>Expression Manifestation</memo:frbrLevel>\n'
    '    <memo:semanticLevel>Iconological</memo:semanticLevel>\n'
    '  </owl:Class>\n'
    '\n'
)

print("Reading", OWL, "...")
text = OWL.read_text(encoding="utf-8")

if INSERTION_MARKER not in text:
    print("ERROR: insertion marker not found — check the section comment text")
    raise SystemExit(1)

if 'owl:Class rdf:about="http://www.semanticweb.org/meme-ontology#CulturalReference"' in text:
    print("CulturalReference owl:Class already present — nothing to do")
    raise SystemExit(0)

text = text.replace(INSERTION_MARKER, NEW_CLASS_BLOCK + INSERTION_MARKER)

tmp = OWL.with_suffix('.owl.tmp')
tmp.write_text(text, encoding="utf-8")
tmp.replace(OWL)
print("Done. CulturalReference owl:Class block injected.")
