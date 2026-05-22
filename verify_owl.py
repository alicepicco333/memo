import re
text = open('meme_ontology.owl', encoding='utf-8').read()
NS = 'http://www.semanticweb.org/meme-ontology#'

print("=== ValueClass removed ===")
print("  ValueClass owl:Class present:", f'owl:Class rdf:about="{NS}ValueClass"' in text)
print("  rdfs:subClassOf #ValueClass present:", f'subClassOf rdf:resource="{NS}ValueClass"' in text)

print()
print("=== No remaining IRI-ref annotation values ===")
leftovers = re.findall(r'<memo:(frbrLevel|semanticLevel|documentaryLevel) rdf:resource=', text)
print(f"  Remaining IRI-ref usages: {len(leftovers)}")

print()
print("=== Class annotations (schema owl:Class blocks) ===")
class_blocks = re.findall(r'<owl:Class rdf:about="[^"]+">.*?</owl:Class>', text, re.DOTALL)
for block in class_blocks:
    name_m = re.search(r'rdf:about="[^#"]+#([^"]+)"', block)
    name = name_m.group(1) if name_m else '?'
    frbr = re.findall(r'<memo:frbrLevel>(.*?)</memo:frbrLevel>', block)
    sem  = re.findall(r'<memo:semanticLevel>(.*?)</memo:semanticLevel>', block)
    doc  = re.findall(r'<memo:documentaryLevel>(.*?)</memo:documentaryLevel>', block)
    sub  = re.findall(r'rdfs:subClassOf rdf:resource="[^#"]+#([^"]+)"', block)
    line = f"  {name}"
    if frbr:  line += f"  frbrLevel={frbr[0]}"
    if sem:   line += f"  semanticLevel={sem[0]}"
    if doc:   line += f"  documentaryLevel={doc[0]}"
    if sub:   line += f"  subClassOf={sub}"
    print(line)
