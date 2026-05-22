import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import torch
from PIL import Image
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, Literal, URIRef

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
    "meme": "Meme",
    "event": "Event",
    "video game": "VideoGame",
    "subculture": "Subculture",
    "person": "Person",
    "trend": "Trend",
    "clothing": "Clothing",
    "website": "Website",
    "hashtag": "Hashtag",
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
_ORIGIN_RULES = [
    ("hasOriginTVShow",    "OriginTVShow",    [
        "television series", "tv series", "tv show", "animated series",
        "web series", "anime series", "cartoon series", "sitcom",
        "miniseries", "webseries",
    ]),
    ("hasOriginFilm",      "OriginFilm",      [
        "(film)", "(movie)", "animated film", "documentary",
        "short film", "motion picture", "(animated movie)",
    ]),
    ("hasOriginVideoGame", "OriginVideoGame", [
        "video game", "(game)", "arcade game", "mobile game",
        "online game", "flash game",
    ]),
    ("hasOriginComic",     "OriginComic",     [
        "comic strip", "comic book", "webcomic", "(manga)",
        "graphic novel", "newspaper comic",
    ]),
    ("hasOriginMusic",     "OriginMusic",     [
        "(song)", "music video", "(album)", "(rap song)", "(single)", "(track)",
    ]),
    ("hasOriginBook",      "OriginBook",      [
        "(novel)", "(book)", "(short story)", "(children's book)",
    ]),
]


def categorize_origin_work(raw):
    """Return (property_name, class_name) for a free-text origin-work string.

    Falls back to ('hasOriginWork', 'OriginWork') when no rule matches.
    Note: hasOriginPerson is defined in the schema but not auto-assigned —
    person names require NER and are best annotated manually in Protégé.
    """
    if not raw or not raw.strip():
        return "hasOriginWork", "OriginWork"
    stripped = raw.strip()
    lower    = stripped.lower()
    if _BOARD_RE.match(stripped):
        return "hasOriginBoard", "OriginBoard"
    for prop, cls, kws in _ORIGIN_RULES:
        if any(kw in lower for kw in kws):
            return prop, cls
    return "hasOriginWork", "OriginWork"


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

ONTO_BASE = "http://www.semanticweb.org/meme-ontology#"
ONTO_URI  = URIRef("http://www.semanticweb.org/meme-ontology")

# All pre-declared named individuals per class
VOCAB = {
    "ImageType":       ["Photograph", "Drawing", "Illustration", "Cartoon", "Painting"],
    "TextPresence":    ["ContainsText", "NoText"],
    "ColorMode":       ["Color", "Monochrome"],
    "SubjectMatter":   ["PersonPresent", "AnimalPresent", "CharacterPresent", "ObjectOnly", "TextOnly", "MultipleSubjects", "Unknown"],
    "TimePeriod":      ["Pre2010", "Period2010to2015", "Period2016to2020", "Period2021toPresent", "Unknown"],
    "FileFormat":      ["JPEG", "PNG", "GIF", "WebP", "BMP", "Unknown"],
    "AnimationStatus": ["Static", "Animated"],
    "MemeFormat": [
        "ImageMacro", "Exploitable", "Catchphrase", "ViralVideo", "Reaction",
        "PopCultureReference", "Character", "Parody", "ParticipatoryMedia",
        "Slang", "Song", "Photoshop", "Snowclone", "Copypasta", "Remix",
        "FanArt", "ViralDebate", "Cliche", "Animal", "SoundEffect",
        "Meme", "Event", "VideoGame", "Subculture", "Person", "Trend",
        "Clothing", "Website", "Hashtag", "Unknown",
    ],
    "OriginPlatform": [
        "TwitterX", "TikTok", "YouTube", "Reddit", "Instagram", "Facebook",
        "Tumblr", "4chan", "iFunny", "Twitch", "Vine", "Imgur", "DeviantArt",
        "Discord", "Snapchat", "KnowYourMeme", "9gag", "MySpace",
        "eBaumsWorld", "SomethingAwful", "FunnyJunk", "Unknown",
    ],
    "GeographicRegion": [
        "UnitedStates", "Japan", "UnitedKingdom", "Worldwide", "China",
        "Brazil", "India", "France", "Canada", "Australia", "Germany",
        "SouthKorea", "Russia", "Spain", "Italy", "Mexico", "Netherlands",
        "Sweden", "Finland", "Poland", "Philippines", "Indonesia",
        "Thailand", "Turkey", "Argentina",
        "Israel", "Singapore", "Ireland", "Ukraine", "Romania", "Serbia",
        "Belgium", "Switzerland", "Vietnam", "CzechRepublic", "Chile",
        "Colombia", "Pakistan",
        "Unknown",
    ],
    "FRBRLevel": ["Work", "Expression", "Manifestation", "Item"],
}

