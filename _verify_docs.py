"""
Verify documentation.html class/property list matches meme_ontology.ttl.
"""
from rdflib import Graph, RDF, RDFS, OWL, URIRef
from pathlib import Path
import re

ROOT = Path(__file__).parent
NS = "http://www.semanticweb.org/meme-ontology#"

print("Parsing meme_ontology.ttl...")
g = Graph()
g.parse(str(ROOT / "meme_ontology.ttl"), format="turtle")
print(f"  {len(g)} triples\n")

def local(uri):
    return str(uri).replace(NS, "memo:")

def label(uri):
    for lbl in g.objects(uri, RDFS.label):
        return str(lbl)
    return local(uri)

# Collect from TTL
ttl_classes    = sorted([u for u in g.subjects(RDF.type, OWL.Class)     if isinstance(u, URIRef) and str(u).startswith(NS)], key=local)
ttl_obj_props  = sorted([u for u in g.subjects(RDF.type, OWL.ObjectProperty)  if isinstance(u, URIRef) and str(u).startswith(NS)], key=local)
ttl_data_props = sorted([u for u in g.subjects(RDF.type, OWL.DatatypeProperty) if isinstance(u, URIRef) and str(u).startswith(NS)], key=local)

print(f"=== OWL Classes ({len(ttl_classes)}) ===")
for c in ttl_classes:
    print(f"  {local(c):<45}  rdfs:label={label(c)!r}")

print(f"\n=== Object Properties ({len(ttl_obj_props)}) ===")
for p in ttl_obj_props:
    print(f"  {local(p)}")

print(f"\n=== Datatype Properties ({len(ttl_data_props)}) ===")
for p in ttl_data_props:
    print(f"  {local(p)}")

# Cross-check with documentation.html
print("\n=== Cross-checking documentation.html ===")
doc = (ROOT / "documentation.html").read_text(encoding="utf-8")

missing_in_doc = []
for c in ttl_classes:
    lname = str(c).replace(NS, "")
    if lname not in doc:
        missing_in_doc.append(local(c))

if missing_in_doc:
    print(f"  MISSING from documentation: {missing_in_doc}")
else:
    print(f"  All {len(ttl_classes)} OWL classes present in documentation.html ✓")

missing_props = []
for p in ttl_obj_props + ttl_data_props:
    lname = str(p).replace(NS, "")
    if lname not in doc:
        missing_props.append(local(p))

if missing_props:
    print(f"  MISSING properties from documentation: {missing_props}")
else:
    print(f"  All {len(ttl_obj_props)+len(ttl_data_props)} properties present in documentation.html ✓")

# Check SPARQL example queries use valid class/property names
print("\n=== Checking SPARQL query class/property names ===")
sparql_text = (ROOT / "sparql.html").read_text(encoding="utf-8")
ttl_names = set(str(u).replace(NS, "") for u in ttl_classes + ttl_obj_props + ttl_data_props)

# Find all memo:X references in sparql.html
used_in_sparql = re.findall(r"memo:([A-Za-z][A-Za-z0-9_-]*)", sparql_text)
unknown = [n for n in set(used_in_sparql) if n not in ttl_names]
if unknown:
    print(f"  Unknown memo: names in SPARQL queries: {sorted(set(unknown))}")
else:
    print(f"  All memo: names in SPARQL queries match TTL entities ✓")

print("\nDone.")
