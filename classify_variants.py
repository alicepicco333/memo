"""
Run CLIP on top5_imgs/ to classify variantImageType for each variant,
then write the result back into transformation_annotations.json.
"""
import json, re, sys, os
from pathlib import Path

try:
    import clip
    import torch
    from PIL import Image
except ImportError:
    raise ImportError("pip install git+https://github.com/openai/CLIP.git Pillow torch")

IMAGE_TYPES = ["Photograph", "Drawing", "Illustration", "Cartoon", "Painting"]
PROMPTS     = [f"a {t.lower()}" for t in IMAGE_TYPES]

IMG_DIR = "top5_imgs"
TA_PATH = "transformation_annotations.json"

# ── Load CLIP ─────────────────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
model.eval()

with torch.no_grad():
    text_tokens = clip.tokenize(PROMPTS).to(device)
    text_feat   = model.encode_text(text_tokens)
    text_feat   = text_feat / text_feat.norm(dim=-1, keepdim=True)

# ── Build photo_id → filename map ────────────────────────────────────────────
pid_to_file = {}
for fname in os.listdir(IMG_DIR):
    m = re.search(r"_(\d+)\.", fname)
    if m:
        pid_to_file[m.group(1)] = os.path.join(IMG_DIR, fname)

# ── Load annotations ─────────────────────────────────────────────────────────
with open(TA_PATH, encoding="utf-8-sig") as f:
    records = json.load(f)

# ── Classify each image ───────────────────────────────────────────────────────
results = {}
for fname in sorted(os.listdir(IMG_DIR)):
    m = re.search(r"_(\d+)\.", fname)
    if not m:
        continue
    pid   = m.group(1)
    fpath = os.path.join(IMG_DIR, fname)

    try:
        img = Image.open(fpath).convert("RGB")
    except Exception:
        # GIF: take first frame
        try:
            from PIL import ImageSequence
            with Image.open(fpath) as im:
                img = next(ImageSequence.Iterator(im)).copy().convert("RGB")
        except Exception as e:
            print(f"  SKIP {fname}: {e}")
            continue

    with torch.no_grad():
        img_feat = model.encode_image(preprocess(img).unsqueeze(0).to(device))
        img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
        sims     = (img_feat @ text_feat.T).squeeze(0)
        probs    = sims.softmax(dim=0).cpu().tolist()

    best_idx  = probs.index(max(probs))
    best_type = IMAGE_TYPES[best_idx]
    score     = round(probs[best_idx], 4)
    results[pid] = best_type
    print(f"  {fname:60s} -> {best_type} ({score:.4f})")

# ── Patch transformation_annotations.json ────────────────────────────────────
matched = 0
for rec in records:
    pid = str(rec["photoId"])
    if pid in results:
        rec["variantImageType"] = results[pid]
        matched += 1

with open(TA_PATH, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"\nUpdated {matched}/{len(records)} records in {TA_PATH}")
