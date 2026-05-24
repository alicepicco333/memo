import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import torch
from PIL import Image
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, Literal, URIRef, DCTERMS, BNode
from rdflib.collection import Collection

PROV   = Namespace("http://www.w3.org/ns/prov#")
SCHEMA = Namespace("http://schema.org/")
DC     = Namespace("http://purl.org/dc/elements/1.1/")
WD     = Namespace("http://www.wikidata.org/entity/")
WDT    = Namespace("http://www.wikidata.org/prop/direct/")

try:
    import clip
except ImportError:
    raise ImportError("pip install git+https://github.com/openai/CLIP.git")

try:
    import easyocr as _easyocr_mod
    _HAS_OCR = True
except ImportError:
    _easyocr_mod = None
    _HAS_OCR = False

_ocr_reader = None  # initialised once in main() after device is known


# ── CLIP prompt groups (each runs its own softmax) ────────────────────────────

PROMPTS_IMAGE_TYPE = [
    ("a photograph of a real scene or real person",          "Photograph"),
    ("a pencil or ink drawing or hand-drawn sketch",         "Drawing"),
    ("a detailed digital or print illustration",             "Illustration"),
    ("an animated cartoon, comic strip, or anime panel",     "Cartoon"),
    ("an oil, acrylic, or watercolor painting on canvas",    "Painting"),
]

PROMPTS_TEXT_PRESENCE = [
    ("an image with text written on it", "ContainsText"),
    ("an image without any text",        "NoText"),
]

PROMPTS_SUBJECT = [
    ("an image featuring a person or people, with or without text overlay",                          "PersonPresent"),
    ("an image featuring an animal, with or without text overlay",                                   "AnimalPresent"),
    ("a cartoon, drawing, or illustration featuring a fictional character or animated figure",        "CharacterPresent"),
    ("an image of objects or scenery only, no people, animals, or characters",                       "ObjectOnly"),
    ("a pure text screenshot or text-only post with no people, characters, or visual imagery at all","TextOnly"),
    ("an image with multiple distinct subjects such as people, animals, and objects together",        "MultipleSubjects"),
]

PROMPTS_PUBLIC_FIGURE = [
    ("a photo of a famous person or celebrity",   "PublicFigure"),
    ("a photo of an unknown or ordinary person",  "UnknownPerson"),
    ("an image with no person visible",           "NoPerson"),
]


# ── Metadata normalization maps ────────────────────────────────────────────────

PLATFORM_MAP = {
    "twitter": "TwitterX", "x (formerly twitter)": "TwitterX", "x": "TwitterX",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "reddit": "Reddit",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tumblr": "Tumblr",
    "4chan": "4chan",
    "ifunny": "iFunny",
    "twitch": "Twitch",
    "vine": "Vine",
    "imgur": "Imgur",
    "deviantart": "DeviantArt",
    "discord": "Discord",
    "snapchat": "Snapchat",
    "know your meme": "KnowYourMeme",
    "9gag": "9gag",
    "myspace": "MySpace",
    "ebaumsworld": "eBaumsWorld",
    "something awful": "SomethingAwful",
    "funnyjunk": "FunnyJunk",
}

FORMAT_MAP = {
    "image macro": "ImageMacro", "image macros": "ImageMacro",
    "exploitable": "Exploitable",
    "catchphrase": "Catchphrase",
    "viral video": "ViralVideo",
    "reaction": "Reaction",
    "pop culture reference": "PopCultureReference",
    "character": "Character",
    "parody": "Parody",
    "participatory media": "ParticipatoryMedia",
    "slang": "Slang",
    "song": "Song",
    "photoshop": "Photoshop",
    "snowclone": "Snowclone",
    "copypasta": "Copypasta",
    "remix": "Remix",
    "fan art": "FanArt",
    "viral debate": "ViralDebate",
    "cliché": "Cliche", "cliche": "Cliche",
    "animal": "Animal",
    "sound effect": "SoundEffect",
    "social game": "SocialGame",
    "lip dub": "LipDub",
    "conspiracy theory": "ConspiracyTheory",
    "fan labor": "FanLabor",
    "hoax": "Hoax",
    "dance": "Dance",
    "emoticon": "Emoticon",
    "ai-generated": "AiGenerated", "ai generated": "AiGenerated",
    "hashtag": "Hashtag",
    "visual effect": "VisualEffect",
    "advertisement": "Advertisement",
    "axiom": "Axiom",
    "creepypasta": "Creepypasta",
    "shock media": "ShockMedia",
    "optical illusion": "OpticalIllusion",
}

REGION_MAP = {
    # United States variants / typos
    "united states": "UnitedStates", "usa": "UnitedStates", "us": "UnitedStates",
    "united satates": "UnitedStates", "unitedstates": "UnitedStates",
    # United Kingdom variants
    "united kingdom": "UnitedKingdom", "uk": "UnitedKingdom", "england": "UnitedKingdom",
    "great britain": "UnitedKingdom", "britain": "UnitedKingdom",
    # Worldwide / broad regions
    "worldwide": "Worldwide", "international": "Worldwide", "global": "Worldwide",
    "latin america": "Worldwide", "north america": "Worldwide", "europe": "Worldwide",
    "middle east": "Worldwide",
    # Countries
    "japan": "Japan",
    "china": "China", "prc": "China",
    "brazil": "Brazil",
    "india": "India",
    "france": "France",
    "canada": "Canada",
    "australia": "Australia",
    "germany": "Germany",
    "south korea": "SouthKorea", "korea": "SouthKorea",
    "russia": "Russia",
    "spain": "Spain",
    "italy": "Italy",
    "mexico": "Mexico",
    "netherlands": "Netherlands",
    "sweden": "Sweden",
    "finland": "Finland",
    "poland": "Poland",
    "philippines": "Philippines",
    "indonesia": "Indonesia",
    "thailand": "Thailand",
    "turkey": "Turkey", "türkiye": "Turkey",
    "argentina": "Argentina",
    "israel": "Israel",
    "singapore": "Singapore",
    "ireland": "Ireland",
    "ukraine": "Ukraine",
    "romania": "Romania",
    "serbia": "Serbia",
    "belgium": "Belgium",
    "switzerland": "Switzerland",
    "vietnam": "Vietnam",
    "czech republic": "CzechRepublic", "czechia": "CzechRepublic",
    "chile": "Chile",
    "colombia": "Colombia",
    "pakistan": "Pakistan",
    # Additional countries present in KYM data
    "ghana": "Ghana",
    "uganda": "Uganda",
    "nigeria": "Nigeria",
    "ecuador": "Ecuador",
    "el salvador": "El Salvador",
    "guatelama": "Guatemala", "guatemala": "Guatemala",   # typo + canonical
    "mali": "Mali",
    "palestine": "Palestine",
    "vatican": "Vatican", "vatican city": "Vatican City",
    "babylon": "Babylon",
    "arabic": "Arabic",
    "little italy": "Little Italy",
    "": "Unknown",
}

FILE_FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG",
    ".png": "PNG",
    ".gif": "GIF",
    ".webp": "WebP",
    ".bmp": "BMP",
}


# ── Normalization functions ────────────────────────────────────────────────────

def normalize_format(types_list):
    out = []
    for t in (types_list or []):
        key = t.strip().lower()
        out.append(FORMAT_MAP.get(key, t.strip()))
    return out or ["Unknown"]


