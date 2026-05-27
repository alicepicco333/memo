"""
make_d0_json.py
---------------
Generate d0.json — a clean listing of the 50 D0 MemeConcept entries,
combining slugs from meme_ontology_d0.owl with metadata from metadata_merged.json.
"""

import json
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS

MEME   = Namespace("https://purl.org/memo#")
SCHEMA = Namespace("https://schema.org/")

def slug_from_uri(uri: str) -> str:
    return uri.split("#")[-1]

def title_from_slug(slug: str) -> str:
    """Human-readable title from slug — strips leading underscore, capitalises."""
    clean = slug.lstrip("_").replace("-", " ")
    return clean.title()

def main():
    # ── Extract D0 slugs from ontology ───────────────────────────────────────
    g = Graph()
    g.parse("meme_ontology_d0.owl")
    concepts = sorted(
        slug_from_uri(str(s))
        for s in g.subjects(RDF.type, MEME.MemeConcept)
    )
    print(f"D0 MemeConcepts found: {len(concepts)}")

    # ── Load metadata_merged.json — index by slug AND by meme_url ────────────
    meta_by_slug: dict = {}
    meta_by_url:  dict = {}
    meta_path = Path("metadata_merged.json")
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            merged = json.load(f)
        for entry in merged:
            fn = entry.get("image_filename", "") or ""
            slug = re.sub(r"^\d{4}_", "", Path(fn).stem) if fn else ""
            if slug:
                meta_by_slug[slug] = entry
            url = entry.get("meme_url", "")
            if url:
                meta_by_url[url] = entry
        print(f"metadata_merged entries indexed: {len(meta_by_slug)}")
    else:
        print("Warning: metadata_merged.json not found — URLs will be inferred from slugs")

    # ── Build d0.json ─────────────────────────────────────────────────────────
    entries = []
    for slug in concepts:
        inferred_url = f"https://knowyourmeme.com/memes/{slug}"
        meta = meta_by_slug.get(slug) or meta_by_url.get(inferred_url) or {}
        meme_url = meta.get("meme_url") or inferred_url
        # metadata 'title' is the image filename — always derive from slug instead
        title = title_from_slug(slug)
        entries.append({
            "slug":             slug,
            "title":            title,
            "meme_url":         meme_url,
            "meme_concept_iri": f"https://purl.org/memo#{slug}",
            "photos":           meta.get("photos"),
            "views":            meta.get("views"),
        })

    out_path = Path("d0.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Written: {out_path}  ({len(entries)} entries)")

if __name__ == "__main__":
    main()
