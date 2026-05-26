#!/usr/bin/env python3
import re
from pathlib import Path

# Label replacements - from spaced to camelCase
LABEL_FIXES = {
    "T V Series": "TvSeries",
    "TV Series": "TvSeries",
    "TVSeries": "TvSeries",
    "Comic Book": "ComicBook",
    "AI-generated": "AiGenerated",
    "Conspiracy Theory": "ConspiracyTheory",
    "Deviant Art": "DeviantArt",
    "El Salvador": "ElSalvador",
    "Fan Labor": "FanLabor",
    "Four Chan": "FourChan",
    "Lip Dub": "LipDub",
    "Little Italy": "LittleItaly",
    "Optical Illusion": "OpticalIllusion",
    "Shock Media": "ShockMedia",
    "Social Game": "SocialGame",
    "South Korea": "SouthKorea",
    "United States, Netherlands": "UnitedStatesNetherlands",
    "United States": "UnitedStates",
    "Unknown Format": "UnknownFormat",
    "Unknown Period": "UnknownPeriod",
    "Unknown Platform": "UnknownPlatform",
    "Unknown Region": "UnknownRegion",
    "Vatican City": "VaticanCity",
    "Visual Effect": "VisualEffect",
    "has ID": "hasId",
    "Has Variant Color Mode": "hasVariantColorMode",
    "Has Variant Image Type": "hasVariantImageType",
    "Has Variant Subject Matter": "hasVariantSubjectMatter",
    "Has Variant Text Presence": "hasVariantTextPresence",
    "has animation status": "hasAnimationStatus",
    "has canonical color mode": "hasCanonicalColorMode",
    "has canonical image type": "hasCanonicalImageType",
    "Has Canonical Subject Matter": "hasCanonicalSubjectMatter",
    "has canonical text presence": "hasCanonicalTextPresence",
    "has file format": "hasFileFormat",
    "has origin board": "hasOriginBoard",
    "has origin platform": "hasOriginPlatform",
    "has origin work": "hasOriginWork",
    "has region": "hasRegion",
    "has time period": "hasTimePeriod",
    "has Variant": "hasVariant",
    "is Animation Status Of": "isAnimationStatusOf",
    "is Canonical Color Mode Of": "isCanonicalColorModeOf",
    "is Canonical Image Type Of": "isCanonicalImageTypeOf",
    "is Canonical Subject Matter Of": "isCanonicalSubjectMatterOf",
    "is Canonical Text Presence Of": "isCanonicalTextPresenceOf",
    "is Color Mode Of": "isColorModeOf",
    "is File Format Of": "isFileFormatOf",
    "is Format Of": "isFormatOf",
    "is Image Type Of": "isImageTypeOf",
    "is Origin Board Of": "isOriginBoardOf",
    "is Origin Book Of": "isOriginBookOf",
    "is Origin Comic Of": "isOriginComicOf",
    "is Origin Film Of": "isOriginFilmOf",
    "is Origin Music Of": "isOriginMusicOf",
    "is Origin Person Of": "isOriginPersonOf",
    "is Origin Platform Of": "isOriginPlatformOf",
    "is Origin TV Show Of": "isOriginTVShowOf",
    "is Origin Video Game Of": "isOriginVideoGameOf",
    "is Origin Work Of": "isOriginWorkOf",
    "is Referenced In": "isReferencedIn",
    "is Region Of": "isRegionOf",
    "is Text Presence Of": "isTextPresenceOf",
    "is Time Period Of": "isTimePeriodOf",
    "is Transformation Dimension Of": "isTransformationDimensionOf",
    "is Transformation Extent Of": "isTransformationExtentOf",
    "Animation Status": "AnimationStatus",
    "Cultural Reference": "CulturalReference",
    "Transformation Dimension": "TransformationDimension",
    "Meme Idea": "MemeIdea",
    "Transformation Extent": "TransformationExtent",
    "File Format": "FileFormat",
    "Time Period": "TimePeriod",
    "Image Type": "ImageType",
    "Origin Work": "OriginWork",
    "Origin Platform": "OriginPlatform",
    "Variant Instance": "VariantInstance",
    "Meme Format": "MemeFormat",
    "Meme Concept": "MemeConcept",
    "Geographic Region": "GeographicRegion",
}

def fix_labels(file_path):
    """Fix all rdfs:label values to camelCase"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    changes = 0
    for old_label, new_label in LABEL_FIXES.items():
        # Match rdfs:label "label" with optional language tag
        pattern = rf'rdfs:label "{re.escape(old_label)}"([@\s]*(?:@en)?[\s;])'
        replacement = rf'rdfs:label "{new_label}"\1'

        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            changes += len(re.findall(pattern, content))
            content = new_content

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return changes

# Process all 4 ontology files
files = [
    'meme_ontology.ttl',
    'meme_ontology.owl',
    'meme_ontology_unpopulated.ttl',
    'meme_ontology_unpopulated.owl',
]

base_dir = Path('c:/Users/awlic/Desktop/meme-ontology')
total_changes = 0

for file in files:
    file_path = base_dir / file
    if file_path.exists():
        changes = fix_labels(file_path)
        total_changes += changes
        print(f"{file}: {changes} labels fixed")
    else:
        print(f"{file}: not found")

print(f"\nTotal: {total_changes} labels fixed across all files")
