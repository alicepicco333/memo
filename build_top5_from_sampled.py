"""
Build top5_variants_raw.json and transformation_annotations.json
from sampled_variants/ for the 5 selected memes.
"""
import json, os

MEME_NS  = "https://purl.org/memo#"
SRC_BASE = "sampled_variants"

SLUGS = [
    "stonks",
    "surprised-pikachu",
    "steven-crowders-change-my-mind-campus-sign",
    "npc-wojak",
    "me-and-the-boys",
]

MEME_TITLES = {
    "stonks":                                       "Stonks",
    "surprised-pikachu":                            "Surprised Pikachu",
    "steven-crowders-change-my-mind-campus-sign":   "Steven Crowders Change My Mind Campus Sign",
    "npc-wojak":                                    "Npc Wojak",
    "me-and-the-boys":                              "Me And The Boys",
}

CANONICAL_TYPE = {
    "stonks":                                       "Cartoon",
    "surprised-pikachu":                            "Drawing",
    "steven-crowders-change-my-mind-campus-sign":   "Photograph",
    "npc-wojak":                                    "Photograph",
    "me-and-the-boys":                              "Cartoon",
}

# photo_id → (dimension, extent)
ANNOTATIONS = {
    # Stonks
    "3171622": (["CaptionChange"],                              "Minimal"),
    "3039073": (["CrossoverMerge","StyleShift","CaptionChange"],"Substantial"),
    "2849405": (["CrossoverMerge","StyleShift"],                "Moderate"),
    "2694210": (["CrossoverMerge","CompositionShift"],          "Moderate"),
    "2623851": (["MediumShift","StyleShift","CrossoverMerge"],  "Substantial"),
    "2481174": (["MediumShift","StyleShift"],                   "Moderate"),
    "2330119": (["CaptionChange","StyleShift"],                 "Moderate"),
    "2163672": (["MediumShift"],                                "Moderate"),
    "2130917": (["CaptionChange"],                              "Minimal"),
    "2074124": (["CrossoverMerge","CompositionShift"],          "Substantial"),
    # Surprised Pikachu
    "3157255": (["CaptionChange"],                     "Minimal"),
    "3099494": (["CaptionChange","CompositionShift"],  "Moderate"),
    "3037094": (["CaptionChange"],                     "Minimal"),
    "3023384": (["CaptionChange"],                     "Minimal"),
    "2970115": (["CaptionChange"],                     "Minimal"),
    "2956566": (["StyleShift"],                        "Moderate"),
    "2943637": (["StyleShift","MediumShift"],          "Substantial"),
    "2921812": (["CompositionShift"],                  "Moderate"),
    "2914754": (["CaptionChange"],                     "Minimal"),
    "2880832": (["MediumShift"],                       "Substantial"),
    # Steven Crowder
    "3259491": (["CrossoverMerge","MediumShift"], "Substantial"),
    "3183766": (["CaptionChange"],                "Minimal"),
    "3177961": (["CaptionChange"],                "Minimal"),
    "3144027": (["CaptionChange"],                "Minimal"),
    "3109813": (["CaptionChange"],                "Minimal"),
    "3105752": (["CaptionChange"],                "Minimal"),
    "3093681": (["CaptionChange"],                "Minimal"),
    "3045918": (["CaptionChange"],                "Minimal"),
    "2977772": (["CrossoverMerge","MediumShift"], "Substantial"),
    "2963518": (["CrossoverMerge","MediumShift"], "Moderate"),
    # NPC Wojak
    "3079818": (["CompositionShift"],              "Moderate"),
    "3056413": (["CaptionChange","CompositionShift"],"Minimal"),
    "3041478": (["CaptionChange","CompositionShift"],"Moderate"),
    "3019094": (["CompositionShift"],              "Moderate"),
    "2995566": (["CrossoverMerge","StyleShift"],   "Moderate"),
    "2939233": (["StyleShift"],                    "Substantial"),
    "2769512": (["CompositionShift"],              "Moderate"),
    "2755458": (["StyleShift","MediumShift"],      "Moderate"),
    "2719952": (["CompositionShift"],              "Moderate"),
    "2712445": (["CompositionShift"],              "Moderate"),
    # Me and the Boys
    "3234426": (["CompositionShift"],                      "Moderate"),
    "3055475": (["CaptionChange"],                         "Minimal"),
    "2984526": (["StyleShift"],                            "Moderate"),
    "2963907": (["CrossoverMerge"],                        "Moderate"),
    "2884868": (["CrossoverMerge"],                        "Moderate"),
    "2801960": (["CrossoverMerge"],                        "Moderate"),
    "2798169": (["StyleShift"],                            "Moderate"),
    "2788822": (["CrossoverMerge"],                        "Substantial"),
    "2769556": (["CrossoverMerge","CaptionChange"],         "Substantial"),
    "2681340": (["CrossoverMerge"],                        "Moderate"),
}

raw_records   = []
ta_records    = []

for slug in SLUGS:
    meta_path = os.path.join(SRC_BASE, slug, "metadata.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    title    = MEME_TITLES[slug]
    concept  = f"{MEME_NS}{slug}"
    can_type = CANONICAL_TYPE[slug]

    for m in meta:
        pid  = m["photo_id"]
        dim, ext = ANNOTATIONS.get(pid, (None, None))
        ext_file = os.path.splitext(m["filename"])[1]
        local    = os.path.join(SRC_BASE, slug, m["filename"])

        raw_records.append({
            "photoId":              pid,
            "variantIndex":         m["index"],
            "memeSlug":             slug,
            "memeName":             title,
            "memeConceptIRI":       concept,
            "variantInstanceIRI":   f"{MEME_NS}photo_{pid}",
            "variantTitle":         m.get("title", ""),
            "variantUploader":      m.get("author", ""),
            "img_alt":              m.get("img_alt", ""),
            "imageURL":             m.get("image_url", ""),
            "localFile":            local,
            "transformationDimension": dim,
            "transformationExtent":    ext,
        })

        ta_records.append({
            "photoId":              pid,
            "variantIndex":         m["index"],
            "memeName":             title,
            "memeConceptIRI":       concept,
            "variantInstanceIRI":   f"{MEME_NS}photo_{pid}",
            "variantTitle":         m.get("title", ""),
            "variantUploader":      m.get("author", ""),
            "captionText":          m.get("img_alt", ""),
            "canonicalImageType":   can_type,
            "variantImageType":     None,
            "transformationDimension": dim,
            "transformationExtent":    ext,
            "imageURL":             m.get("image_url", ""),
        })

with open("top5_variants_raw.json", "w", encoding="utf-8") as f:
    json.dump(raw_records, f, indent=2, ensure_ascii=False)

with open("transformation_annotations.json", "w", encoding="utf-8") as f:
    json.dump(ta_records, f, indent=2, ensure_ascii=False)

from collections import Counter
by_slug = Counter(r["memeSlug"] for r in raw_records)
print(f"top5_variants_raw.json:        {len(raw_records)} records")
print(f"transformation_annotations.json: {len(ta_records)} records")
print("\nPer meme:")
for slug in SLUGS:
    print(f"  {slug}: {by_slug[slug]}")