def normalize_origin(raw):
    """Return (hasOriginPlatform, hasOriginWork).
    Known platforms → hasOriginPlatform. Everything else → hasOriginWork.

    Source of the value: the 'origin' metadata field scraped from Know Your Meme.
    KYM allows free text here — it can be a platform, a TV show, a person's name,
    a 4chan board, a movie, etc.  Platform names are resolved here; everything
    else is categorised further by categorize_origin_work().
    """
    if not raw or not raw.strip():
        return "Unknown", None
    key = raw.strip().lower()
    if key in PLATFORM_MAP:
        return PLATFORM_MAP[key], None
    for k, v in PLATFORM_MAP.items():
        if k in key:
            return v, None
    return None, raw.strip()


# ── OriginWork sub-category classification ────────────────────────────────────
# KYM often appends a parenthetical type annotation to the origin field, e.g.
# "The Simpsons (Television Series)" or "Shrek (Film)".  The rules below match
# those annotations (and a few non-annotated patterns) to route each value into
# the most specific OWL property instead of the generic hasOriginWork.

_BOARD_RE    = re.compile(r"^/[\w\-]+/$")   # /b/  /pol/  /v/  etc.
# Each rule maps keyword hints to a schema.org type URIRef.
# Matched individuals are linked via prov:wasDerivedFrom and typed as schema:X.
_ORIGIN_RULES = [
    (SCHEMA.TVSeries,    [
        "television series", "tv series", "tv show", "animated series",
        "web series", "anime series", "cartoon series", "sitcom",
        "miniseries", "webseries",
    ]),
    (SCHEMA.Movie,       [
        "(film)", "(movie)", "animated film", "documentary",
        "short film", "motion picture", "(animated movie)",
    ]),
    (SCHEMA.VideoGame,   [
        "video game", "(game)", "arcade game", "mobile game",
        "online game", "flash game",
    ]),
    (SCHEMA.ComicSeries, [
        "comic strip", "comic book", "webcomic", "(manga)",
        "graphic novel", "newspaper comic",
    ]),
    (SCHEMA.MusicAlbum,  [
        "(song)", "music video", "(album)", "(rap song)", "(single)", "(track)",
    ]),
    (SCHEMA.Book,        [
        "(novel)", "(book)", "(short story)", "(children's book)",
    ]),
]


def categorize_origin_work(raw):
    """Return a schema.org type URIRef for a free-text origin-work string, or None.

    None means no specific schema type was identified; caller types the individual
    as OriginWork only.  Imageboards (/b/, /pol/ …) also return None.
    prov:wasAttributedTo (person attribution) is assigned manually in Protégé.
    """
    if not raw or not raw.strip():
        return None
    stripped = raw.strip()
    lower    = stripped.lower()
    if _BOARD_RE.match(stripped):
        return None  # imageboard — no schema.org type; stays as OriginWork
    for schema_type, kws in _ORIGIN_RULES:
        if any(kw in lower for kw in kws):
            return schema_type
    return None


def normalize_region(raw):
    if not raw or not raw.strip():
        return "Unknown"
    return REGION_MAP.get(raw.strip().lower(), raw.strip())


def normalize_time_period(year_raw):
    try:
        y = int(str(year_raw).strip())
        if y < 2010:
            label = "Pre2010"
        elif y <= 2015:
            label = "Period2010to2015"
        elif y <= 2020:
            label = "Period2016to2020"
        else:
            label = "Period2021toPresent"
        return y, label
    except (ValueError, TypeError):
        return None, "Unknown"


def _original_ext(image_url):
    """Extract the original file extension from the image URL, not the local filename
    (which may have been converted to .jpg by the scraper)."""
    try:
        path = urlparse(image_url).path
        return Path(path).suffix.lower()
    except Exception:
        return ""


def normalize_file_format(image_url):
    return FILE_FORMAT_MAP.get(_original_ext(image_url), "Unknown")


def normalize_animation(image_url):
    return "Animated" if _original_ext(image_url) == ".gif" else "Static"


# ── Image classification ───────────────────────────────────────────────────────

def _softmax_group(img_feat, model, device, labeled_prompts):
    """Run one independent softmax over a prompt group given pre-encoded image features."""
    prompts = [p for p, _ in labeled_prompts]
    labels  = [l for _, l in labeled_prompts]
    with torch.no_grad():
        txt_feat = model.encode_text(clip.tokenize(prompts).to(device))
        txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)
        logits = 100.0 * img_feat @ txt_feat.t()
        probs  = logits.softmax(dim=-1).cpu().numpy()[0]
    return {labels[i]: float(probs[i]) for i in range(len(labels))}


def classify_image(model, preprocess, device, image_path, text_threshold, subj_threshold=0.40, textonly_threshold=0.65):
    img = Image.open(image_path).convert("RGB")

    with torch.no_grad():
        img_feat = model.encode_image(preprocess(img).unsqueeze(0).to(device))
        img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)

    # ImageType
    type_scores = _softmax_group(img_feat, model, device, PROMPTS_IMAGE_TYPE)
    best_type   = max(type_scores, key=type_scores.get)

    # TextPresence — CLIP first; EasyOCR fallback for uncertain cases
    text_scores     = _softmax_group(img_feat, model, device, PROMPTS_TEXT_PRESENCE)
    clip_text_score = text_scores.get("ContainsText", 0.0)
    ocr_snippet     = None
    if clip_text_score >= text_threshold:
        text_presence = "ContainsText"
    elif _HAS_OCR and _ocr_reader is not None:
        try:
            # Upscale small images so OCR has enough resolution
            ocr_img = img
            if max(img.size) < 512:
                scale = 512 / max(img.size)
                ocr_img = img.resize(
                    (int(img.width * scale), int(img.height * scale)),
                    Image.LANCZOS,
                )
            ocr_results = _ocr_reader.readtext(np.array(ocr_img))
            confident = [r[1] for r in ocr_results if r[2] > 0.5]
            ocr_text  = " ".join(confident).strip()
            if ocr_text:
                text_presence = "ContainsText"
                ocr_snippet   = ocr_text[:200]
            else:
                text_presence = "NoText"
        except Exception:
            text_presence = "NoText"
    else:
        text_presence = "NoText"

    # Public figure score — computed first so it can inform subject assignment
    pubfig_scores = _softmax_group(img_feat, model, device, PROMPTS_PUBLIC_FIGURE)
    pubfig_score  = pubfig_scores.get("PublicFigure", 0.0)

    # SubjectMatter
    subj_scores = _softmax_group(img_feat, model, device, PROMPTS_SUBJECT)
    best_subj   = max(subj_scores, key=subj_scores.get)
    if subj_scores[best_subj] < subj_threshold:
        best_subj = "Unknown"
    elif best_subj == "TextOnly" and subj_scores[best_subj] < textonly_threshold:
        # TextOnly needs stronger evidence; fall back to next-best non-TextOnly label.
        alt = max((l for l in subj_scores if l != "TextOnly"), key=subj_scores.get)
        best_subj = alt if subj_scores[alt] >= subj_threshold else "Unknown"
    # A high public figure score means there is a recognisable face/character — TextOnly
    # is a direct contradiction and must be overridden.
    if best_subj == "TextOnly" and pubfig_score > 0.5:
        alt = max((l for l in subj_scores if l != "TextOnly"), key=subj_scores.get)
        best_subj = alt if subj_scores[alt] >= subj_threshold else "Unknown"

    # Any above-chance signal for a living subject also vetoes TextOnly — covers image
    # macros where text overlay causes TextOnly to win over the actual visual subject.
    if best_subj == "TextOnly":
        living_signal = max(
            subj_scores.get("PersonPresent",    0.0),
            subj_scores.get("AnimalPresent",    0.0),
            subj_scores.get("CharacterPresent", 0.0),
        )
        if living_signal > 0.22:  # meaningfully above random chance (1/6 ≈ 0.167)
            alt = max((l for l in subj_scores if l != "TextOnly"), key=subj_scores.get)
            best_subj = alt if subj_scores[alt] >= subj_threshold else "Unknown"

    # ColorMode — per-pixel range (max-min across R,G,B channels).
    # Channel std dev comparison fails on cartoons/drawings: heavy black outlines and
    # white backgrounds make all three std devs equal even when color fills are present.
    # Per-pixel range is 0 for achromatic pixels (black, white, grey) and >0 only for
    # pixels that actually carry color, so it is not distorted by B&W dominance.
    arr = np.array(img, dtype=np.uint8)
    per_pixel_range = arr.max(axis=2).astype(np.float32) - arr.min(axis=2).astype(np.float32)
    mean_color_range = per_pixel_range.mean()
    color_mode = "Color" if mean_color_range > 10.0 else "Monochrome"

    # ── Consistency rules ─────────────────────────────────────────────────────
    # TextOnly subject always implies text is present, regardless of CLIP/OCR score.
    if best_subj == "TextOnly":
        text_presence = "ContainsText"

    return {
        "hasImageType":          best_type,
        "clipImageTypeScore":    round(type_scores[best_type], 4),
        "hasTextPresence":       text_presence,
        "clipTextScore":         round(clip_text_score, 4),
        "ocrSnippet":            ocr_snippet,
        "hasColorMode":          color_mode,
        "hasSubjectMatter":      best_subj,
        "clipPublicFigureScore": round(pubfig_score, 4),
    }


