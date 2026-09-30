"""Add individuals to onto_graph.json (the Ontology page graph).

For every class node, records how many individuals the populated ontology
(meme_ontology.ttl) types with it, and up to six examples: the most viewed
memes for MemeConcept, their variants for VariantInstance, otherwise the
individuals in alphabetical order.

Usage: python build_onto_individuals.py
"""
import json
import os

from rdflib import RDF, RDFS, Graph, URIRef

HERE = os.path.dirname(os.path.abspath(__file__))
MEMO = 'https://purl.org/memo#'
PREFIXES = {
    'memo:': MEMO,
    'wd:': 'http://www.wikidata.org/entity/',
    'schema:': 'http://schema.org/',
    'frbrer:': 'http://iflastandards.info/ns/fr/frbr/frbrer/',
}
MAX_SAMPLE = 6

g = Graph()
g.parse(os.path.join(HERE, 'meme_ontology.ttl'), format='turtle')
views = {s: int(o) for s, o in g.subject_objects(URIRef(MEMO + 'views'))}


def expand(cid):
    for p, ns in PREFIXES.items():
        if cid.startswith(p):
            return ns + cid[len(p):]
    return cid


def label(ind):
    lab = g.value(ind, RDFS.label)
    if lab:
        return str(lab)
    local = str(ind).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
    return local.lstrip('_').replace('-', ' ').replace('_', ' ')


path = os.path.join(HERE, 'onto_graph.json')
data = json.load(open(path, encoding='utf-8'))
top_memes = None
for node in data['nodes']:
    cls = URIRef(expand(node['id']))
    inds = sorted({s for s in g.subjects(RDF.type, cls) if isinstance(s, URIRef)}, key=str)
    node['count'] = len(inds)
    if not inds:
        node['sample'] = []
        continue
    if node['id'] == 'memo:MemeConcept':
        inds.sort(key=lambda s: -views.get(s, 0))
        top_memes = [str(s).rsplit('#', 1)[-1] for s in inds[:MAX_SAMPLE]]
    elif node['id'] == 'memo:VariantInstance':
        # one variant from each of the first annotated memes
        seen, picked = set(), []
        for s in inds:
            stem = str(s).rsplit('#', 1)[-1].rsplit('_v', 1)[0]
            if stem not in seen:
                seen.add(stem)
                picked.append(s)
        inds = picked
    node['sample'] = [{'id': str(s), 'label': label(s)} for s in inds[:MAX_SAMPLE]]

json.dump(data, open(path, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
total = sum(n['count'] for n in data['nodes'])
print(f"onto_graph.json: {total} typed individuals across {sum(1 for n in data['nodes'] if n['count'])} classes")
