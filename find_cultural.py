import re
text = open('meme_ontology.owl', encoding='utf-8').read()
NS = 'http://www.semanticweb.org/meme-ontology#'

targets = ['CulturalReference', 'PoliticalEvent', 'MediaProperty', 'WebCulture',
           'PublicFigure', 'HistoricalEvent', 'SocialPhenomenon']

for name in targets:
    has_class_block = bool(re.search(r'<owl:Class rdf:about="' + re.escape(NS + name) + '">', text))
    count_as_type = text.count(f'rdf:type rdf:resource="{NS}{name}"')
    count_subclassof = text.count(f'<rdfs:subClassOf rdf:resource="{NS}{name}"')
    print(f'{name}: owl:Class={has_class_block}, used-as-type={count_as_type}, has-subclasses={count_subclassof}')