OBJ_PROPS = [
    # Image analysis
    ("hasImageType",       "Meme", "ImageType"),
    ("hasTextPresence",    "Meme", "TextPresence"),
    ("hasColorMode",       "Meme", "ColorMode"),
    ("hasSubjectMatter",   "Meme", "SubjectMatter"),
    # Format & distribution
    ("hasFormat",          "Meme", "MemeFormat"),
    ("hasOriginPlatform",  "Meme", "OriginPlatform"),
    ("hasRegion",          "Meme", "GeographicRegion"),
    ("hasTimePeriod",      "Meme", "TimePeriod"),
    ("hasAnimationStatus", "Meme", "AnimationStatus"),
    ("hasFileFormat",      "Meme", "FileFormat"),
    ("hasReference",       "Meme", "CulturalReference"),
    # Origin work — generic catch-all (used when no specific sub-type is matched)
    ("hasOriginWork",      "Meme", "OriginWork"),
    # Origin work — specific sub-types (classified from KYM 'origin' field)
    ("hasOriginTVShow",    "Meme", "OriginTVShow"),
    ("hasOriginFilm",      "Meme", "OriginFilm"),
    ("hasOriginVideoGame", "Meme", "OriginVideoGame"),
    ("hasOriginComic",     "Meme", "OriginComic"),
    ("hasOriginPerson",    "Meme", "OriginPerson"),   # assigned manually in Protégé
    ("hasOriginBoard",     "Meme", "OriginBoard"),
    ("hasOriginMusic",     "Meme", "OriginMusic"),
    ("hasOriginBook",      "Meme", "OriginBook"),
    # FRBR
    ("hasFRBRLevel",        "Meme",               "FRBRLevel"),
    ("hasFRBRExpression",   "FRBRWork",           "FRBRExpression"),
    ("hasFRBRManifestation","FRBRExpression",     "FRBRManifestation"),
    ("hasFRBRItem",         "FRBRManifestation",  "FRBRItem"),
]

