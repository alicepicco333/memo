"""Download 3 replacement Me Gusta variants from pages 2-5 of the gallery."""
import json, re, sys, time, os
sys.path.insert(0, ".")
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

USED_IDS = {"1941912","3055187","2634604","2093625","2093626","1358553","1484749","1945179","2076348"}
WANT_IDS  = {"844118", "663014", "483461"}   # Me Gustavo, SpongeBob Se Gusta, Me Gusta IRL

def ext_from_url(url, ct=""):
    path = url.split("?")[0]
    ext  = os.path.splitext(path)[1].lower()
    if ext in (".jpg",".jpeg",".png",".gif",".webp"): return ext
    if "gif" in ct: return ".gif"
    if "png" in ct: return ".png"
    return ".jpg"

session = make_session()
found = {}

for pg in range(1, 6):
    if len(found) == len(WANT_IDS):
        break
    url = "https://knowyourmeme.com/memes/me-gusta/photos" + (f"?page={pg}" if pg > 1 else "")
    html = fetch_html(session, url)
    if not html:
        continue
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a.item"):
        img = a.find("img")
        if not img:
            continue
        orig = img.get("data-image","") or ""
        if not orig:
            src = img.get("src","")
            if "photos/images" not in src:
                continue
            orig = src.replace("/masonry/","/original/")
        if not orig:
            continue
        href = a.get("href","")
        pid_m = re.search(r"/photos/(\d+)", href)
        pid   = pid_m.group(1) if pid_m else ""
        if pid not in WANT_IDS:
            continue
        found[pid] = {
            "photo_id": pid,
            "title":    a.get("data-title",""),
            "author":   a.get("data-author",""),
            "img_alt":  img.get("alt",""),
            "image_url": orig,
        }
        print(f"Found pid={pid} title={found[pid]['title']!r}")
    time.sleep(1.2)

if not found:
    print("Nothing found — exiting")
    sys.exit(1)

# Download
os.makedirs("top5_imgs", exist_ok=True)
records = []
for pid, item in found.items():
    url = item["image_url"]
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        ct  = resp.headers.get("Content-Type","")
        ext = ext_from_url(url, ct)
        fname = f"me-gusta_{pid}{ext}"
        dest  = os.path.join("top5_imgs", fname)
        with open(dest, "wb") as fh:
            fh.write(resp.content)
        print(f"Downloaded {fname}  ({len(resp.content)//1024}kB)")
        item["local"] = dest
    except Exception as e:
        print(f"FAIL {pid}: {e}")
    time.sleep(1.2)

with open("megusta_new3.json","w",encoding="utf-8") as f:
    json.dump(list(found.values()), f, indent=2)
print("\nSaved metadata to megusta_new3.json")
