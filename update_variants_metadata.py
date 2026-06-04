"""Rebuild variants_metadata.json from all sampled_variants folders."""
import json, os

SRC_BASE = "sampled_variants"
SLUGS = sorted(os.listdir(SRC_BASE))

records = []
for slug in SLUGS:
    meta_path = os.path.join(SRC_BASE, slug, "metadata.json")
    if not os.path.exists(meta_path):
        continue
    with open(meta_path, encoding="utf-8", errors="replace") as f:
        meta = json.load(f)
    for m in meta:
        rec = dict(m)
        rec["folder"] = slug
        records.append(rec)

with open("variants_metadata.json", "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)
print(f"variants_metadata.json: {len(records)} records across {len(SLUGS)} memes")
