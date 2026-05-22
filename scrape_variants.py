"""
scrape_variants.py
------------------
For each of the 50 entries in sampled_dataset.json, download up to 10 variant
images from the KYM photos gallery and save them to:

  sampled_variants/
    <slug>/
      01_<filename>.<ext>
      02_<filename>.<ext>
      ...
"""

import os
import re
import sys
import time
import json
import random

sys.path.insert(0, '.')
from memescrape import make_session, fetch_html

from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
WANTED      = 10          # variants per entry
OUT_ROOT    = 'sampled_variants'
SLEEP_MIN   = 1.2
SLEEP_MAX   = 2.2
PROGRESS_F  = 'variants_progress.json'

# ── Helpers ───────────────────────────────────────────────────────────────────

def slug_from_url(meme_url):
    return meme_url.rstrip('/').split('/')[-1]

def sanitize(name):
    return re.sub(r'[^\w\-.]', '_', name)[:80]

def load_progress():
    if os.path.exists(PROGRESS_F):
        with open(PROGRESS_F, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_progress(prog):
    tmp = PROGRESS_F + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(prog, f, indent=2)
    os.replace(tmp, PROGRESS_F)

def img_url_to_original(masonry_url):
    """Convert masonry thumbnail URL to original-size URL."""
    return masonry_url.replace('/photos/images/masonry/', '/photos/images/original/')

def extract_photo_items(html):
    """Return a list of dicts with metadata + original image URL for each gallery item.

    Only selects <a class="item"> links — these are the actual meme gallery
    submissions. <a class="result"> links are unrelated trending/sidebar photos
    and are deliberately skipped.

    Uses data-image (already original size) from the <img> tag instead of
    rewriting the masonry URL, which is more reliable.
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    seen = set()
    for a in soup.select('a.item'):
        img = a.find('img')
        if not img:
            continue
        # Prefer data-image (original), fall back to src + masonry→original swap
        orig_url = img.get('data-image', '')
        if not orig_url:
            src = img.get('src', '')
            if 'photos/images' not in src:
                continue
            orig_url = img_url_to_original(src)
        if not orig_url or orig_url in seen:
            continue
        seen.add(orig_url)

        # Extract photo ID from href
        href = a.get('href', '')
        photo_id_match = re.search(r'/photos/(\d+)', href)
        photo_id = photo_id_match.group(1) if photo_id_match else ''

        items.append({
            'photo_id':    photo_id,
            'photo_url':   href,
            'title':       a.get('data-title', ''),
            'author':      a.get('data-author', ''),
            'img_alt':     img.get('alt', ''),
            'meme_name':   a.get('data-entry-name', ''),
            'image_url':   orig_url,
        })
    return items

def download_file(session, url, dest_path):
    """Download url to dest_path. Returns True on success."""
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get('Content-Type', '')
        if not ct.startswith('image/'):
            return False
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f'    Download failed {url}: {e}')
        return False

def ext_from_url(url):
    path = url.split('?')[0]
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp') else '.jpg'

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open('sampled_dataset.json', encoding='utf-8') as f:
        dataset = json.load(f)

    session  = make_session()
    progress = load_progress()
    os.makedirs(OUT_ROOT, exist_ok=True)

    total_entries = len(dataset)
    for idx, entry in enumerate(dataset, 1):
        meme_url = entry.get('meme_url', '')
        slug     = slug_from_url(meme_url)
        title    = entry.get('title', slug)
        folder   = sanitize(slug)

        photos_url  = meme_url.rstrip('/') + '/photos'
        entry_dir   = os.path.join(OUT_ROOT, folder)

        # Count images already downloaded (exclude metadata.json)
        existing = [f for f in os.listdir(entry_dir)
                    if f != 'metadata.json' and os.path.isfile(os.path.join(entry_dir, f))]\
                   if os.path.isdir(entry_dir) else []
        if len(existing) >= WANTED:
            print(f'[{idx}/{total_entries}] Skip (complete {len(existing)} imgs): {folder}')
            continue

        print(f'[{idx}/{total_entries}] {folder} ({len(existing)} imgs so far)')
        os.makedirs(entry_dir, exist_ok=True)

        # Collect up to WANTED photo items (paginate if needed)
        collected = []
        page = 1
        while len(collected) < WANTED:
            url = photos_url if page == 1 else f'{photos_url}?page={page}'
            html = fetch_html(session, url)
            if not html:
                print(f'  Page {page}: fetch failed')
                break
            page_items = extract_photo_items(html)
            if not page_items:
                print(f'  Page {page}: no photos found')
                break
            for item in page_items:
                if item['image_url'] not in {c['image_url'] for c in collected}:
                    collected.append(item)
            print(f'  Page {page}: {len(page_items)} photos found (total so far: {len(collected)})')
            if len(page_items) < 16:
                break  # last page
            page += 1
            time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

        to_download = collected[:WANTED]
        downloaded  = 0
        saved_meta  = []

        for i, item in enumerate(to_download, 1):
            img_url = item['image_url']
            base = sanitize(os.path.splitext(os.path.basename(img_url.split('?')[0]))[0])
            ext  = ext_from_url(img_url)
            fname = f'{i:02}_{base}{ext}'
            dest  = os.path.join(entry_dir, fname)

            if os.path.exists(dest):
                print(f'  [{i}/{len(to_download)}] Already exists: {fname}')
                downloaded += 1
            else:
                ok = download_file(session, img_url, dest)
                if ok:
                    downloaded += 1
                    print(f'  [{i}/{len(to_download)}] OK: {fname}')
                time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

            saved_meta.append({**item, 'filename': fname, 'index': i})

        # Write per-folder metadata JSON
        meta_path = os.path.join(entry_dir, 'metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(saved_meta, f, ensure_ascii=False, indent=2)

        print(f'  -> {downloaded}/{len(to_download)} downloaded, metadata.json written')

        # Mark done in progress using sanitized folder name
        if downloaded > 0 or len(to_download) == 0:
            progress[folder] = 'done'
            save_progress(progress)

    print(f'\nAll done. Variants saved to: {OUT_ROOT}/')
    consolidate_metadata()


def consolidate_metadata():
    """Merge all per-folder metadata.json files into one master variants_metadata.json."""
    master = []
    folders = sorted(os.listdir(OUT_ROOT))
    for folder in folders:
        meta_path = os.path.join(OUT_ROOT, folder, 'metadata.json')
        if not os.path.exists(meta_path):
            continue
        with open(meta_path, encoding='utf-8') as f:
            items = json.load(f)
        for item in items:
            master.append({**item, 'folder': folder})

    out_path = 'variants_metadata.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print(f'Consolidated {len(master)} variant records -> {out_path}')

if __name__ == '__main__':
    main()
