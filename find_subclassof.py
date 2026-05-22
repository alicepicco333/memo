import re
text = open('meme_ontology.owl', encoding='utf-8').read()
NS = 'http://www.semanticweb.org/meme-ontology#'

matches = list(re.finditer(
    r'<rdfs:subClassOf rdf:resource="' + re.escape(NS + 'CulturalReference') + r'"',
    text
))
print(f"Found {len(matches)} subclasses of CulturalReference")
for m in matches:
    ctx = text[max(0, m.start()-300):m.start()+80]
    print()
    print(ctx)
    print('---')
