"""
Fix sampled_variants for Surprised Pikachu and Steven Crowder:
 - Delete specified files
 - Scrape replacement images from KYM gallery
 - Update each folder's metadata.json
 - Renumber files 01-10 sequentially
"""
import json, re, os, sys, time, shutil
sys.path.insert(0, ".")
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

MEME_NS  = "https://purl.org/memo#"
BASE_DIR = "sampled_variants"

# ── Config: what to delete and how many replacements to scrape ────────────────
DELETE = {
    "surprised-pikachu": [
        "01_5c4.jpeg","02_710.jpg","03_541.jpeg","04_b56.png","06_f82.jpeg"
    ],
    "steven-crowders-change-my-mind-campus-sign": [
        "04_273.jpg"
    ],
}
# photo IDs that were removed (so scraper skips them)
REMOVED_IDS = {
    "surprised-pikachu": {"3262056","3216536","3194015","3175479","3118321"},
    "steven-crowders-change-my-mind-campus-sign": {"3162300"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def ext_from_url(url, ct=""):
    path = url.split("?")[0]
    e    = os.path.splitext(path)[1].lower()
    if e in (".jpg",".jpeg",".png",".gif",".webp"): return e
    if "gif" in ct: return ".gif"
    if "png" in ct: return ".png"
    return ".jpg"

def scrape_gallery_pages(session, gallery_url, used_ids, wanted):
    """Return `wanted` unique items not in used_ids, scanning gallery pages."""
    collected = []
    page = 1
    while len(collected) < wanted:
        url  = gallery_url + (f"?page={page}" if page > 1 else "")
        html = fetch_html(session, url)
        if not html:
            break
        soup   = BeautifulSoup(html, "html.parser")
        found  = 0
        for a in soup.select("a.item"):
            img = a.find("img")
            if not img:
                continue
            orig = img.get("data-image","") or ""
            if not orig:
                src = img.get("src","")
                if "photos/images" not in src: continue
                orig = src.replace("/masonry/","/original/")
            if not orig: continue
            href  = a.get("href","")
            pid_m = re.search(r"/photos/(\d+)", href)
            pid   = pid_m.group(1) if pid_m else ""
            if pid in used_ids or pid in {c["photo_id"] for c in collected}:
                continue
            collected.append({
                "photo_id":  pid,
                "photo_url": href,
                "title":     a.get("data-title",""),
                "author":    a.get("data-author",""),
                "img_alt":   img.get("alt",""),
                "meme_name": a.get("data-entry-name",""),
                "image_url": orig,
            })
            found += 1
            if len(collected) >= wanted:
                break
        print(f"  page {page}: found {found} candidates | total {len(collected)}")
        if found == 0:
            break
        page += 1
        time.sleep(1.5)
    return collected[:wanted]

def download_image(session, url, dest):
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get("Content-Type","")
        if not ct.startswith("image/"):
            return False
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"  Download failed {url}: {e}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────
session = make_session()

for slug, delete_files in DELETE.items():
    folder = os.path.join(BASE_DIR, slug)
    meta_path = os.path.join(folder, "metadata.json")

    print(f"\n=== {slug} ===")

    # Load existing metadata
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    # Delete specified files and remove from metadata
    removed_ids   = REMOVED_IDS[slug]
    del_filenames  = set(delete_files)
    meta_by_fname  = {m["filename"]: m for m in meta}

    for fname in delete_files:
        fpath = os.path.join(folder, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"  Deleted {fname}")
        else:
            print(f"  (already gone) {fname}")

    # Keep records whose filename is NOT in delete list
    kept = [m for m in meta if m["filename"] not in del_filenames]
    print(f"  Kept {len(kept)} records after deletion")

    # Scrape replacements
    n_needed = 10 - len(kept)
    print(f"  Scraping {n_needed} replacements...")
    gallery_url = f"https://knowyourmeme.com/memes/{slug}/photos"
    all_used    = removed_ids | {m["photo_id"] for m in kept}
    new_items   = scrape_gallery_pages(session, gallery_url, all_used, n_needed)
    print(f"  Got {len(new_items)} new candidates")

    # Download new items
    for it in new_items:
        url = it["image_url"]
        try:
            resp = session.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            ct  = resp.headers.get("Content-Type","")
            ext = ext_from_url(url, ct)
            # temporary filename, will be renumbered below
            basename  = url.split("?")[0].split("/")[-1][:8].lstrip("/")
            tmp_fname = f"new_{it['photo_id']}{ext}"
            dest      = os.path.join(folder, tmp_fname)
            with open(dest, "wb") as fh:
                fh.write(resp.content)
            it["_tmp"] = tmp_fname
            print(f"  Downloaded {tmp_fname}  ({len(resp.content)//1024}kB)")
        except Exception as e:
            print(f"  FAIL {it['photo_id']}: {e}")
            it["_tmp"] = None
        time.sleep(1.2)

    # Build combined + re-indexed list
    combined = list(kept)
    for it in new_items:
        if it.get("_tmp"):
            combined.append({
                "photo_id":  it["photo_id"],
                "photo_url": it["photo_url"],
                "title":     it["title"],
                "author":    it["author"],
                "img_alt":   it["img_alt"],
                "meme_name": it.get("meme_name",""),
                "image_url": it["image_url"],
                "filename":  it["_tmp"],  # will be updated below
                "index":     -1,
            })

    # Re-number files 01-10
    new_meta = []
    for new_idx, record in enumerate(combined, 1):
        old_fname = record["filename"]
        old_path  = os.path.join(folder, old_fname)
        # derive new filename from URL tail
        url_tail  = record["image_url"].split("?")[0].split("/")[-1]
        ext       = os.path.splitext(url_tail)[1] or os.path.splitext(old_fname)[1]
        short     = url_tail[:8].lstrip("/")
        new_fname = f"{new_idx:02}_{short}{ext}" if not url_tail.endswith(ext) else f"{new_idx:02}_{url_tail}"
        new_path  = os.path.join(folder, new_fname)
        if old_fname != new_fname and os.path.exists(old_path):
            os.rename(old_path, new_path)
        record["filename"] = new_fname
        record["index"]    = new_idx
        new_meta.append(record)

    # Write metadata.json
    out = [{k: v for k, v in m.items() if not k.startswith("_")} for m in new_meta]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"  metadata.json updated: {len(out)} records")

print("\nDone.")
