"""
Generate static Manovich-style collage images for the meme ontology website.
Outputs:
  manovich_chrono.jpg   - chronological strip (B)
  manovich_powerlaw.jpg - power-law montage (C)
"""

import json, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT   = os.path.dirname(os.path.abspath(__file__))
DATA_F = os.path.join(ROOT, 'meme_data.json')
FLAT   = os.path.join(ROOT, 'images_flat')

# Target canvas size (fits in one browser screenful, leaving room for header)
W, H = 1760, 820
BG   = (10, 10, 10)

# ── helpers ──────────────────────────────────────────────────────────────────

def load_thumb(filename, size):
    path = os.path.join(FLAT, filename)
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert('RGB')
        img.thumbnail((size, size), Image.LANCZOS)
        # square-crop to exactly size×size
        w, h = img.size
        left = (w - size) // 2
        top  = (h - size) // 2
        img = img.crop((left, top, left + size, top + size))
        return img
    except Exception:
        return None

def tiny_font():
    try:
        return ImageFont.truetype("arial.ttf", 8)
    except Exception:
        return ImageFont.load_default()

# ── load data ────────────────────────────────────────────────────────────────

with open(DATA_F, encoding='utf-8') as f:
    DATA = json.load(f)['memes']

# ═══════════════════════════════════════════════════════════════════════════
# B — Chronological Strip
# ═══════════════════════════════════════════════════════════════════════════

def build_chrono():
    by_year = {}
    for slug, m in DATA.items():
        if not m or not m.get('imageFilename'):
            continue
        try:
            yr = int(m['year'])
        except (TypeError, ValueError):
            continue
        if yr < 1995 or yr > 2026:
            continue
        by_year.setdefault(yr, []).append(slug)

    years = sorted(by_year.keys())
    YEAR_GAP = 3

    # find largest THUMB that fits all years in W
    THUMB = 20
    for THUMB in range(20, 1, -1):
        CELL = THUMB + 1
        ROWS = max(1, (H - 20) // CELL)
        total_w = sum(
            (len(by_year[yr]) + ROWS - 1) // ROWS * CELL
            for yr in years
        )
        total_w += (len(years) - 1) * YEAR_GAP
        if total_w <= W:
            break
    THUMB = max(2, THUMB)

    GAP  = 1
    CELL = THUMB + GAP
    ROWS = max(1, (H - 20) // CELL)

    canvas = Image.new('RGB', (W, H), BG)
    draw   = ImageDraw.Draw(canvas)
    font   = tiny_font()

    x = 0
    placed = 0
    for yr in years:
        slugs = by_year[yr]
        cols  = (len(slugs) + ROWS - 1) // ROWS
        col_w = cols * CELL

        # year label at bottom
        if THUMB >= 6:
            draw.text((x + col_w // 2, H - 14), str(yr),
                      fill=(180, 180, 180), font=font, anchor='mm')

        for idx, slug in enumerate(slugs):
            col = idx // ROWS
            row = idx  % ROWS
            px  = x + col * CELL
            py  = row * CELL
            if px + THUMB > W:
                break
            m = DATA[slug]
            thumb = load_thumb(m['imageFilename'], THUMB)
            if thumb:
                canvas.paste(thumb, (px, py))
                placed += 1

        x += col_w + YEAR_GAP
        if x >= W:
            break

    print(f'Chrono: placed {placed} thumbnails  (thumb={THUMB}px, rows={ROWS})')
    out = os.path.join(ROOT, 'manovich_chrono.jpg')
    canvas.save(out, 'JPEG', quality=82, optimize=True)
    print(f'Saved  {out}')


# ═══════════════════════════════════════════════════════════════════════════
# C — Power-Law Montage
# ═══════════════════════════════════════════════════════════════════════════

def build_powerlaw():
    slugs = sorted(
        [s for s, m in DATA.items() if m and m.get('imageFilename')],
        key=lambda s: DATA[s].get('popularityViews') or -1,
        reverse=True,
    )

    TIERS = [
        {'label': 'TOP 200',  'count': 200,       'size': 56},
        {'label': 'NEXT 500', 'count': 500,       'size': 22},
        {'label': 'REST',     'count': 999_999,   'size': 9},
    ]

    canvas  = Image.new('RGB', (W, H), BG)
    draw    = ImageDraw.Draw(canvas)
    font    = tiny_font()
    y_off   = 0
    slug_i  = 0
    placed  = 0

    for tier in TIERS:
        if y_off + 16 >= H:
            break
        sz   = tier['size']
        GAP  = 1 if sz <= 18 else 2
        CELL = sz + GAP
        cols = max(1, W // CELL)

        rows_avail = max(1, (H - y_off - 16 - 14) // CELL)
        take = min(tier['count'], len(slugs) - slug_i, rows_avail * cols)
        if take <= 0:
            break

        # section label
        if sz >= 22:
            draw.text((8, y_off + 4), tier['label'],
                      fill=(100, 100, 100), font=font)
        y_off += 16

        for i in range(take):
            slug = slugs[slug_i + i]
            m    = DATA[slug]
            col  = i % cols
            row  = i // cols
            px   = col * CELL
            py   = y_off + row * CELL
            if py + sz > H:
                break
            thumb = load_thumb(m['imageFilename'], sz)
            if thumb:
                canvas.paste(thumb, (px, py))
                placed += 1

        rows_used = (take + cols - 1) // cols
        y_off += rows_used * CELL + 14
        slug_i += take

    print(f'Powerlaw: placed {placed} thumbnails')
    out = os.path.join(ROOT, 'manovich_powerlaw.jpg')
    canvas.save(out, 'JPEG', quality=82, optimize=True)
    print(f'Saved  {out}')


if __name__ == '__main__':
    print('Building chronological strip …')
    build_chrono()
    print()
    print('Building power-law montage …')
    build_powerlaw()
    print()
    print('Done.')