# ── OWL output ────────────────────────────────────────────────────────────────

ONTO_BASE = "https://purl.org/memo#"
ONTO_URI  = URIRef("https://purl.org/memo")

# P2 — Wikidata Q-item classes that replace memo: class declarations
WD_CLASS_MAP = {
    "GeographicRegion": WD.Q82794,
    "TimePeriod":       WD.Q11471,
    "OriginPlatform":   WD.Q3220391,
    "OriginWork":       WD.Q386724,
    "FileFormat":       WD.Q235557,
    "CulturalReference":WD.Q96622155,
    "MemeIdea":         WD.Q3249551,
    "SubjectMatter":    WD.Q16334295,
}

# P3 — Wikidata P-item properties that replace memo: object property declarations
WD_PROP_MAP = {
    "hasRegion":         WDT.P495,
    "hasTimePeriod":     WDT.P2408,
    "hasReference":      WDT.P8371,
    "hasVariant":        WDT.P527,
    "isVariantOf":       WDT.P361,
    "hasFormat":         WDT.P2283,
    "hasOriginPlatform": WDT.P123,
}

# All pre-declared named individuals per class
VOCAB = {
    "ImageType":       ["Photograph", "Drawing", "Illustration", "Cartoon", "Painting"],
    "TextPresence":    ["ContainsText", "NoText"],
    "ColorMode":       ["Color", "Monochrome"],
    "SubjectMatter":   ["PersonPresent", "AnimalPresent", "CharacterPresent", "ObjectOnly", "TextOnly", "MultipleSubjects", "Unknown"],
    "TimePeriod":      ["Pre2010", "Period2010to2015", "Period2016to2020", "Period2021toPresent", "Unknown"],
    "FileFormat":      ["JPEG", "PNG", "GIF", "WebP", "BMP"],
    "AnimationStatus": ["Static", "Animated"],
    "OriginPlatform":   ["Unknown"],           # WD-mapped platforms declared via WD_PLATFORM_INDIVIDUALS
    "GeographicRegion": ["Unknown", "Worldwide"],  # WD-mapped regions declared via WD_REGION_INDIVIDUALS
}

# Wikidata QIDs for GeographicRegion individuals.
# Keys are the strings that appear as `_norm` after the REGION_MAP lookup at OWL-build time,
# which is the same as the value stored in classifications.json (normalize_region output).
REGION_QID_MAP = {
    # CamelCase — produced by normalize_region (stored in classifications.json)
    "UnitedStates":  "Q30",
    "UnitedKingdom": "Q145",
    "SouthKorea":    "Q884",
    "CzechRepublic": "Q213",
    # Natural / single-word names that fall through REGION_MAP unchanged
    "Japan":         "Q17",
    "China":         "Q148",
    "Brazil":        "Q155",
    "India":         "Q668",
    "France":        "Q142",
    "Russia":        "Q159",
    "Mexico":        "Q96",
    "Germany":       "Q183",
    "Australia":     "Q408",
    "Canada":        "Q16",
    "Italy":         "Q38",
    "Spain":         "Q29",
    "Indonesia":     "Q252",
    "Philippines":   "Q928",
    "Poland":        "Q36",
    "Netherlands":   "Q55",
    "Ukraine":       "Q212",
    "Turkey":        "Q43",
    "Sweden":        "Q34",
    "Switzerland":   "Q39",
    "Belgium":       "Q31",
    "Argentina":     "Q414",
    "Colombia":      "Q739",
    "Chile":         "Q298",
    "Finland":       "Q33",
    "Romania":       "Q218",
    "Pakistan":      "Q843",
    "Israel":        "Q801",
    "Singapore":     "Q334",
    "Vietnam":       "Q881",
    "Thailand":      "Q869",
    "Ireland":       "Q27",
    "Serbia":        "Q403",
    "Ghana":         "Q117",
    "Uganda":        "Q1036",
    "Nigeria":       "Q1033",
    "Ecuador":       "Q736",
    "El Salvador":   "Q792",
    "Guatemala":     "Q774",
    "Guatelama":     "Q774",   # typo variant possibly stored in classifications.json
    "Mali":          "Q912",
    "Palestine":     "Q219060",
    "Vatican":       "Q237",
    "Vatican City":  "Q237",
    "Babylon":       "Q5684",
    # Worldwide / Unknown / linguistic labels have no QID — keep as memo: (None means skip)
}

# Wikidata QIDs for OriginPlatform individuals, keyed by PLATFORM_MAP output.
PLATFORM_QID_MAP = {
    "TwitterX":       "Q918",
    "TikTok":         "Q50003786",
    "YouTube":        "Q866",
    "Reddit":         "Q28811",
    "Instagram":      "Q209330",
    "Facebook":       "Q355",
    "Tumblr":         "Q212971",
    "4chan":          "Q674637",
    "Vine":           "Q5754076",
    "Imgur":          "Q898279",
    "DeviantArt":     "Q545858",
    "Discord":        "Q56028744",
    "Snapchat":       "Q18373543",
    "Twitch":         "Q10288502",
    "MySpace":        "Q38022",
    "SomethingAwful": "Q3489062",
    "9gag":           "Q2737200",
    "iFunny":         "Q4319804",
    "eBaumsWorld":    "Q3724165",
    "FunnyJunk":      "Q5509787",
    "KnowYourMeme":   "Q928047",
}

# Schema-level declarations: Wikidata individuals for GeographicRegion (wd:Q82794).
# QID → display label (used as rdfs:label on the wd: individual).
WD_REGION_INDIVIDUALS = {
    "Q30":      "United States",
    "Q145":     "United Kingdom",
    "Q884":     "South Korea",
    "Q213":     "Czech Republic",
    "Q17":      "Japan",
    "Q148":     "China",
    "Q155":     "Brazil",
    "Q668":     "India",
    "Q142":     "France",
    "Q159":     "Russia",
    "Q96":      "Mexico",
    "Q183":     "Germany",
    "Q408":     "Australia",
    "Q16":      "Canada",
    "Q38":      "Italy",
    "Q29":      "Spain",
    "Q252":     "Indonesia",
    "Q928":     "Philippines",
    "Q36":      "Poland",
    "Q55":      "Netherlands",
    "Q212":     "Ukraine",
    "Q43":      "Turkey",
    "Q34":      "Sweden",
    "Q39":      "Switzerland",
    "Q31":      "Belgium",
    "Q414":     "Argentina",
    "Q739":     "Colombia",
    "Q298":     "Chile",
    "Q33":      "Finland",
    "Q218":     "Romania",
    "Q843":     "Pakistan",
    "Q801":     "Israel",
    "Q334":     "Singapore",
    "Q881":     "Vietnam",
    "Q869":     "Thailand",
    "Q27":      "Ireland",
    "Q403":     "Serbia",
    "Q117":     "Ghana",
    "Q1036":    "Uganda",
    "Q1033":    "Nigeria",
    "Q736":     "Ecuador",
    "Q792":     "El Salvador",
    "Q774":     "Guatemala",
    "Q912":     "Mali",
    "Q219060":  "Palestine",
    "Q237":     "Vatican City",
    "Q5684":    "Babylon",
}

