"""
scrape_d0_variants.py
---------------------
For each of the 50 D0 memes in d0.json, scrape 10 variants chosen randomly
across the full KYM photo gallery (not just page 1).

Strategy
--------
1. Fetch page 1 to detect how many gallery pages exist (via pagination links).
2. Build the full list of page numbers and shuffle it.
3. Fetch pages in random order, collecting unique photo items, until >= WANTED.
4. random.sample() exactly WANTED items from the pool.
5. Download images to  sampled_variants_d0/<slug>/
6. Write d0_variants_raw.json — same schema as transformation_annotations.json
   but with annotation fields left null, ready for manual completion.

Usage
-----
    python scrape_d0_variants.py [--wanted 10] [--proxy http://...]
"""

import os
import re
import sys
import time
import json
import random
import argparse
from pathlib import Path

sys.path.insert(0, ".")
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
WANTED      = 10
OUT_ROOT    = "sampled_variants_d0"
SLEEP_MIN   = 1.2
SLEEP_MAX   = 2.5
PROGRESS_F  = "d0_variants_progress.json"
RAW_OUT     = "d0_variants_raw.json"
MEME_NS     = "https://purl.org/memo#"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_progress() -> dict:
    if os.path.exists(PROGRESS_F):
        with open(PROGRESS_F, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_progress(prog: dict) -> None:
    tmp = PROGRESS_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prog, f, indent=2)
    os.replace(tmp, PROGRESS_F)

def sanitize(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)[:80]

def ext_from_url(url: str) -> str:
    path = url.split("?")[0]
    ext  = os.path.splitext(path)[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp") else ".jpg"

def img_url_to_original(url: str) -> str:
    return url.replace("/photos/images/masonry/", "/photos/images/original/")

def detect_max_page(soup: BeautifulSoup) -> int:
    """Return the highest page number found in pagination links, or 1."""
    max_page = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page

def extract_photo_items(html: str) -> list[dict]:
    """Parse gallery page HTML and return a list of photo item dicts."""
    soup  = BeautifulSoup(html, "html.parser")
    items = []
    seen  = set()
    for a in soup.select("a.item"):
        img = a.find("img")
        if not img:
            continue
        orig_url = img.get("data-image", "")
        if not orig_url:
            src = img.get("src", "")
            if "photos/images" not in src:
                continue
            orig_url = img_url_to_original(src)
        if not orig_url or orig_url in seen:
            continue
        seen.add(orig_url)

        href = a.get("href", "")
        photo_id_match = re.search(r"/photos/(\d+)", href)
        photo_id = photo_id_match.group(1) if photo_id_match else ""

        items.append({
            "photo_id":  photo_id,
            "photo_url": href,
            "title":     a.get("data-title", ""),
            "author":    a.get("data-author", ""),
            "img_alt":   img.get("alt", ""),
            "meme_name": a.get("data-entry-name", ""),
            "image_url": orig_url,
        })
    return items

def download_image(session, url: str, dest: str) -> bool:
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        if not r.headers.get("Content-Type", "").startswith("image/"):
            return False
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"    Download failed {url}: {e}")
        return False

# ── Random gallery collection ─────────────────────────────────────────────────

