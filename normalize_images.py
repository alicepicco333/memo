import json
import os
import shutil
from pathlib import Path

BASE = Path(__file__).parent
SRC_ROOT = BASE / 'images'
DST_ROOT = BASE / 'images_flat'
META_IN = BASE / 'metadata.json'
META_OUT = BASE / 'metadata.json'

DST_ROOT.mkdir(exist_ok=True)

with open(META_IN, encoding='utf-8') as f:
    data = json.load(f)

copied = 0
skipped = 0
missing = 0

for entry in data:
    meme_slug = entry['meme_url'].rstrip('/').split('/')[-1]
    src = BASE / entry['image_path']

    if not src.exists():
        print(f"MISSING: {src}")
        missing += 1
        continue

    ext = src.suffix.lower()
    new_filename = f"{entry['id']:04d}_{meme_slug}{ext}"
    dst = DST_ROOT / new_filename

    if dst.exists():
        skipped += 1
    else:
        shutil.copy2(src, dst)
        copied += 1

    entry['image_filename'] = new_filename
    entry['image_path'] = str(Path('images_flat') / new_filename)

with open(META_OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Done — copied: {copied}, already existed: {skipped}, missing source: {missing}")
print(f"metadata.json updated with new image_filename and image_path fields.")
