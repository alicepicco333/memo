"""Write small WebP thumbnails for the meme wall on the home page (index.html) into img/wall/.

The wall draws its tiles from memes_lite.json (every meme) and variants_metadata.json (every
variant); Shuffle and Arrange can bring any of them onto the wall. Each image is downloaded once
from Know Your Meme, scaled to a 420 px long side and saved as WebP:

  img/wall/m-<slug>.webp       a meme
  img/wall/v-<photo_id>.webp   a variant

Characters outside a-z 0-9 _ - become _ (thumbName() in index.html uses the same rule).
Files that already exist are skipped, so a rerun only fetches what is new or failed.
Animated GIFs keep their first frame.

img/wall/missing.json lists the images that have no thumbnail:
  "gone"    Know Your Meme answers 404 or 410 (or 403 twice), or the file is not an image:
            the wall leaves them out
  "failed"  any other error: the wall loads them from Know Your Meme as before

Run it again after build_memes_lite.py or a change to variants_metadata.json.

Usage: python build_wall_thumbs.py
"""
import http.client
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageOps, UnidentifiedImageError

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'img', 'wall')
CDN = 'https://i.kym-cdn.com/'  # memes_lite.json stores paths without it
SIZE = 420                      # long side, px
QUALITY = 72
WORKERS = 4
TIMEOUT = 30                    # seconds per request
USER_AGENT = 'meme-ontology-thumbs/1.0'


class Gone(Exception):
    """The image is not there any more, or it is not an image."""


def thumb_name(prefix, key):
    return prefix + '-' + re.sub(r'[^a-z0-9_-]', '_', str(key).lower())


def wall_items():
    """(name, url) for every image the wall can show, in the order index.html builds them."""
    with open(os.path.join(HERE, 'memes_lite.json'), encoding='utf-8') as f:
        memes = json.load(f)
    with open(os.path.join(HERE, 'variants_metadata.json'), encoding='utf-8') as f:
        variants = json.load(f)
    items = []
    for m in memes:
        if m.get('i'):
            url = m['i'] if re.match(r'https?:', m['i']) else CDN + m['i']
            items.append((thumb_name('m', m['s']), url))
    for v in variants:
        if v.get('image_url') and v.get('photo_id'):
            items.append((thumb_name('v', v['photo_id']), v['image_url']))
    return items


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # the CDN's storage (S3) answers 403 Access Denied for a file that is not there
            if e.code in (404, 410) or (e.code == 403 and attempt == 2):
                raise Gone(f'HTTP {e.code}')
            if attempt == 2:
                raise
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == 2:
                raise
        time.sleep(3)


def make_thumb(data, path):
    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError:
        raise Gone(f'not an image ({data[:12]!r})')
    img.draft(None, (SIZE * 2, SIZE * 2))  # JPEG: decode at a smaller scale, still at least 2x
    img.load()                             # animated GIF: the first frame
    img = ImageOps.exif_transpose(img)
    alpha = img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info)
    img = img.convert('RGBA' if alpha else 'RGB')
    img.thumbnail((SIZE, SIZE), Image.LANCZOS)
    part = path + '.part'
    img.save(part, 'WEBP', quality=QUALITY, method=6)
    os.replace(part, path)  # never leave a half-written file that a rerun would skip


def build(name, url):
    path = os.path.join(OUT_DIR, name + '.webp')
    make_thumb(fetch(url), path)
    return os.path.getsize(path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    items = wall_items()
    names = [n for n, _ in items]
    if len(set(names)) != len(names):
        clash = sorted({n for n in names if names.count(n) > 1})
        raise SystemExit(f'Two images map to the same file name: {clash[:10]}')

    todo = [(n, u) for n, u in items if not os.path.exists(os.path.join(OUT_DIR, n + '.webp'))]
    print(f'{len(items)} wall images, {len(items) - len(todo)} thumbnails already there, {len(todo)} to make')

    gone, failed = {}, {}
    done = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(build, n, u): (n, u) for n, u in todo}
        for job in as_completed(jobs):
            name, url = jobs[job]
            done += 1
            try:
                job.result()
            except Gone as e:
                gone[name] = str(e)
                print(f'  GONE {name}  {url}  {e}')
            except Exception as e:
                failed[name] = f'{e.__class__.__name__}: {e}'
                print(f'  FAIL {name}  {url}  {failed[name]}')
            if done % 250 == 0:
                print(f'  {done}/{len(todo)}  {time.time() - started:.0f} s')

    with open(os.path.join(OUT_DIR, 'missing.json'), 'w', encoding='utf-8') as f:
        json.dump({'gone': sorted(gone), 'failed': sorted(failed)}, f, indent=1)
        f.write('\n')

    wanted = {n + '.webp' for n in names}
    files = [e for e in os.scandir(OUT_DIR) if e.name.endswith('.webp')]
    stale = [e.name for e in files if e.name not in wanted]
    total = sum(e.stat().st_size for e in files)
    print(f'Made {len(todo) - len(gone) - len(failed)}, gone {len(gone)}, failed {len(failed)}.')
    print(f'img/wall: {len(files)} thumbnails, {total / 1024 / 1024:.1f} MB'
          f' (average {total / max(len(files), 1) / 1024:.1f} KB)')
    if stale:
        print(f'{len(stale)} thumbnails are no longer on the wall (not deleted), e.g. {stale[:5]}')


if __name__ == '__main__':
    main()
