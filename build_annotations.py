"""
Patch top5_variants_raw.json with transformation annotations for the new
big-chungus / me-gusta / stonks entries, remove 2076348, re-index Me Gusta,
then rebuild transformation_annotations.json.
"""
import json, os

# ---------------------------------------------------------------------------
# Transformation annotations for the 28 new images
# ---------------------------------------------------------------------------
ANNOTATIONS = {
    # Big Chungus
    "2159829": ("StyleShift",       "Moderate"),
    "2152539": ("MediumShift",      "Substantial"),
    "2232636": ("CaptionChange",    "Minimal"),
    "3223636": ("MediumShift",      "Substantial"),
    "2107495": ("MediumShift",      "Substantial"),
    "2150764": ("CrossoverMerge",   "Moderate"),
    "2435116": ("CompositionShift", "Moderate"),
    "2152472": ("CompositionShift", "Moderate"),
    "2076947": ("MediumShift",      "Moderate"),
    "2150124": ("CaptionChange",    "Minimal"),
    # Me Gusta
    "1941912": ("CompositionShift", "Moderate"),
    "3055187": ("CaptionChange",    "Minimal"),
    "2634604": ("MediumShift",      "Substantial"),
    "2093626": ("StyleShift",       "Moderate"),
    "1358553": ("CrossoverMerge",   "Moderate"),
    "1484749": ("CompositionShift", "Moderate"),
    "1945179": ("CrossoverMerge",   "Moderate"),
    # Stonks
    "2074124": ("CompositionShift", "Moderate"),
    "2047395": ("CompositionShift", "Moderate"),
    "3039073": ("CrossoverMerge",   "Moderate"),
    "3171622": ("CaptionChange",    "Minimal"),
    "2849405": ("StyleShift",       "Moderate"),
    "2047398": ("CompositionShift", "Moderate"),
    "2330119": ("CrossoverMerge",   "Moderate"),
    "2047394": ("MediumShift",      "Minimal"),
    "2067702": ("CaptionChange",    "Minimal"),
    "2065588": ("CaptionChange",    "Minimal"),
}

CANONICAL_TYPE = {
    "big-chungus":            "Cartoon",
    "me-gusta":               "Drawing",
    "stonks":                 "Cartoon",
    "npc-wojak":              "Photograph",
    "woman-yelling-at-a-cat": "Photograph",
}

REMOVE_IDS = {"2076348"}

# ---------------------------------------------------------------------------
# 1. Patch top5_variants_raw.json
# ---------------------------------------------------------------------------
with open("top5_variants_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

# Remove blocked IDs
raw = [r for r in raw if r["photoId"] not in REMOVE_IDS]

# Apply annotations
for r in raw:
    pid = r["photoId"]
    if pid in ANNOTATIONS:
        r["transformationDimension"], r["transformationExtent"] = ANNOTATIONS[pid]

# Re-index Me Gusta variants
mg_idx = 1
for r in raw:
    if r["memeSlug"] == "me-gusta":
        r["variantIndex"] = mg_idx
        mg_idx += 1

with open("top5_variants_raw.json", "w", encoding="utf-8") as f:
    json.dump(raw, f, indent=2, ensure_ascii=False)
print(f"top5_variants_raw.json: {len(raw)} records")

# ---------------------------------------------------------------------------
# 2. Rebuild transformation_annotations.json
# ---------------------------------------------------------------------------
MEME_NS = "https://purl.org/memo#"

records = []
for r in raw:
    slug = r["memeSlug"]
    records.append({
        "photoId":              r["photoId"],
        "variantIndex":         r["variantIndex"],
        "memeName":             r["memeName"],
        "memeConceptIRI":       r["memeConceptIRI"],
        "variantInstanceIRI":   r["variantInstanceIRI"],
        "variantTitle":         r.get("variantTitle", ""),
        "variantUploader":      r.get("variantUploader", ""),
        "captionText":          r.get("img_alt", ""),
        "canonicalImageType":   CANONICAL_TYPE.get(slug),
        "variantImageType":     None,
        "transformationDimension": r["transformationDimension"],
        "transformationExtent":    r["transformationExtent"],
        "imageURL":             r["imageURL"],
    })

with open("transformation_annotations.json", "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)
print(f"transformation_annotations.json: {len(records)} records")

# Quick summary
from collections import Counter
by_slug = Counter(r["memeSlug"] for r in raw)
print("\nVariants per meme:")
for slug, count in sorted(by_slug.items()):
    print(f"  {slug}: {count}")
