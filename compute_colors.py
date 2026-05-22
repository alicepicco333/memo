"""Precompute average hue/saturation for each meme image -> color_data.json."""
import json, os, colorsys
from PIL import Image

IMAGES_DIR = 'images_flat'
MEME_DATA  = 'meme_data.json'
OUTPUT     = 'color_data.json'
SAMPLE     = 16  # resize to 16×16 before averaging

def avg_hsl(path):
    try:
        with Image.open(path) as img:
            img = img.convert('RGB').resize((SAMPLE, SAMPLE), Image.LANCZOS)
            px = list(img.getdata())
            n  = len(px)
            r  = sum(p[0] for p in px) / n / 255
            g  = sum(p[1] for p in px) / n / 255
            b  = sum(p[2] for p in px) / n / 255
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            return round(h * 360, 1), round(s * 100, 1), round(l * 100, 1)
    except Exception:
        return 0.0, 0.0, 0.0

def main():
    with open(MEME_DATA, encoding='utf-8') as f:
        memes = json.load(f)['memes']

    results, total = {}, len(memes)
    for i, (slug, m) in enumerate(memes.items()):
        if i % 200 == 0:
            print(f'  {i}/{total}', end='\r', flush=True)
        path = os.path.join(IMAGES_DIR, m.get('imageFilename', ''))
        if os.path.exists(path):
            h, s, l = avg_hsl(path)
            results[slug] = {'h': h, 's': s, 'l': l}
        else:
            results[slug] = {'h': 0, 's': 0, 'l': 0}

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, separators=(',', ':'))
    print(f'\nDone — {len(results)} entries written to {OUTPUT}')

if __name__ == '__main__':
    main()
