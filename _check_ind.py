from rdflib import Graph, RDF, OWL, URIRef, RDFS
NS = "http://www.semanticweb.org/meme-ontology#"
g = Graph()
g.parse("meme_ontology.ttl", format="turtle")

results = [(str(s).replace(NS,"memo:"), str(l)) for s,l in g.subject_objects(RDFS.label) if "distracted" in str(l).lower()]
print("Distracted entries:", results[:5])

uri = URIRef(NS + "distracted-boyfriend")
triples = list(g.triples((uri, None, None)))
print(f"Triples for memo:distracted-boyfriend: {len(triples)}")
for s,p,o in triples[:3]:
    pname = str(p).split("#")[-1]
    print(f"  {pname} = {str(o)[:80]}")