DATA_PROPS = [
    ("hasId",                 XSD.integer),
    ("memeURL",               XSD.string),
    ("imageURL",              XSD.string),
    ("imageFilename",         XSD.string),
    ("yearOfOrigin",          XSD.integer),
    ("scrapedAt",             XSD.string),
    ("tags",                  XSD.string),
    ("clipImageTypeScore",    XSD.float),
    ("clipTextScore",         XSD.float),
    ("clipPublicFigureScore", XSD.float),
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


def build_ontology(results, owl_path, meta_lookup=None):
    """Build OWL ontology from classification results.
    meta_lookup: optional dict {zero-padded-id -> metadata entry} for imageFilename lookup."""
    MEME = Namespace(ONTO_BASE)
    g = Graph()
    g.bind("meme", MEME)
    g.bind("owl",  OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd",  XSD)

    g.add((ONTO_URI, RDF.type, OWL.Ontology))

    # Classes
    all_classes = [
        "Meme", "ImageType", "TextPresence", "ColorMode", "SubjectMatter",
        "MemeFormat", "OriginPlatform", "GeographicRegion",
        "TimePeriod", "FileFormat", "AnimationStatus", "CulturalReference",
        # OriginWork hierarchy
        "OriginWork",
        "OriginTVShow", "OriginFilm", "OriginVideoGame", "OriginComic",
        "OriginPerson", "OriginBoard", "OriginMusic", "OriginBook",
        # FRBR entity classes
        "FRBRLevel", "FRBRWork", "FRBRExpression", "FRBRManifestation", "FRBRItem",
    ]
    for c in all_classes:
        g.add((MEME[c], RDF.type, OWL.Class))
        g.add((MEME[c], RDFS.label, Literal(c)))

    # OriginWork sub-class hierarchy
    for sub in ["OriginTVShow", "OriginFilm", "OriginVideoGame", "OriginComic",
                "OriginPerson", "OriginBoard", "OriginMusic", "OriginBook"]:
        g.add((MEME[sub], RDFS.subClassOf, MEME["OriginWork"]))

    # FRBR entity hierarchy (schema only — instances at Manifestation level for now)
    g.add((MEME["FRBRExpression"],     RDFS.subClassOf, MEME["FRBRWork"]))
    g.add((MEME["FRBRManifestation"],  RDFS.subClassOf, MEME["FRBRExpression"]))
    g.add((MEME["FRBRItem"],           RDFS.subClassOf, MEME["FRBRManifestation"]))

    # Object properties
    for name, domain, range_ in OBJ_PROPS:
        p = MEME[name]
        g.add((p, RDF.type,        OWL.ObjectProperty))
        g.add((p, RDFS.domain,     MEME[domain]))
        g.add((p, RDFS.range,      MEME[range_]))
        g.add((p, RDFS.label,      Literal(name)))

    # Data properties
    for name, dtype in DATA_PROPS:
        p = MEME[name]
        g.add((p, RDF.type,    OWL.DatatypeProperty))
        g.add((p, RDFS.domain, MEME["Meme"]))
        g.add((p, RDFS.range,  dtype))
        g.add((p, RDFS.label,  Literal(name)))

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
                g.add((ind, RDF.type, MEME[class_name]))
                declared_ind[local].add(class_name)

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
            g.add((ind, RDF.type, MEME[class_name]))
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
        g.add((meme_uri, RDF.type,   MEME.Meme))
        g.add((meme_uri, RDFS.label, Literal(label_str)))

        def obj(prop, class_, val):
            if val:
                g.add((meme_uri, MEME[prop], ensure_individual(class_, val)))

        # Macro 1 — CLIP / pixel
        obj("hasImageType",      "ImageType",     rec.get("hasImageType"))
        obj("hasTextPresence",   "TextPresence",  rec.get("hasTextPresence"))
        obj("hasColorMode",      "ColorMode",     rec.get("hasColorMode"))
        obj("hasSubjectMatter",  "SubjectMatter", rec.get("hasSubjectMatter"))

        # Macro 2 — metadata (hasFormat is a list)
        for fmt in rec.get("hasFormat", []):
            if fmt:
                g.add((meme_uri, MEME.hasFormat, ensure_individual("MemeFormat", fmt)))
        obj("hasOriginPlatform", "OriginPlatform",  rec.get("hasOriginPlatform"))
        # OriginWork: free-text from KYM, routed to the most specific sub-property.
        # IRI is lowercased so "The Simpsons" / "the simpsons" collapse to one individual.
        # Skip literal "Unknown" — avoids creating a lowercase 'unknown' IRI via normalize=True.
        ow = rec.get("hasOriginWork")
        if ow and ow.strip().lower() not in ("unknown", "none", "n/a", ""):
            prop, cls = categorize_origin_work(ow)
            g.add((meme_uri, MEME[prop], ensure_individual(cls, ow, normalize=True)))
        obj("hasRegion",         "GeographicRegion", rec.get("hasRegion"))
        obj("hasTimePeriod",     "TimePeriod",       rec.get("hasTimePeriod"))

        # FRBR — all current Meme individuals represent a specific image file,
        # which maps to the Manifestation level of the FRBR hierarchy.
        g.add((meme_uri, MEME.hasFRBRLevel,
               ensure_individual("FRBRLevel", "Manifestation")))

        # Macro 3 — format
        obj("hasFileFormat",      "FileFormat",      rec.get("hasFileFormat"))
        obj("hasAnimationStatus", "AnimationStatus", rec.get("hasAnimationStatus"))

        # Data properties
        def dat(prop, val, dtype):
            if val is not None and val != "":
                g.add((meme_uri, MEME[prop], Literal(val, datatype=dtype)))

        dat("hasId",                 rec.get("id"),                    XSD.integer)
        dat("memeURL",               rec.get("memeURL", ""),           XSD.string)
        dat("imageURL",              rec.get("imageURL", ""),          XSD.string)
        dat("imageFilename",         rec.get("imageFilename", ""),     XSD.string)
        dat("scrapedAt",             rec.get("scrapedAt", ""),         XSD.string)
        dat("clipImageTypeScore",    rec.get("clipImageTypeScore"),    XSD.float)
        dat("clipTextScore",         rec.get("clipTextScore"),         XSD.float)
        dat("clipPublicFigureScore", rec.get("clipPublicFigureScore"), XSD.float)

        if rec.get("yearOfOrigin") is not None:
            g.add((meme_uri, MEME.yearOfOrigin,
                   Literal(rec["yearOfOrigin"], datatype=XSD.integer)))

        for tag in rec.get("tags", []):
            if tag:
                g.add((meme_uri, MEME.tags, Literal(tag, datatype=XSD.string)))

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
    args = parser.parse_args()

    # ── OWL-only / merge-only mode ────────────────────────────────────────────
    if args.owl_only:
        with open(args.out, encoding="utf-8") as f:
            results = json.load(f)
        with open(args.meta, encoding="utf-8") as f:
            _meta_list = json.load(f)
        meta_lookup = {f"{e['id']:04d}": e for e in _meta_list}
        _write_three_files(results, args.meta, args.out, args.merged)
        build_ontology(results, Path(args.owl), meta_lookup)
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