# Schema-level declarations: Wikidata individuals for OriginPlatform (wd:Q3220391).
WD_PLATFORM_INDIVIDUALS = {
    "Q918":      "Twitter/X",
    "Q50003786": "TikTok",
    "Q866":      "YouTube",
    "Q28811":    "Reddit",
    "Q209330":   "Instagram",
    "Q355":      "Facebook",
    "Q212971":   "Tumblr",
    "Q674637":   "4chan",
    "Q5754076":  "Vine",
    "Q898279":   "Imgur",
    "Q545858":   "DeviantArt",
    "Q56028744": "Discord",
    "Q18373543": "Snapchat",
    "Q10288502": "Twitch",
    "Q38022":    "MySpace",
    "Q3489062":  "Something Awful",
    "Q2737200":  "9GAG",
    "Q4319804":  "iFunny",
    "Q3724165":  "eBaum's World",
    "Q5509787":  "FunnyJunk",
    "Q928047":   "Know Your Meme",
}

OBJ_PROPS = [
    # P4 — consolidated visual props: union domain MemeConcept ∪ VariantInstance
    ("hasImageType",      ("MemeConcept", "VariantInstance"), "ImageType"),
    ("isImageTypeOf",     "ImageType",    ("MemeConcept", "VariantInstance")),
    ("hasTextPresence",   ("MemeConcept", "VariantInstance"), "TextPresence"),
    ("isTextPresenceOf",  "TextPresence", ("MemeConcept", "VariantInstance")),
    ("hasColorMode",      ("MemeConcept", "VariantInstance"), "ColorMode"),
    ("isColorModeOf",     "ColorMode",    ("MemeConcept", "VariantInstance")),
    ("hasSubjectMatter",  ("MemeConcept", "VariantInstance"), "SubjectMatter"),
    ("isSubjectMatterOf", "SubjectMatter",("MemeConcept", "VariantInstance")),
    # MemeConcept — format & distribution (P3: several use Wikidata URIs)
    ("hasFormat",          "MemeConcept",     "MemeFormat"),        # → WDT.P2283
    ("isFormatOf",         "MemeFormat",      "MemeConcept"),
    ("hasOriginPlatform",  "MemeConcept",     "OriginPlatform"),    # → WDT.P123
    ("isOriginPlatformOf", "OriginPlatform",  "MemeConcept"),
    ("hasOriginWork",      "MemeConcept",     "OriginWork"),
    ("isOriginWorkOf",     "OriginWork",      "MemeConcept"),
    ("hasRegion",          "MemeConcept",     "GeographicRegion"),  # → WDT.P495
    ("isRegionOf",         "GeographicRegion","MemeConcept"),
    ("hasTimePeriod",      "MemeConcept",     "TimePeriod"),        # → WDT.P2408
    ("isTimePeriodOf",     "TimePeriod",      "MemeConcept"),
    ("hasAnimationStatus", "MemeConcept",     "AnimationStatus"),
    ("isAnimationStatusOf","AnimationStatus", "MemeConcept"),
    ("hasReference",       "MemeConcept",     "CulturalReference"), # → WDT.P8371
    ("isReferencedIn",     "CulturalReference","MemeConcept"),
    # FRBR relations (P3: hasVariant/isVariantOf use Wikidata)
    ("hasVariant",         "MemeConcept",     "VariantInstance"),   # → WDT.P527
    ("isVariantOf",        "VariantInstance", "MemeConcept"),       # → WDT.P361
    ("conceptualizes",     "MemeConcept",     "MemeIdea"),
    ("isConceptualizedAs", "MemeIdea",        "MemeConcept"),
    # VariantInstance
    ("hasTransformationDimension", "VariantInstance",        "TransformationDimension"),
    ("isTransformationDimensionOf","TransformationDimension","VariantInstance"),
    ("hasTransformationExtent",    "VariantInstance",        "TransformationExtent"),
    ("isTransformationExtentOf",   "TransformationExtent",   "VariantInstance"),
]

# (name, domain_class, xsd_range)
DATA_PROPS = [
    # MemeConcept level
    ("hasId",                 "MemeConcept",    XSD.integer),
    ("imageFilename",         "MemeConcept",    XSD.string),
    ("imageFilePath",         "MemeConcept",    XSD.string),
    ("views",                 "MemeConcept",    XSD.integer),
    ("clipImageTypeScore",    "MemeConcept",    XSD.float),
    ("clipTextScore",         "MemeConcept",    XSD.float),
    ("clipPublicFigureScore", "MemeConcept",    XSD.float),
    # MemeIdea level
    ("conceptDescription",    "MemeIdea",       XSD.string),
    # VariantInstance level
    ("captionText",           "VariantInstance", XSD.string),
    ("variantFilename",       "VariantInstance", XSD.string),
    ("variantImageURL",       "VariantInstance", XSD.string),
    ("variantIndex",          "VariantInstance", XSD.integer),
    ("variantTitle",          "VariantInstance", XSD.string),
    ("variantUploader",       "VariantInstance", XSD.string),
    ("photoURL",              "VariantInstance", XSD.string),
]

# Fix 1 — owl:inverseOf for all 15 inverse pairs
INVERSE_PAIRS = [
    ("hasImageType",               "isImageTypeOf"),
    ("hasTextPresence",            "isTextPresenceOf"),
    ("hasColorMode",               "isColorModeOf"),
    ("hasSubjectMatter",           "isSubjectMatterOf"),
    ("hasFormat",                  "isFormatOf"),
    ("hasOriginPlatform",          "isOriginPlatformOf"),
    ("hasOriginWork",              "isOriginWorkOf"),
    ("hasRegion",                  "isRegionOf"),
    ("hasTimePeriod",              "isTimePeriodOf"),
    ("hasAnimationStatus",         "isAnimationStatusOf"),
    ("hasReference",               "isReferencedIn"),
    ("hasVariant",                 "isVariantOf"),
    ("conceptualizes",             "isConceptualizedAs"),
    ("hasTransformationDimension", "isTransformationDimensionOf"),
    ("hasTransformationExtent",    "isTransformationExtentOf"),
]

# Reverse lookup for asserting explicit inverses in the populated file
INVERSE_LOOKUP = {fwd: inv for fwd, inv in INVERSE_PAIRS}
INVERSE_LOOKUP.update({inv: fwd for fwd, inv in INVERSE_PAIRS})