def collect_random_variants(session, photos_url: str, wanted: int) -> list[dict]:
    """
    Detect total gallery pages, shuffle them, fetch in random order until
    we have >= wanted unique photo items, then return a random sample of wanted.
    """
    # Step 1 — fetch page 1 to detect pagination
    html1 = fetch_html(session, photos_url)
    if not html1:
        print("  Could not fetch gallery page 1")
        return []

    soup1    = BeautifulSoup(html1, "html.parser")
    max_page = detect_max_page(soup1)
    items_p1 = extract_photo_items(html1)
    print(f"  Page 1: {len(items_p1)} photos — gallery has {max_page} page(s)")

    # Step 2 — build randomised page order (page 1 already fetched)
    all_pages = list(range(1, max_page + 1))
    random.shuffle(all_pages)

    pool      = {item["image_url"]: item for item in items_p1}
    fetched_pages = {1}

    # Step 3 — fetch more pages in random order until pool is large enough
    for page_num in all_pages:
        if len(pool) >= wanted or page_num in fetched_pages:
            continue
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        url  = f"{photos_url}?page={page_num}"
        html = fetch_html(session, url)
        if not html:
            print(f"  Page {page_num}: fetch failed")
            continue
        page_items = extract_photo_items(html)
        for item in page_items:
            pool.setdefault(item["image_url"], item)
        fetched_pages.add(page_num)
        print(f"  Page {page_num}: {len(page_items)} photos — pool now {len(pool)}")
        if len(pool) >= max(wanted * 2, 20):
            break  # enough candidates for a fair random sample

    # Step 4 — random sample
    candidates = list(pool.values())
    if len(candidates) <= wanted:
        return candidates
    return random.sample(candidates, wanted)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wanted", type=int, default=WANTED)
    parser.add_argument("--proxy",  default=None)
    args = parser.parse_args()

    with open("d0.json", encoding="utf-8") as f:
        d0 = json.load(f)

    session  = make_session(proxy=args.proxy)
    progress = load_progress()
    os.makedirs(OUT_ROOT, exist_ok=True)

    # Load existing raw output so we can append without losing prior work
    if os.path.exists(RAW_OUT):
        with open(RAW_OUT, encoding="utf-8") as f:
            raw_records: list = json.load(f)
    else:
        raw_records = []

    done_slugs = {r["memeSlug"] for r in raw_records}

    for idx, entry in enumerate(d0, 1):
        slug     = entry["slug"]
        title    = entry["title"]
        meme_url = entry["meme_url"]

        if slug in done_slugs:
            print(f"[{idx}/50] Skip (already done): {slug}")
            continue

        photos_url = meme_url.rstrip("/") + "/photos"
        entry_dir  = os.path.join(OUT_ROOT, sanitize(slug))
        os.makedirs(entry_dir, exist_ok=True)

        print(f"\n[{idx}/50] {title} ({slug})")

        chosen = collect_random_variants(session, photos_url, args.wanted)
        if not chosen:
            print(f"  No variants found — skipping")
            progress[slug] = "no_variants"
            save_progress(progress)
            continue

        # Download and build records
        for i, item in enumerate(chosen, 1):
            img_url = item["image_url"]
            base    = sanitize(os.path.splitext(os.path.basename(img_url.split("?")[0]))[0])
            ext     = ext_from_url(img_url)
            fname   = f"{i:02}_{base}{ext}"
            dest    = os.path.join(entry_dir, fname)

            if not os.path.exists(dest):
                ok = download_image(session, img_url, dest)
                if ok:
                    print(f"  [{i}/{len(chosen)}] Downloaded: {fname}")
                else:
                    print(f"  [{i}/{len(chosen)}] Failed:     {fname}")
                time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
            else:
                print(f"  [{i}/{len(chosen)}] Exists:     {fname}")

            photo_id = item.get("photo_id", "")
            raw_records.append({
                # identity
                "photoId":          photo_id,
                "variantIndex":     i,
                "memeSlug":         slug,
                "memeName":         title,
                "memeConceptIRI":   entry["meme_concept_iri"],
                "variantInstanceIRI": f"{MEME_NS}photo_{photo_id}" if photo_id else "",
                # scraped metadata
                "variantTitle":     item.get("title", ""),
                "variantUploader":  item.get("author", ""),
                "imageURL":         img_url,
                "localFile":        os.path.join(entry_dir, fname),
                # annotation fields — to be completed manually
                "captionText":             None,
                "canonicalImageType":      None,
                "variantImageType":        None,
                "transformationDimension": None,
                "transformationExtent":    None,
                "notes":                   None,
            })

        # Save after each meme
        tmp = RAW_OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw_records, f, indent=4, ensure_ascii=False)
        os.replace(tmp, RAW_OUT)

        progress[slug] = "done"
        save_progress(progress)
        print(f"  -> {len(chosen)} variants saved  [{len(raw_records)} total records]")

    print(f"\nDone. Raw records written to: {RAW_OUT}")
    print("Fill in the null annotation fields, then replace transformation_annotations.json.")

if __name__ == "__main__":
    main()
