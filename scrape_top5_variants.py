"""
scrape_top5_variants.py
-----------------------
Collect 10 randomly-sampled gallery variants for the top 5 D0 memes by views.
Outputs top5_variants_raw.json — image URLs + metadata, no images downloaded.
"""

import json, re, random, time, sys, os
sys.path.insert(0, ".")
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

WANTED   = 10
OUT_FILE = "top5_variants_raw.json"
MEME_NS  = "https://purl.org/memo#"

SLEEP_MIN, SLEEP_MAX = 1.0, 2.0

TOP5_SLUGS = [
    "big-chungus",
    "me-gusta",
    "stonks",
    "npc-wojak",
    "woman-yelling-at-a-cat",
]

# Per-slug title keyword blocklists (lowercase)
BLOCKLIST_TITLE = {
    "me-gusta": ["nft"],
}

# Per-slug photo ID blocklists
BLOCKLIST_PHOTO_ID = {
    "me-gusta": {"2093625"},  # creator portrait (May Oswald)
}

# Global URL suffix blocklist
BLOCKLIST_URL_EXT = [".pnj"]

def is_blocked(slug, item):
    title_lower = item.get("title", "").lower()
    for kw in BLOCKLIST_TITLE.get(slug, []):
        if kw in title_lower:
            return True
    if item.get("photo_id") in BLOCKLIST_PHOTO_ID.get(slug, set()):
        return True
    url = item.get("image_url", "")
    for ext in BLOCKLIST_URL_EXT:
        if url.lower().endswith(ext):
            return True
    return False

def detect_max_page(soup):
    max_page = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page

def extract_items(html):
    soup  = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for a in soup.select("a.item"):
        img = a.find("img")
        if not img:
            continue
        orig = img.get("data-image", "") or ""
        if not orig:
            src = img.get("src", "")
            if "photos/images" not in src:
                continue
            orig = src.replace("/masonry/", "/original/")
        if not orig or orig in seen:
            continue
        seen.add(orig)
        href = a.get("href", "")
        pid  = re.search(r"/photos/(\d+)", href)
        items.append({
            "photo_id":  pid.group(1) if pid else "",
            "title":     a.get("data-title", ""),
            "author":    a.get("data-author", ""),
            "img_alt":   img.get("alt", ""),
            "image_url": orig,
        })
    return items, soup

def collect_random(session, photos_url, wanted, slug=""):
    html1 = fetch_html(session, photos_url)
    if not html1:
        return []
    items1, soup1 = extract_items(html1)
    max_page = detect_max_page(soup1)
    print(f"  page 1: {len(items1)} items  |  total pages: {max_page}")

    pool = {it["image_url"]: it for it in items1 if not is_blocked(slug, it)}
    pages_left = list(range(2, max_page + 1))
    random.shuffle(pages_left)

    for pg in pages_left:
        if len(pool) >= wanted * 3:
            break
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        html = fetch_html(session, f"{photos_url}?page={pg}")
        if not html:
            continue
        page_items, _ = extract_items(html)
        for it in page_items:
            if not is_blocked(slug, it):
                pool.setdefault(it["image_url"], it)
        print(f"  page {pg}: {len(page_items)} items  |  pool: {len(pool)}")

    candidates = list(pool.values())
    return random.sample(candidates, min(wanted, len(candidates)))

def main():
    with open("d0.json") as f:
        d0 = {e["slug"]: e for e in json.load(f)}

    session = make_session()
    records = []

    for slug in TOP5_SLUGS:
        entry      = d0[slug]
        meme_url   = entry["meme_url"]
        title      = entry["title"]
        photos_url = meme_url.rstrip("/") + "/photos"

        print(f"\n-- {title} ({slug})")
        chosen = collect_random(session, photos_url, WANTED, slug=slug)
        print(f"  -> {len(chosen)} variants selected")

        for i, it in enumerate(chosen, 1):
            records.append({
                "photoId":             it["photo_id"],
                "variantIndex":        i,
                "memeSlug":            slug,
                "memeName":            title,
                "memeConceptIRI":      entry["meme_concept_iri"],
                "variantInstanceIRI":  f"{MEME_NS}photo_{it['photo_id']}" if it["photo_id"] else "",
                "variantTitle":        it.get("title", ""),
                "variantUploader":     it.get("author", ""),
                "img_alt":             it.get("img_alt", ""),
                "imageURL":            it["image_url"],
                "transformationDimension": None,
                "transformationExtent":    None,
            })

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\nWritten {len(records)} records -> {OUT_FILE}")

if __name__ == "__main__":
    main()
