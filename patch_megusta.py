"""Add 3 new Me Gusta records and rebuild both JSON files."""
import json

MEME_NS = "https://purl.org/memo#"

NEW_RECORDS = [
    {
        "photoId": "844118", "variantIndex": 8,
        "memeSlug": "me-gusta", "memeName": "Me Gusta",
        "memeConceptIRI": "https://purl.org/memo#me-gusta",
        "variantInstanceIRI": f"{MEME_NS}photo_844118",
        "variantTitle": "Me Gustavo", "variantUploader": "prisius",
        "img_alt": "me gusta ",
        "imageURL": "https://i.kym-cdn.com/photos/images/original/000/844/118/f7c.jpg",
        "transformationDimension": "CrossoverMerge",
        "transformationExtent": "Moderate",
    },
    {
        "photoId": "663014", "variantIndex": 9,
        "memeSlug": "me-gusta", "memeName": "Me Gusta",
        "memeConceptIRI": "https://purl.org/memo#me-gusta",
        "variantInstanceIRI": f"{MEME_NS}photo_663014",
        "variantTitle": "SpongeBob Se Gusta", "variantUploader": "gnbman",
        "img_alt": "I decided to color it.",
        "imageURL": "https://i.kym-cdn.com/photos/images/original/000/663/014/3ea.png",
        "transformationDimension": "CrossoverMerge",
        "transformationExtent": "Moderate",
    },
    {
        "photoId": "483461", "variantIndex": 10,
        "memeSlug": "me-gusta", "memeName": "Me Gusta",
        "memeConceptIRI": "https://purl.org/memo#me-gusta",
        "variantInstanceIRI": f"{MEME_NS}photo_483461",
        "variantTitle": "Me Gusta IRL", "variantUploader": "Brian",
        "img_alt": "MEMERASF COM",
        "imageURL": "https://i.kym-cdn.com/photos/images/original/000/483/461/588.jpg",
        "transformationDimension": "CompositionShift",
        "transformationExtent": "Moderate",
    },
]

CANONICAL_TYPE = {
    "big-chungus":            "Cartoon",
    "me-gusta":               "Drawing",
    "stonks":                 "Cartoon",
    "npc-wojak":              "Photograph",
    "woman-yelling-at-a-cat": "Photograph",
}

# ── Patch top5_variants_raw.json ──────────────────────────────────────────────
with open("top5_variants_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

existing_pids = {r["photoId"] for r in raw}
for rec in NEW_RECORDS:
    if rec["photoId"] not in existing_pids:
        raw.append(rec)

with open("top5_variants_raw.json", "w", encoding="utf-8") as f:
    json.dump(raw, f, indent=2, ensure_ascii=False)
print(f"top5_variants_raw.json: {len(raw)} records")

# ── Rebuild transformation_annotations.json ───────────────────────────────────
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

from collections import Counter
by_slug = Counter(r["memeSlug"] for r in raw)
print("\nVariants per meme:")
for slug, count in sorted(by_slug.items()):
    print(f"  {slug}: {count}")
