"""
scrape_variant_counts.py
------------------------
Fetches the total number of photos (variants) on KYM for each meme in
variants_metadata.json, writing the result to variant_counts.json.

  { "woman-yelling-at-a-cat": 847, "distracted-boyfriend": 1203, ... }

The keys match the meme_name / folder values already used in the JS.

Usage:
  python scrape_variant_counts.py
"""

import sys
import re
import json
import time
import random
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, '.')
from memescrape import make_session, fetch_html

# ── Config ────────────────────────────────────────────────────────────────────
VARIANTS_META = Path('variants_metadata.json')
OUTPUT        = Path('variant_counts.json')
SLEEP_MIN     = 1.5
SLEEP_MAX     = 2.8
BASE_URL      = 'https://knowyourmeme.com'

# ── Load existing results (resume support) ────────────────────────────────────
if OUTPUT.exists():
    counts = json.loads(OUTPUT.read_text(encoding='utf-8'))
    print(f"Resuming — {len(counts)} memes already counted.")
else:
    counts = {}

# ── Get unique meme slugs from variants_metadata ──────────────────────────────
meta = json.loads(VARIANTS_META.read_text(encoding='utf-8'))
slugs = []
seen = set()
for entry in meta:
    slug = entry.get('meme_name') or entry.get('folder', '')
    if slug and slug not in seen:
        seen.add(slug)
        slugs.append(slug)

print(f"Found {len(slugs)} unique memes in variants_metadata.json")
todo = [s for s in slugs if s not in counts]
print(f"  {len(todo)} still need fetching\n")

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_photo_count(html):
    """Try several strategies to pull the total photo count from a KYM photos page."""
    soup = BeautifulSoup(html, 'html.parser')

    # Strategy 1: "1,234 Photos" heading / subheading text
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'span', 'div']):
        text = tag.get_text(separator=' ', strip=True)
        m = re.search(r'([\d,]+)\s+[Pp]hotos?', text)
        if m:
            return int(m.group(1).replace(',', ''))

    # Strategy 2: pagination — "Showing 1–20 of 847"
    for tag in soup.find_all(string=re.compile(r'Showing\s+\d')):
        m = re.search(r'of\s+([\d,]+)', str(tag))
        if m:
            return int(m.group(1).replace(',', ''))

    # Strategy 3: count the visible <a class="item"> gallery items on page 1
    # (fallback — only works when all images are listed, i.e. ≤ 1 page)
    items = soup.select('a.item')
    if items:
        return len(items)   # minimum bound for now

    return None


def save_counts():
    tmp = str(OUTPUT) + '.tmp'
    Path(tmp).write_text(json.dumps(counts, indent=2, ensure_ascii=False), encoding='utf-8')
    Path(tmp).replace(OUTPUT)


# ── Main loop ─────────────────────────────────────────────────────────────────
session = make_session()

for i, slug in enumerate(todo):
    url = f'{BASE_URL}/memes/{slug}/photos'
    print(f"[{i+1}/{len(todo)}] {slug}")
    print(f"        {url}")

    html = fetch_html(session, url)
    if html is None:
        print(f"        !! fetch failed — skipping")
        continue

    total = extract_photo_count(html)
    if total is None:
        print(f"        !! could not parse count — skipping")
        continue

    counts[slug] = total
    print(f"        → {total:,} photos")
    save_counts()

    if i < len(todo) - 1:
        sleep = random.uniform(SLEEP_MIN, SLEEP_MAX)
        time.sleep(sleep)

# ── Final save ────────────────────────────────────────────────────────────────
save_counts()
print(f"\nDone. variant_counts.json has {len(counts)} entries.")
