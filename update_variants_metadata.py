"""Rebuild variants_metadata.json from the 5 selected sampled_variants folders."""
import json, os

SLUGS = [
    "stonks",
    "surprised-pikachu",
    "steven-crowders-change-my-mind-campus-sign",
    "npc-wojak",
    "me-and-the-boys",
]
SRC_BASE = "sampled_variants"

records = []
for slug in SLUGS:
    meta_path = os.path.join(SRC_BASE, slug, "metadata.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    for m in meta:
        rec = dict(m)
        rec["folder"] = slug
        records.append(rec)

with open("variants_metadata.json", "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)
print(f"variants_metadata.json: {len(records)} records across {len(SLUGS)} memes")
