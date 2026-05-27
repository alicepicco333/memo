"""Sync top5_imgs/ from the 5 selected sampled_variants folders."""
import json, os, shutil

SLUGS = [
    "stonks",
    "surprised-pikachu",
    "steven-crowders-change-my-mind-campus-sign",
    "npc-wojak",
    "me-and-the-boys",
]
SRC_BASE = "sampled_variants"
DEST_DIR = "top5_imgs"

# Clear top5_imgs
if os.path.exists(DEST_DIR):
    for f in os.listdir(DEST_DIR):
        os.remove(os.path.join(DEST_DIR, f))
    print(f"Cleared {DEST_DIR}/")
os.makedirs(DEST_DIR, exist_ok=True)

# Copy from each slug folder
for slug in SLUGS:
    meta_path = os.path.join(SRC_BASE, slug, "metadata.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    for m in meta:
        src_file = os.path.join(SRC_BASE, slug, m["filename"])
        ext = os.path.splitext(m["filename"])[1]
        dest_file = os.path.join(DEST_DIR, f"{slug}_{m['photo_id']}{ext}")
        shutil.copy2(src_file, dest_file)
    print(f"  {slug}: {len(meta)} files copied")

total = len(os.listdir(DEST_DIR))
print(f"\ntop5_imgs/ now has {total} files")
