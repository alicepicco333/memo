"""Write memes_lite.json — a small index of the corpus for site-wide meme features
(random meme card, title banners) so pages don't need the 12 MB meme_data.json.

Usage: python build_memes_lite.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, 'meme_data.json'), encoding='utf-8'))

CDN = 'https://i.kym-cdn.com/'  # stripped to keep the file small; the site re-adds it
rows = []
for slug, m in data['memes'].items():
    img = m.get('imageURL')
    if not img:
        continue
    fmt = next((f for f in (m.get('hasFormat') or []) if f and f != 'Unknown'), None)
    year = m.get('year')
    rows.append({
        's': slug,
        'i': img[len(CDN):] if img.startswith(CDN) else img,
        'y': int(year) if str(year or '').isdigit() else None,
        'f': fmt,
        'v': m.get('popularityViews') or 0,
        't': m.get('hasImageType'),
        'a': m.get('hasAnimationStatus') == 'Animated',
    })

out = os.path.join(HERE, 'memes_lite.json')
json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'memes_lite.json: {len(rows)} memes, {os.path.getsize(out) / 1024:.0f} KB')
