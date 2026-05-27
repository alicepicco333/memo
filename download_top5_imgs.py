"""Download variant images for big-chungus, me-gusta, stonks into top5_imgs/."""
import json, os, re, time, random
import sys
sys.path.insert(0, ".")
from memescrape import make_session

OUT_DIR = "top5_imgs"
SLUGS   = {"big-chungus", "me-gusta", "stonks"}

def ext_from_url(url, content_type=""):
    path = url.split("?")[0]
    ext  = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return ext
    if "gif" in content_type:
        return ".gif"
    if "png" in content_type:
        return ".png"
    return ".jpg"

def main():
    with open("top5_variants_raw.json", encoding="utf-8") as f:
        records = json.load(f)

    session = make_session()
    os.makedirs(OUT_DIR, exist_ok=True)

    todo = [r for r in records if r["memeSlug"] in SLUGS]
    print(f"Downloading {len(todo)} images...")

    for r in todo:
        slug = r["memeSlug"]
        pid  = r["photoId"]
        url  = r["imageURL"]

        try:
            resp = session.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            ct   = resp.headers.get("Content-Type", "")
            ext  = ext_from_url(url, ct)
            fname = f"{slug}_{pid}{ext}"
            dest  = os.path.join(OUT_DIR, fname)
            with open(dest, "wb") as fh:
                fh.write(resp.content)
            print(f"  OK  {fname}  ({len(resp.content)//1024}kB)")
        except Exception as e:
            print(f"  FAIL {slug}_{pid}: {e}")

        time.sleep(random.uniform(1.0, 1.8))

    print("Done.")

if __name__ == "__main__":
    main()
