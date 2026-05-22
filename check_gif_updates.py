"""
For each entry in metadata.json whose image_url does NOT already end in .gif,
fetch the meme page and look for an animated GIF that is the entry's OWN ICON
(URL path must contain entries/icons/).  Gallery submissions (photos/images/,
photos/newsfeed/, etc.) are never used as updates.

If a valid entry-icon GIF is found:
  - download it to images_flat/ (replacing the old static file)
  - replace the file in images/<slug>/ if that folder exists
  - update image_url, image_filename, image_path in metadata.json

Checkpoints every CHECKPOINT_EVERY entries so interruptions are safe.
Run AFTER the classifier has finished.
"""
import json
import time
import random
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests

from memescrape import _find_gif_in_page, make_session, fetch_html, _resolve_ext

BASE          = Path(__file__).parent
META_PATH     = BASE / 'metadata.json'
PROGRESS_PATH = BASE / 'gif_check_progress.json'
CHECKPOINT_EVERY = 20


def load_progress():
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_progress(checked_ids):
    with open(PROGRESS_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(checked_ids), f)


def find_in_images_folder(slug, entry_id):
    """Return the first file in images/<slug>/ whose stem starts with the zero-padded id."""
    folder = BASE / 'images' / slug
    if not folder.is_dir():
        return None
    prefix = f"{entry_id:04d}_"
    for f in folder.iterdir():
        if f.name.startswith(prefix):
            return f
    return None


def update_entry(entry, gif_url, raw_gif):
    entry_id  = entry['id']
    meme_slug = entry['meme_url'].rstrip('/').split('/')[-1]

    # New flat filename always uses .gif
    new_flat_name = f"{entry_id:04d}_{meme_slug}.gif"
    new_flat_path = BASE / 'images_flat' / new_flat_name

    # Remove all stale flat files for this entry
    for old in (BASE / 'images_flat').glob(f"{entry_id:04d}_{meme_slug}.*"):
        old.unlink()

    new_flat_path.write_bytes(raw_gif)

    # Update images/<slug>/ if the folder exists
    old_in_folder = find_in_images_folder(meme_slug, entry_id)
    if old_in_folder:
        new_in_folder = old_in_folder.parent / new_flat_name
        if old_in_folder != new_in_folder:
            old_in_folder.unlink()
        new_in_folder.write_bytes(raw_gif)

    # Update metadata fields
    entry['image_url']      = gif_url
    entry['image_filename'] = new_flat_name
    entry['image_path']     = str(Path('images_flat') / new_flat_name)

    return True


def main():
    with open(META_PATH, encoding='utf-8') as f:
        data = json.load(f)

    checked_ids = load_progress()

    # Only process entries that are not already GIFs and not yet checked
    candidates = [
        e for e in data
        if Path(urlparse(e.get('image_url', '')).path).suffix.lower() != '.gif'
        and str(e['id']) not in checked_ids
    ]

    already_gif  = sum(1 for e in data
                       if Path(urlparse(e.get('image_url', '')).path).suffix.lower() == '.gif')
    print(f"Entries to check : {len(candidates)}")
    print(f"Already GIF      : {already_gif}")
    print(f"Already checked  : {len(checked_ids)}")

    session = make_session()
    updated   = 0
    processed = 0

    for i, entry in enumerate(candidates, 1):
        entry_id  = entry['id']
        meme_slug = entry['meme_url'].rstrip('/').split('/')[-1]

        print(f"[{i}/{len(candidates)}] {meme_slug}", end=" ... ", flush=True)

        html = fetch_html(session, entry['meme_url'])
        if not html:
            print("fetch failed")
            checked_ids.add(str(entry_id))
            processed += 1
            if processed % CHECKPOINT_EVERY == 0:
                _checkpoint(data, checked_ids)
            time.sleep(random.uniform(2.0, 4.0))
            continue

        soup    = BeautifulSoup(html, 'html.parser')
        gif_url = _find_gif_in_page(soup, html)

        if not gif_url:
            print("no entry-icon gif")
            checked_ids.add(str(entry_id))
            processed += 1
            if processed % CHECKPOINT_EVERY == 0:
                _checkpoint(data, checked_ids)
            time.sleep(random.uniform(1.5, 3.0))
            continue

        # Download and validate the GIF
        try:
            r = session.get(gif_url, timeout=30, allow_redirects=True)
            r.raise_for_status()
            raw = r.content
            if raw[:3] != b'GIF':
                print(f"not a valid GIF (magic={raw[:4]!r})")
                checked_ids.add(str(entry_id))
                processed += 1
                if processed % CHECKPOINT_EVERY == 0:
                    _checkpoint(data, checked_ids)
                time.sleep(random.uniform(1.5, 3.0))
                continue

            update_entry(entry, gif_url, raw)
            updated += 1
            print(f"updated -> {entry['image_filename']} ({len(raw)//1024} KB)")
        except Exception as e:
            print(f"download error: {e}")

        checked_ids.add(str(entry_id))
        processed += 1

        if processed % CHECKPOINT_EVERY == 0:
            _checkpoint(data, checked_ids)

        time.sleep(random.uniform(2.0, 4.5))

    _checkpoint(data, checked_ids)
    session.close()
    print(f"\nDone -- {updated} entries updated with entry-icon GIFs.")


def _checkpoint(data, checked_ids):
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    save_progress(checked_ids)
    print(f"  [checkpoint] {len(checked_ids)} checked so far")


if __name__ == '__main__':
    main()
