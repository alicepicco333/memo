"""
Rename prefix meme: -> memo: across all relevant files.
Run from workspace root.
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).parent

# ── TTL ───────────────────────────────────────────────────────────────────────
print("=== meme_ontology.ttl ===")
ttl_path = ROOT / "meme_ontology.ttl"
text = ttl_path.read_text(encoding="utf-8")
total = text.count("meme:")
# check for meme: inside quoted strings
in_strings = re.findall(r'"[^"]*meme:[^"]*"', text)
print(f"  Total meme: occurrences: {total}")
print(f"  meme: inside string literals: {len(in_strings)}")
for s in in_strings[:5]:
    print(f"    {s[:80]}")

new_text = text.replace("meme:", "memo:")
ttl_path.write_text(new_text, encoding="utf-8")
print(f"  Done – replaced {total} occurrences")

# ── sparql.html ───────────────────────────────────────────────────────────────
print("\n=== sparql.html ===")
sp_path = ROOT / "sparql.html"
text = sp_path.read_text(encoding="utf-8")
total = text.count("meme:")
# In sparql.html, meme: appears as:
#   PREFIX meme: <...>  (in JS strings and HTML textarea)
#   meme:ClassName      (in SPARQL query strings)
new_text = text.replace("meme:", "memo:")
sp_path.write_text(new_text, encoding="utf-8")
print(f"  Replaced {total} occurrences")

# ── documentation.html ────────────────────────────────────────────────────────
print("\n=== documentation.html ===")
doc_path = ROOT / "documentation.html"
text = doc_path.read_text(encoding="utf-8")
total = text.count("meme:")
new_text = text.replace("meme:", "memo:")
doc_path.write_text(new_text, encoding="utf-8")
print(f"  Replaced {total} occurrences")

# ── generate_lode_docs.py ─────────────────────────────────────────────────────
print("\n=== generate_lode_docs.py ===")
gen_path = ROOT / "generate_lode_docs.py"
text = gen_path.read_text(encoding="utf-8")
total = text.count('"meme:"')
new_text = text.replace('"meme:"', '"memo:"')
gen_path.write_text(new_text, encoding="utf-8")
print(f"  Replaced {total} occurrences of \"meme:\"")

# ── populate_annotations.py ───────────────────────────────────────────────────
print("\n=== populate_annotations.py ===")
pa_path = ROOT / "populate_annotations.py"
if pa_path.exists():
    text = pa_path.read_text(encoding="utf-8")
    total = text.count("meme:")
    new_text = text.replace("meme:", "memo:")
    pa_path.write_text(new_text, encoding="utf-8")
    print(f"  Replaced {total} occurrences")

# ── Python scripts ────────────────────────────────────────────────────────────
for name in ["restructure_ontology.py", "fix_class_hierarchy.py", "remap_frbr.py"]:
    p = ROOT / name
    if p.exists():
        text = p.read_text(encoding="utf-8")
        total = text.count("meme:")
        if total:
            p.write_text(text.replace("meme:", "memo:"), encoding="utf-8")
            print(f"\n=== {name} === replaced {total} occurrences")

print("\nAll done.")