# Fix: rdfs:comment for all memo: classes (external classes get theirs via WD_CLASS_META)
MEMO_CLASS_COMMENTS = {
    "MemeConcept":             "A meme template or canonical format; the Expression level of the FRBR hierarchy. Represents the stable, recognisable form of a meme as documented on Know Your Meme.",
    "VariantInstance":         "A specific image derived from a meme template; the Manifestation level of the FRBR hierarchy. Represents a single scraped or documented instantiation of a MemeConcept.",
    "ImageType":               "The visual medium or rendering technique of a meme image (e.g. Photograph, Drawing, Cartoon). Corresponds to Panofsky's pre-iconographic description.",
    "TextPresence":            "Whether visible text is present in a meme image (ContainsText or NoText). Detected automatically via CLIP and EasyOCR.",
    "ColorMode":               "Whether a meme image uses colour or is monochromatic (Color or Monochrome). Determined by per-pixel colour range analysis.",
    "MemeFormat":              "The genre or structural format of a meme (e.g. ImageMacro, Copypasta, ViralVideo). Drawn from Know Your Meme's type taxonomy.",
    "AnimationStatus":         "Whether a meme image is animated (Animated, i.e. a GIF) or static (Static). Derived from file extension.",
    "TransformationDimension": "The primary dimension along which a VariantInstance transforms the source template (e.g. textual, visual, contextual). Enables typological analysis of meme variation.",
    "TransformationExtent":    "The degree to which a VariantInstance diverges from its source template (e.g. Minimal, Moderate, Major). Enables quantitative analysis of meme mutation.",
    "PoliticalEvent":          "A political event, controversy, or campaign that a meme iconologically references.",
    "MediaProperty":           "A media franchise, film, TV series, game, or other creative property referenced by a meme.",
    "WebCulture":              "A web-native cultural phenomenon, community, or trend referenced by a meme.",
    "PublicFigure":            "A public figure, celebrity, politician, or historical person referenced by a meme.",
    "HistoricalEvent":         "A historical event, period, or crisis referenced by a meme.",
    "SocialPhenomenon":        "A social movement, behavioural trend, or cultural practice referenced by a meme.",
}

# Fix: rdfs:comment + rdfs:seeAlso for each Wikidata class
WD_CLASS_META = {
    "GeographicRegion":  (
        "Geographic region or country of meme origin, as defined by Wikidata Q82794.",
        "Q82794",
    ),
    "TimePeriod":        (
        "Chronological period in which the meme originated or peaked, aligned with Wikidata Q11471.",
        "Q11471",
    ),
    "OriginPlatform":    (
        "Online platform or service where the meme was first published, aligned with Wikidata Q3220391.",
        "Q3220391",
    ),
    "OriginWork":        (
        "Creative work (film, TV series, game, etc.) from which the meme derives, aligned with Wikidata Q386724.",
        "Q386724",
    ),
    "FileFormat":        (
        "Digital file format of the meme image resource, as defined by Wikidata Q235557.",
        "Q235557",
    ),
    "CulturalReference": (
        "Cultural artefact, event, or phenomenon that a meme iconologically references, aligned with Wikidata Q96622155.",
        "Q96622155",
    ),
    "MemeIdea":          (
        "Abstract creative idea underlying a meme template; corresponds to the FRBR Work level, aligned with Wikidata Q3249551.",
        "Q3249551",
    ),
    "SubjectMatter":     (
        "Primary visual subject depicted in a meme image; corresponds to Panofsky's pre-iconographic level, aligned with Wikidata Q16334295.",
        "Q16334295",
    ),
}

# Fix 10 — CulturalReference subtypes as owl:Class subclasses of wd:Q96622155
CULTURAL_REF_SUBTYPES = [
    "PoliticalEvent", "MediaProperty", "WebCulture",
    "PublicFigure", "HistoricalEvent", "SocialPhenomenon",
]


def _iri_local(s):
    """Sanitize a string for use as an IRI local name (valid in RDF/XML)."""
    s = re.sub(r"[^\w\-]", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if s and s[0].isdigit():
        s = "_" + s
    return s or "Unknown"


def _iri_local_norm(s):
    """Like _iri_local but lowercases first — used for free-text fields so
    'VK' and 'vk' collapse to the same IRI."""
    return _iri_local(s.lower())


def build_ontology(results, owl_path, meta_lookup=None, variants_path=None):
    """Build OWL ontology from classification results.
    meta_lookup:   optional dict {zero-padded-id -> metadata entry} for imageFilename lookup.
    variants_path: optional path to variants_metadata.json; generates MemeIdea + VariantInstance individuals."""
    MEME = Namespace(ONTO_BASE)
    g = Graph()
    g.bind("memo",    MEME)
    g.bind("owl",     OWL)
    g.bind("rdfs",    RDFS)
    g.bind("xsd",     XSD)
    g.bind("prov",    PROV)
    g.bind("schema",  SCHEMA, override=True, replace=True)
    g.bind("dcterms", DCTERMS)
    g.bind("wd",      WD)
    g.bind("wdt",     WDT)
    g.bind("dc",      DC)

    g.add((ONTO_URI, RDF.type,        OWL.Ontology))
    g.add((ONTO_URI, OWL.versionInfo, Literal("1.0")))
    g.add((ONTO_URI, DCTERMS.title,   Literal("The Meme Ontology (MEMO)", lang="en")))
    g.add((ONTO_URI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    g.add((ONTO_URI, DC.creator,      Literal("Alice Picco")))

    def class_uri(name):
        return WD_CLASS_MAP.get(name, MEME[name])

    def prop_uri(name):
        return WD_PROP_MAP.get(name, MEME[name])

    def _union_node(class_names):
        bn = BNode()
        g.add((bn, RDF.type, OWL.Class))
        lst = BNode()
        Collection(g, lst, [class_uri(c) for c in class_names])
        g.add((bn, OWL.unionOf, lst))
        return bn

    # Classes — memo: classes (P2 Wikidata classes declared separately below)
    memo_only_classes = [
        "MemeConcept", "ImageType", "TextPresence", "ColorMode",
        "MemeFormat", "AnimationStatus",
        "VariantInstance", "TransformationDimension", "TransformationExtent",
    ]
    for c in memo_only_classes:
        g.add((MEME[c], RDF.type,  OWL.Class))
        g.add((MEME[c], RDFS.label, Literal(c)))
        if c in MEMO_CLASS_COMMENTS:
            g.add((MEME[c], RDFS.comment, Literal(MEMO_CLASS_COMMENTS[c], lang="en")))

    # P2 — Wikidata Q-item classes declared as OWL classes (Fix 8: comment + seeAlso)
    for name, wd_uri in WD_CLASS_MAP.items():
        g.add((wd_uri, RDF.type,  OWL.Class))
        g.add((wd_uri, RDFS.label, Literal(name)))
        if name in WD_CLASS_META:
            comment, q_id = WD_CLASS_META[name]
            g.add((wd_uri, RDFS.comment,  Literal(comment, lang="en")))
            g.add((wd_uri, RDFS.seeAlso,  URIRef(f"https://www.wikidata.org/wiki/{q_id}")))

    # Object properties (P3: Wikidata props via prop_uri; P4: union domains via _union_node)
    for name, domain, range_ in OBJ_PROPS:
        p = prop_uri(name)
        g.add((p, RDF.type,   OWL.ObjectProperty))
        g.add((p, RDFS.label, Literal(name)))
        dom_node = _union_node(domain) if isinstance(domain, tuple) else class_uri(domain)
        rng_node = _union_node(range_) if isinstance(range_, tuple) else class_uri(range_)
        g.add((p, RDFS.domain, dom_node))
        g.add((p, RDFS.range,  rng_node))

    # Data properties
    for name, domain, dtype in DATA_PROPS:
        p = MEME[name]
        g.add((p, RDF.type,    OWL.DatatypeProperty))
        g.add((p, RDFS.domain, class_uri(domain)))
        g.add((p, RDFS.range,  dtype))
        g.add((p, RDFS.label,  Literal(name)))

    # Fix 1 — owl:inverseOf for all 15 inverse pairs
    for fwd, inv in INVERSE_PAIRS:
        p_fwd = prop_uri(fwd)
        p_inv = prop_uri(inv)
        g.add((p_fwd, OWL.inverseOf, p_inv))
        g.add((p_inv, OWL.inverseOf, p_fwd))

    # Fix 4 — hasOriginWork is a specialisation of prov:wasDerivedFrom
    g.add((MEME.hasOriginWork, RDFS.subPropertyOf, PROV.wasDerivedFrom))

    # Fix 2 — declare external properties used in populated but absent from schema
    # prov:wasDerivedFrom — object property linking MemeConcept to OriginWork
    g.add((PROV.wasDerivedFrom, RDF.type,    OWL.ObjectProperty))
    g.add((PROV.wasDerivedFrom, RDFS.domain, MEME.MemeConcept))
    g.add((PROV.wasDerivedFrom, RDFS.range,  WD.Q386724))
    g.add((PROV.wasDerivedFrom, RDFS.label,  Literal("wasDerivedFrom")))
    # dcterms: metadata properties
    for _prop, _label, _rng, _ptype in [
        (DCTERMS.created,     "created",     XSD.integer,  OWL.AnnotationProperty),
        (DCTERMS.description, "description", XSD.string,   OWL.AnnotationProperty),
        (DCTERMS.modified,    "modified",    XSD.string,   OWL.AnnotationProperty),
        (DCTERMS["format"],      "format",      WD.Q235557,   OWL.ObjectProperty),
    ]:
        g.add((_prop, RDF.type,    _ptype))
        g.add((_prop, RDFS.domain, MEME.MemeConcept))
        g.add((_prop, RDFS.range,  _rng))
        g.add((_prop, RDFS.label,  Literal(_label)))
    # schema: annotation properties
    for _prop, _label in [
        (SCHEMA.url,      "url"),
        (SCHEMA.image,    "image"),
        (SCHEMA.keywords, "keywords"),
    ]:
        g.add((_prop, RDF.type,    OWL.AnnotationProperty))
        g.add((_prop, RDFS.domain, MEME.MemeConcept))
        g.add((_prop, RDFS.range,  XSD.string))
        g.add((_prop, RDFS.label,  Literal(_label)))

    # Pre-declared named individuals (controlled vocabularies).
    # declared_ind: {local_iri -> set(class_names)} — tracks which type triples have
    # been added so that shared labels like "Unknown" get typed under EVERY class.
    declared_ind = {}

    for class_name, individuals in VOCAB.items():
        for label in individuals:
            local = _iri_local(label)
            ind   = MEME[local]
            if local not in declared_ind:
                g.add((ind, RDF.type,   OWL.NamedIndividual))
                g.add((ind, RDFS.label, Literal(label)))
                declared_ind[local] = set()
            if class_name not in declared_ind[local]:
                g.add((ind, RDF.type, class_uri(class_name)))
                declared_ind[local].add(class_name)

    # Wikidata-namespace individuals for GeographicRegion (wd:Q82794) and OriginPlatform (wd:Q3220391).
    # Declared here so the unpopulated schema includes them; the populated file reuses these URIs.
    for _qid, _label in WD_REGION_INDIVIDUALS.items():
        _ind = WD[_qid]
        g.add((_ind, RDF.type,     OWL.NamedIndividual))
        g.add((_ind, RDF.type,     WD.Q82794))
        g.add((_ind, RDFS.label,   Literal(_label)))
        g.add((_ind, RDFS.seeAlso, URIRef(f"https://www.wikidata.org/wiki/{_qid}")))
    for _qid, _label in WD_PLATFORM_INDIVIDUALS.items():
        _ind = WD[_qid]
        g.add((_ind, RDF.type,     OWL.NamedIndividual))
        g.add((_ind, RDF.type,     WD.Q3220391))
        g.add((_ind, RDFS.label,   Literal(_label)))
        g.add((_ind, RDFS.seeAlso, URIRef(f"https://www.wikidata.org/wiki/{_qid}")))

    # Fix 10 — CulturalReference subtypes as owl:Class subclasses of wd:Q96622155 (with rdfs:comment)
    for subtype in CULTURAL_REF_SUBTYPES:
        sub_uri = MEME[subtype]
        g.add((sub_uri, RDF.type,        OWL.Class))
        g.add((sub_uri, RDFS.label,      Literal(subtype)))
        g.add((sub_uri, RDFS.subClassOf, WD.Q96622155))
        if subtype in MEMO_CLASS_COMMENTS:
            g.add((sub_uri, RDFS.comment, Literal(MEMO_CLASS_COMMENTS[subtype], lang="en")))

    def ensure_individual(class_name, label, normalize=False):
        """Declare a named individual on first encounter; return its URI.
        normalize=True lowercases the IRI for free-text fields (e.g. OriginWork)
        so that 'VK' and 'vk' collapse to one individual."""
        local = _iri_local_norm(label) if normalize else _iri_local(label)
        ind   = MEME[local]
        if local not in declared_ind:
            g.add((ind, RDF.type,   OWL.NamedIndividual))
            g.add((ind, RDFS.label, Literal(label.strip())))
            declared_ind[local] = set()
        if class_name not in declared_ind[local]:
            g.add((ind, RDF.type, class_uri(class_name)))
            declared_ind[local].add(class_name)
        return ind

    # Meme individuals — named by slug extracted from imageFilename
    for entry_id, rec in results.items():
        if rec.get("error") and not rec.get("hasFormat"):
            continue

        # Resolve imageFilename: prefer field in rec, fall back to meta_lookup
        img_fn = rec.get("imageFilename", "")
        if not img_fn and meta_lookup:
            img_fn = (meta_lookup.get(entry_id) or {}).get("image_filename", "")

        if img_fn:
            stem      = Path(img_fn).stem                        # "0011_renamon"
            name_slug = re.sub(r"^\d{4}_", "", stem)             # "renamon"
            local_id  = _iri_local(name_slug) or f"Meme_{entry_id}"
            label_str = name_slug.replace("_", " ")              # human-readable
        else:
            local_id  = f"Meme_{entry_id}"
            label_str = f"Meme {entry_id}"

        meme_uri = MEME[local_id]
        g.add((meme_uri, RDF.type,   OWL.NamedIndividual))
        g.add((meme_uri, RDF.type,   MEME.MemeConcept))
        g.add((meme_uri, RDFS.label, Literal(label_str)))

        def obj(prop, class_, val):
            if val:
                ind = ensure_individual(class_, val)
                g.add((meme_uri, prop_uri(prop), ind))
                inv = INVERSE_LOOKUP.get(prop)
                if inv:
                    g.add((ind, prop_uri(inv), meme_uri))

        # Macro 1 — CLIP / pixel (stored in classifications.json as hasImageType etc.)
        obj("hasImageType",     "ImageType",     rec.get("hasImageType"))
        obj("hasTextPresence",  "TextPresence",  rec.get("hasTextPresence"))
        obj("hasColorMode",     "ColorMode",     rec.get("hasColorMode"))
        obj("hasSubjectMatter", "SubjectMatter", rec.get("hasSubjectMatter"))

        # Macro 2 — metadata (hasFormat is a list)
        for fmt in rec.get("hasFormat", []):
            if fmt:
                fmt_ind = ensure_individual("MemeFormat", fmt)
                g.add((meme_uri, prop_uri("hasFormat"), fmt_ind))
                g.add((fmt_ind,  prop_uri("isFormatOf"), meme_uri))
        _plat_val = rec.get("hasOriginPlatform")
        if _plat_val:
            _plat_qid = PLATFORM_QID_MAP.get(_plat_val)
            _plat_ind = WD[_plat_qid] if _plat_qid else ensure_individual("OriginPlatform", _plat_val)
            g.add((meme_uri,   prop_uri("hasOriginPlatform"), _plat_ind))
            g.add((_plat_ind,  prop_uri("isOriginPlatformOf"), meme_uri))
        # OriginWork: free-text from KYM, routed to the most specific sub-property.
        # IRI is lowercased so "The Simpsons" / "the simpsons" collapse to one individual.
        # Skip literal "Unknown" — avoids creating a lowercase 'unknown' IRI via normalize=True.
        ow = rec.get("hasOriginWork")
        if ow and ow.strip().lower() not in ("unknown", "none", "n/a", ""):
            schema_type = categorize_origin_work(ow)
            origin_ind  = ensure_individual("OriginWork", ow, normalize=True)
            if schema_type:
                g.add((origin_ind, RDF.type, schema_type))
            g.add((meme_uri, PROV.wasDerivedFrom, origin_ind))
        region_raw = rec.get("hasRegion", "")
        if region_raw and region_raw != "Unknown":
            for _part in region_raw.split(","):
                _part = _part.strip()
                if _part and _part != "Unknown":
                    _norm    = REGION_MAP.get(_part.lower(), _part)
                    _reg_qid = REGION_QID_MAP.get(_norm)
                    _reg_ind = WD[_reg_qid] if _reg_qid else ensure_individual("GeographicRegion", _norm)
                    g.add((meme_uri,   prop_uri("hasRegion"), _reg_ind))
                    g.add((_reg_ind,   prop_uri("isRegionOf"), meme_uri))
        obj("hasTimePeriod",     "TimePeriod",       rec.get("hasTimePeriod"))

        # Macro 3 — format
        ff = rec.get("hasFileFormat")
        if ff and ff != "Unknown":
            g.add((meme_uri, DCTERMS["format"], ensure_individual("FileFormat", ff)))
        obj("hasAnimationStatus", "AnimationStatus", rec.get("hasAnimationStatus"))

        # Data properties (MEME namespace)
        def dat(prop, val, dtype):
            if val is not None and val != "":
                g.add((meme_uri, MEME[prop], Literal(val, datatype=dtype)))

        dat("hasId",                 rec.get("id"),                    XSD.integer)
        dat("imageFilename",         img_fn,                           XSD.string)
        dat("clipImageTypeScore",    rec.get("clipImageTypeScore"),    XSD.float)
        dat("clipTextScore",         rec.get("clipTextScore"),         XSD.float)
        dat("clipPublicFigureScore", rec.get("clipPublicFigureScore"), XSD.float)

        # Metadata properties from meta_lookup (external vocabulary)
        meta = (meta_lookup or {}).get(entry_id, {})

        dat("views",         meta.get("views"),              XSD.integer)
        dat("imageFilePath", meta.get("image_path", ""),     XSD.string)

        meme_url = meta.get("meme_url", "")
        if meme_url:
            g.add((meme_uri, SCHEMA.url, Literal(meme_url, datatype=XSD.string)))

        image_url = meta.get("image_url", "")
        if image_url:
            g.add((meme_uri, SCHEMA.image, Literal(image_url, datatype=XSD.string)))

        scraped_at = meta.get("scraped_at", "")
        if scraped_at:
            g.add((meme_uri, DCTERMS.modified, Literal(scraped_at, datatype=XSD.string)))

        year = meta.get("year")
        try:
            if year is not None:
                g.add((meme_uri, DCTERMS.created, Literal(int(year), datatype=XSD.integer)))
        except (ValueError, TypeError):
            pass

        description = meta.get("description", "")
        if description:
            g.add((meme_uri, DCTERMS.description, Literal(description, datatype=XSD.string)))

        for tag in meta.get("tags", []):
            if tag:
                g.add((meme_uri, SCHEMA.keywords, Literal(tag, datatype=XSD.string)))

    # ── MemeIdea + VariantInstance individuals ────────────────────────────────
    if variants_path and Path(variants_path).exists():
        with open(variants_path, encoding="utf-8") as _vf:
            variant_rows = json.load(_vf)

        # Build slug→meme_uri lookup from already-declared MemeConcept individuals
        def _meme_slug_from_name(name):
            slug = re.sub(r"[^\w\s-]", "", name.lower())
            slug = re.sub(r"[\s_]+", "-", slug).strip("-")
            return _iri_local(slug)

        # Build slug→meme_uri from meta_lookup (meme_url path segment → iri local)
        url_slug_to_meme_uri = {}
        if meta_lookup:
            for _eid, _me in meta_lookup.items():
                _img = _me.get("image_filename", "")
                if _img:
                    _stem = Path(_img).stem
                    _name_slug = re.sub(r"^\d{4}_", "", _stem)
                    _local = _iri_local(_name_slug) or f"Meme_{_eid}"
                    _meme_url = _me.get("meme_url", "")
                    if _meme_url:
                        _url_slug = _meme_url.rstrip("/").split("/")[-1]
                        url_slug_to_meme_uri[_url_slug] = (MEME[_local], _me)

        # Group variants by meme_name
        from collections import defaultdict
        variants_by_meme = defaultdict(list)
        for row in variant_rows:
            variants_by_meme[row["meme_name"]].append(row)

        n_ideas = n_variants = 0
        for meme_name, rows in variants_by_meme.items():
            url_slug = _meme_slug_from_name(meme_name)
            match = url_slug_to_meme_uri.get(url_slug)
            if match is None:
                # Fallback: linear search by comparing slugified meme_url
                for _slug, (_uri, _me) in url_slug_to_meme_uri.items():
                    if _meme_slug_from_name(_slug) == url_slug:
                        match = (_uri, _me)
                        break
            if match is None:
                print(f"  [variants] no MemeConcept match for {meme_name!r}")
                continue

            meme_uri, meta_entry = match

            # MemeIdea individual: <meme_local>_idea
            meme_local = str(meme_uri).split("#")[-1]
            idea_local  = f"{meme_local}_idea"
            idea_uri    = MEME[idea_local]
            g.add((idea_uri, RDF.type,   OWL.NamedIndividual))
            g.add((idea_uri, RDF.type,   WD.Q3249551))           # MemeIdea class
            g.add((idea_uri, RDFS.label, Literal(f"{meme_name} (idea)")))
            desc = (meta_entry.get("description") or "").strip()
            if desc:
                g.add((idea_uri, MEME.conceptDescription, Literal(desc, datatype=XSD.string)))
            # Link MemeConcept ↔ MemeIdea
            g.add((meme_uri, MEME.conceptualizes,     idea_uri))
            g.add((idea_uri, MEME.isConceptualizedAs, meme_uri))
            n_ideas += 1

            # VariantInstance individuals
            for row in rows:
                idx       = int(row.get("index", 0))
                v_local   = f"{meme_local}_v{idx:02d}"
                v_uri     = MEME[v_local]
                g.add((v_uri, RDF.type,   OWL.NamedIndividual))
                g.add((v_uri, RDF.type,   MEME.VariantInstance))
                g.add((v_uri, RDFS.label, Literal(row.get("title") or f"{meme_name} variant {idx}")))
                if row.get("title"):
                    g.add((v_uri, MEME.variantTitle,    Literal(row["title"],    datatype=XSD.string)))
                if row.get("author"):
                    g.add((v_uri, MEME.variantUploader, Literal(row["author"],   datatype=XSD.string)))
                if row.get("image_url"):
                    g.add((v_uri, MEME.variantImageURL, Literal(row["image_url"],datatype=XSD.string)))
                if row.get("filename"):
                    g.add((v_uri, MEME.variantFilename, Literal(row["filename"], datatype=XSD.string)))
                if row.get("photo_url"):
                    g.add((v_uri, MEME.photoURL,        Literal(row["photo_url"],datatype=XSD.string)))
                if row.get("img_alt"):
                    g.add((v_uri, MEME.captionText,     Literal(row["img_alt"],  datatype=XSD.string)))
                g.add((v_uri, MEME.variantIndex, Literal(idx, datatype=XSD.integer)))
                # Link MemeConcept ↔ VariantInstance
                g.add((meme_uri, prop_uri("hasVariant"), v_uri))
                g.add((v_uri,    prop_uri("isVariantOf"), meme_uri))
                n_variants += 1

        print(f"  MemeIdea individuals added: {n_ideas}")
        print(f"  VariantInstance individuals added: {n_variants}")

    g.serialize(destination=str(owl_path), format="xml")
    print(f"OWL ontology written -> {owl_path}")


# Fields that belong exclusively to classifications (not scraping data)
CLASSIFICATION_FIELDS = [
    "imageFilename",
    "hasImageType", "clipImageTypeScore",
    "hasTextPresence", "clipTextScore", "ocrSnippet",
    "hasColorMode", "hasSubjectMatter", "clipPublicFigureScore",
    "hasFormat", "hasOriginPlatform", "hasOriginWork",
    "hasRegion", "hasTimePeriod",
    "hasFileFormat", "hasAnimationStatus",
]

CHECKPOINT_EVERY = 50  # save partial results to disk every N entries


def _write_three_files(results, meta_path, out_path, merged_path):
    """Write classifications.json (classification only) and metadata_merged.json.
    metadata.json is never touched — it stays as pure scraping data.
    """
    # classifications.json — classification fields + id only, sorted by id
    classifications = {}
    for entry_id, rec in sorted(results.items(), key=lambda x: int(x[0])):
        key = f"{int(entry_id):04d}"
        classifications[key] = {"id": rec["id"]}
        for field in CLASSIFICATION_FIELDS:
            if field in rec:
                classifications[key][field] = rec[field]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(classifications, f, ensure_ascii=False, indent=2)
    print(f"classifications.json written -> {out_path}  ({len(classifications)} entries)")

    # metadata_merged.json — scraping fields + classification fields joined by id
    with open(meta_path, encoding="utf-8") as f:
        meta_data = json.load(f)
    merged = []
    for entry in meta_data:
        rec = results.get(f"{entry['id']:04d}", results.get(str(entry["id"]), {}))
        merged_entry = dict(entry)
        for field in CLASSIFICATION_FIELDS:
            if field in rec:
                merged_entry[field] = rec[field]
        merged.append(merged_entry)
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"metadata_merged.json written -> {merged_path}  ({len(merged)} entries)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Classify meme images per ontology schema")
    parser.add_argument("--meta",           default="metadata.json",        help="Input scraping metadata (read-only)")
    parser.add_argument("--images",         default="images_flat",           help="Flat images directory")
    parser.add_argument("--out",            default="classifications.json",  help="Classification-only output")
    parser.add_argument("--merged",         default="metadata_merged.json",  help="Merged scraping + classification output")
    parser.add_argument("--owl",            default="meme_ontology.owl",     help="OWL/RDF output for Protege")
    parser.add_argument("--text-threshold", type=float, default=0.60,
                        help="CLIP ContainsText confidence threshold (default 0.60)")
    parser.add_argument("--subj-threshold", type=float, default=0.40,
                        help="CLIP SubjectMatter confidence threshold; below this → Unknown (default 0.40)")
    parser.add_argument("--textonly-threshold", type=float, default=0.65,
                        help="Extra confidence required to assign TextOnly specifically (default 0.65)")
    parser.add_argument("--limit",          type=int,   default=None,
                        help="Process only N entries (for testing)")
    parser.add_argument("--owl-only",       action="store_true",
                        help="Skip CLIP; rebuild OWL + merged from existing --out JSON")
    parser.add_argument("--variants",       default="variants_metadata.json",
                        help="Variant images metadata for MemeIdea+VariantInstance generation")
    args = parser.parse_args()

    # ── OWL-only / merge-only mode ────────────────────────────────────────────
    if args.owl_only:
        with open(args.out, encoding="utf-8") as f:
            results = json.load(f)
        with open(args.meta, encoding="utf-8") as f:
            _meta_list = json.load(f)
        meta_lookup = {f"{e['id']:04d}": e for e in _meta_list}
        _write_three_files(results, args.meta, args.out, args.merged)
        build_ontology(results, Path(args.owl), meta_lookup, variants_path=args.variants)
        return

    # ── Classification mode ───────────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP ViT-B/32 on {device}...")
    model, preprocess = clip.load("ViT-B/32", device=device)

    global _ocr_reader
    if _HAS_OCR:
        print("Initialising EasyOCR (may download models on first run)...")
        try:
            _ocr_reader = _easyocr_mod.Reader(
                ['en'], gpu=(device == "cuda"), verbose=False
            )
            print("EasyOCR ready.")
        except Exception as e:
            print(f"EasyOCR init failed: {e} — OCR disabled.")

    with open(args.meta, encoding="utf-8") as f:
        metadata = json.load(f)

    if args.limit:
        metadata = metadata[: args.limit]

    # Resume from existing partial results (checkpoint)
    results = {}
    if Path(args.out).exists():
        try:
            with open(args.out, encoding="utf-8") as f:
                existing = json.load(f)
            # Only resume if the existing file looks like a classifications dict
            # (values are dicts with classification fields, not merged entries)
            if existing and isinstance(next(iter(existing.values())), dict):
                # Normalize all keys to zero-padded 4-digit format
                results = {f"{int(k):04d}": v for k, v in existing.items()}
                print(f"Resuming: {len(results)} entries already classified.")
        except Exception:
            pass

    images_dir = Path(args.images)
    total      = len(metadata)
    new_count  = 0

    for i, entry in enumerate(metadata, 1):
        entry_id = f"{entry['id']:04d}"

        # Skip already-processed entries (checkpoint resume)
        if entry_id in results:
            continue

        img_path = images_dir / entry["image_filename"]
        fn       = entry.get("image_filename", "")

        print(f"[{i}/{total}] {fn}", end=" ", flush=True)

        origin_platform, origin_work = normalize_origin(entry.get("origin", ""))
        year_int, period_label       = normalize_time_period(entry.get("year"))

        rec = {
            "id":            entry["id"],
            "imageFilename": entry.get("image_filename", ""),
            # Macro 2 — from KYM metadata
            "hasFormat":          normalize_format(entry.get("type", [])),
            "hasOriginPlatform":  origin_platform,
            "hasOriginWork":      origin_work,
            "hasRegion":          normalize_region(entry.get("region", "")),
            "hasTimePeriod":      period_label,
            # Macro 3 — from image_url extension (not local filename)
            "hasFileFormat":      normalize_file_format(entry.get("image_url", "")),
            "hasAnimationStatus": normalize_animation(entry.get("image_url", "")),
        }

        if not img_path.exists():
            print("MISSING IMAGE")
            rec["error"] = "image file not found"
            results[entry_id] = rec
            new_count += 1
            continue

        try:
            rec.update(classify_image(model, preprocess, device, img_path, args.text_threshold, args.subj_threshold, args.textonly_threshold))
            print("ok")
        except Exception as e:
            print(f"ERROR: {e}")
            rec["error"] = str(e)

        results[entry_id] = rec
        new_count += 1

        # Checkpoint save
        if new_count % CHECKPOINT_EVERY == 0:
            sorted_out = {f"{int(k):04d}": v for k, v in sorted(results.items(), key=lambda x: int(x[0]))}
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(sorted_out, f, ensure_ascii=False, indent=2)
            print(f"  [checkpoint] {len(results)}/{total} saved")

    meta_lookup = {f"{e['id']:04d}": e for e in metadata}
    _write_three_files(results, args.meta, args.out, args.merged)
    build_ontology(results, Path(args.owl), meta_lookup)


if __name__ == "__main__":
    main()
