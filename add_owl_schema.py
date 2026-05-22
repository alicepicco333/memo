"""
add_owl_schema.py
-----------------
Prepends the full OWL 2 schema (ontology metadata, class hierarchy, annotation
properties, object/data properties) to meme_ontology.owl while keeping every
existing individual triple unchanged.

Run once: python add_owl_schema.py
"""

BASE = "http://www.semanticweb.org/meme-ontology"
NS   = BASE + "#"
IN_F = "meme_ontology.owl"

# ─────────────────────────────────────────────────────────────────────────────
# The full schema block to insert after <rdf:RDF ...>
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA = """
  <!-- ════════════════════════════════════════════════════════════════════════
       Ontology metadata
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Ontology rdf:about="{base}">
    <rdfs:label xml:lang="en">Meme Ontology (MEMO)</rdfs:label>
    <dc:creator>Meme Ontology Project</dc:creator>
    <dc:description xml:lang="en">The Meme Ontology (MEMO) is an OWL 2 DL
ontology for the formal description of internet memes. It models meme templates
(MemeConcept), their underlying creative ideas (MemeIdea), and scraped variant
images (VariantInstance) using a FRBR-aligned four-level abstraction hierarchy
and Panofsky's three levels of semantic analysis. Value classes provide
controlled vocabularies for format, platform, image type, transformation extent
and dimension, and other classifiers. 5,000 meme concepts, 50 enriched meme
ideas and 391 variant instances are included as named individuals.</dc:description>
    <dc:rights xml:lang="en">Released for academic research. Data sourced from
Know Your Meme under fair use.</dc:rights>
    <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#gYear">2024</dcterms:created>
    <owl:versionInfo rdf:datatype="http://www.w3.org/2001/XMLSchema#string">1.0</owl:versionInfo>
    <rdfs:seeAlso rdf:resource="https://github.com/meme-ontology/meme-ontology"/>
  </owl:Ontology>

  <!-- ════════════════════════════════════════════════════════════════════════
       Annotation properties
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:AnnotationProperty rdf:about="{ns}frbrLevel">
    <rdfs:label xml:lang="en">FRBR level</rdfs:label>
    <rdfs:comment xml:lang="en">Associates a class or property with its
position in the FRBR abstraction hierarchy: Work, Expression, Manifestation, or
Item.</rdfs:comment>
    <rdfs:range rdf:resource="{ns}FRBRLevel"/>
  </owl:AnnotationProperty>

  <owl:AnnotationProperty rdf:about="{ns}semanticLevel">
    <rdfs:label xml:lang="en">semantic level</rdfs:label>
    <rdfs:comment xml:lang="en">Associates a class or property with a Panofsky
level of iconological analysis: PreIconographical, Iconographical, or
Iconological.</rdfs:comment>
    <rdfs:range rdf:resource="{ns}SemanticLevel"/>
  </owl:AnnotationProperty>

  <owl:AnnotationProperty rdf:about="{ns}documentaryLevel">
    <rdfs:label xml:lang="en">documentary level</rdfs:label>
    <rdfs:comment xml:lang="en">Associates a class or property with the
documentary analysis dimension (provenance, platform, geographic and temporal
context).</rdfs:comment>
    <rdfs:range rdf:resource="{ns}DocumentaryLevel"/>
  </owl:AnnotationProperty>

  <!-- ════════════════════════════════════════════════════════════════════════
       Axis classes — FRBR
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Class rdf:about="{ns}FRBRLevel">
    <rdfs:label xml:lang="en">FRBR Level</rdfs:label>
    <rdfs:comment xml:lang="en">Abstract axis class grouping the four FRBR
abstraction levels (Work, Expression, Manifestation, Item). This class has no
direct individuals; it exists as a superclass to enable annotation-based
classification of domain and value classes.</rdfs:comment>
  </owl:Class>

  <owl:Class rdf:about="{ns}Work">
    <rdfs:label xml:lang="en">Work</rdfs:label>
    <rdfs:comment xml:lang="en">FRBR Work: the distinct intellectual or artistic
creation — the underlying meme idea abstracted from any concrete realisation.
Corresponds to MemeIdea individuals.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}FRBRLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}Expression">
    <rdfs:label xml:lang="en">Expression</rdfs:label>
    <rdfs:comment xml:lang="en">FRBR Expression: a specific realisation of a
Work — the canonical meme template with its format, platform and cultural
associations. Corresponds to MemeConcept individuals.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}FRBRLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}Manifestation">
    <rdfs:label xml:lang="en">Manifestation</rdfs:label>
    <rdfs:comment xml:lang="en">FRBR Manifestation: the physical or digital
embodiment of an Expression — characterised by image type, colour mode, file
format and animation status.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}FRBRLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}Item">
    <rdfs:label xml:lang="en">Item</rdfs:label>
    <rdfs:comment xml:lang="en">FRBR Item: a single exemplar — one scraped
variant image with its transformation annotations. Corresponds to
VariantInstance individuals.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}FRBRLevel"/>
  </owl:Class>

  <!-- ════════════════════════════════════════════════════════════════════════
       Axis classes — Panofsky semantic levels
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Class rdf:about="{ns}SemanticLevel">
    <rdfs:label xml:lang="en">Semantic Level</rdfs:label>
    <rdfs:comment xml:lang="en">Abstract axis class grouping Panofsky's three
levels of iconological analysis. No direct individuals.</rdfs:comment>
  </owl:Class>

  <owl:Class rdf:about="{ns}PreIconographical">
    <rdfs:label xml:lang="en">Pre-Iconographical</rdfs:label>
    <rdfs:comment xml:lang="en">Panofsky level I: description of visible forms
(colours, shapes, image medium) without symbolic interpretation. Applies to
properties describing the physical appearance of the image.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}SemanticLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}Iconographical">
    <rdfs:label xml:lang="en">Iconographical</rdfs:label>
    <rdfs:comment xml:lang="en">Panofsky level II: recognition of conventional
subjects, formats, cultural motifs and structural patterns.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}SemanticLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}Iconological">
    <rdfs:label xml:lang="en">Iconological</rdfs:label>
    <rdfs:comment xml:lang="en">Panofsky level III: interpretation of intrinsic
cultural meaning, symbolic significance and ideological value.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}SemanticLevel"/>
  </owl:Class>

  <!-- ════════════════════════════════════════════════════════════════════════
       Axis class — Documentary level
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Class rdf:about="{ns}DocumentaryLevel">
    <rdfs:label xml:lang="en">Documentary Level</rdfs:label>
    <rdfs:comment xml:lang="en">Abstract axis class representing the documentary
analysis dimension: origin, platform, geographic and temporal provenance of a
meme.</rdfs:comment>
  </owl:Class>

  <!-- ════════════════════════════════════════════════════════════════════════
       Domain classes
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Class rdf:about="{ns}MemeConcept">
    <rdfs:label xml:lang="en">Meme Concept</rdfs:label>
    <rdfs:comment xml:lang="en">A canonical internet meme template as indexed
on Know Your Meme. Represents the stable, Expression-level identity of a meme
across all its variants. 5,000 named individuals are included, classified by
image type, format, platform, region and time period.</rdfs:comment>
    <meme:frbrLevel rdf:resource="{ns}Expression"/>
    <meme:semanticLevel rdf:resource="{ns}Iconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}MemeIdea">
    <rdfs:label xml:lang="en">Meme Idea</rdfs:label>
    <rdfs:comment xml:lang="en">The abstract Work-level idea underlying a meme:
its core narrative, emotional register, rhetorical function or cultural role,
independent of any specific image or format. 50 enriched individuals from the
D0 sample, with descriptions and cultural reference annotations.</rdfs:comment>
    <meme:frbrLevel rdf:resource="{ns}Work"/>
    <meme:semanticLevel rdf:resource="{ns}Iconological"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}VariantInstance">
    <rdfs:label xml:lang="en">Variant Instance</rdfs:label>
    <rdfs:comment xml:lang="en">A single scraped variant image — an Item-level
exemplar of a MemeConcept. 391 named individuals with transformation extent and
dimension annotations for 5 fully annotated meme templates.</rdfs:comment>
    <meme:frbrLevel rdf:resource="{ns}Item"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <!-- ════════════════════════════════════════════════════════════════════════
       ValueClass grouping + controlled-vocabulary subclasses
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:Class rdf:about="{ns}ValueClass">
    <rdfs:label xml:lang="en">Value Class</rdfs:label>
    <rdfs:comment xml:lang="en">Grouping superclass for all controlled-vocabulary
term classes used as object values of MEMO object properties. Individuals of
these classes are the enumerated values that classify MemeConcept and
VariantInstance individuals.</rdfs:comment>
  </owl:Class>

  <owl:Class rdf:about="{ns}MemeFormat">
    <rdfs:label xml:lang="en">Meme Format</rdfs:label>
    <rdfs:comment xml:lang="en">The rhetorical or structural format of a meme
(e.g. ImageMacro, Catchphrase, Exploitable, Reaction, ViralVideo). Classifies
memes at the Expression level with Iconographical analysis.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Expression"/>
    <meme:semanticLevel rdf:resource="{ns}Iconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}OriginPlatform">
    <rdfs:label xml:lang="en">Origin Platform</rdfs:label>
    <rdfs:comment xml:lang="en">The online platform where a meme first appeared
or gained traction (e.g. Reddit, Twitter/X, 4chan, TikTok). Classified at the
Expression level with Documentary provenance.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Expression"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}OriginWork">
    <rdfs:label xml:lang="en">Origin Work</rdfs:label>
    <rdfs:comment xml:lang="en">The original cultural work (film, TV show, video
game, book, song, etc.) from which a meme derives its source material.
Classified at the Work level with Iconological analysis.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Work"/>
    <meme:semanticLevel rdf:resource="{ns}Iconological"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}CanonicalImageType">
    <rdfs:label xml:lang="en">Canonical Image Type</rdfs:label>
    <rdfs:comment xml:lang="en">The visual medium of the canonical meme image
(Photograph, Drawing, Cartoon, Illustration, Painting, etc.). Pre-iconographical
classification at the Manifestation level, assigned via CLIP-based scoring.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}ImageType">
    <rdfs:label xml:lang="en">Image Type</rdfs:label>
    <rdfs:comment xml:lang="en">The visual medium type of an individual variant
image. Uses the same controlled vocabulary as CanonicalImageType but applied at
the Item (VariantInstance) level.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Item"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}CanonicalColorMode">
    <rdfs:label xml:lang="en">Canonical Color Mode</rdfs:label>
    <rdfs:comment xml:lang="en">Whether the canonical meme image is in colour or
monochrome.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}CanonicalTextPresence">
    <rdfs:label xml:lang="en">Canonical Text Presence</rdfs:label>
    <rdfs:comment xml:lang="en">Whether the canonical meme image contains
overlaid text.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}CanonicalSubjectMatter">
    <rdfs:label xml:lang="en">Canonical Subject Matter</rdfs:label>
    <rdfs:comment xml:lang="en">The category of subjects depicted in the
canonical image (PersonPresent, AnimalPresent, ObjectOnly, TextOnly,
MultipleSubjects, etc.).</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}GeographicRegion">
    <rdfs:label xml:lang="en">Geographic Region</rdfs:label>
    <rdfs:comment xml:lang="en">The country or geographic region of a meme's
origin.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}TimePeriod">
    <rdfs:label xml:lang="en">Time Period</rdfs:label>
    <rdfs:comment xml:lang="en">The era in which a meme originated or peaked
(Pre2010, Period2010to2015, Period2016to2020, Period2021toPresent).</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}FileFormat">
    <rdfs:label xml:lang="en">File Format</rdfs:label>
    <rdfs:comment xml:lang="en">The digital file format of the meme image (JPEG,
PNG, GIF, WebP, BMP).</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}AnimationStatus">
    <rdfs:label xml:lang="en">Animation Status</rdfs:label>
    <rdfs:comment xml:lang="en">Whether a meme image is static or animated
(GIF/video).</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}TransformationExtent">
    <rdfs:label xml:lang="en">Transformation Extent</rdfs:label>
    <rdfs:comment xml:lang="en">The degree to which a variant departs from the
canonical template: Minimal (close copy), Moderate, Substantial, or Parody
(radical departure).</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Item"/>
    <meme:semanticLevel rdf:resource="{ns}Iconographical"/>
  </owl:Class>

  <owl:Class rdf:about="{ns}TransformationDimension">
    <rdfs:label xml:lang="en">Transformation Dimension</rdfs:label>
    <rdfs:comment xml:lang="en">The axis along which a variant transforms the
canonical template: CaptionChange, VisualSubstrate, MediumShift, StyleShift,
CompositionShift, CrossoverMerge, LanguageShift, Localization.</rdfs:comment>
    <rdfs:subClassOf rdf:resource="{ns}ValueClass"/>
    <meme:frbrLevel rdf:resource="{ns}Item"/>
    <meme:semanticLevel rdf:resource="{ns}Iconographical"/>
  </owl:Class>

  <!-- ════════════════════════════════════════════════════════════════════════
       Object properties
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:ObjectProperty rdf:about="{ns}hasFormat">
    <rdfs:label xml:lang="en">has format</rdfs:label>
    <rdfs:comment xml:lang="en">Links a MemeConcept to one or more MemeFormat
values describing its rhetorical structure.</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}MemeFormat"/>
    <meme:frbrLevel rdf:resource="{ns}Expression"/>
    <meme:semanticLevel rdf:resource="{ns}Iconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasCanonicalImageType">
    <rdfs:label xml:lang="en">has canonical image type</rdfs:label>
    <rdfs:comment xml:lang="en">The visual medium of the canonical meme image,
assigned by CLIP-based classification.</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}CanonicalImageType"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasCanonicalColorMode">
    <rdfs:label xml:lang="en">has canonical color mode</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}CanonicalColorMode"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasCanonicalTextPresence">
    <rdfs:label xml:lang="en">has canonical text presence</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}CanonicalTextPresence"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasCanonicalSubjectMatter">
    <rdfs:label xml:lang="en">has canonical subject matter</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}CanonicalSubjectMatter"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasOriginWork">
    <rdfs:label xml:lang="en">has origin work</rdfs:label>
    <rdfs:comment xml:lang="en">Links a MemeConcept to the cultural Work it
derives from or references.</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}OriginWork"/>
    <meme:frbrLevel rdf:resource="{ns}Work"/>
    <meme:semanticLevel rdf:resource="{ns}Iconological"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasOriginBoard">
    <rdfs:label xml:lang="en">has origin board</rdfs:label>
    <rdfs:comment xml:lang="en">Links a MemeConcept to the specific imageboard
or forum thread where it originated.</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <meme:frbrLevel rdf:resource="{ns}Expression"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasRegion">
    <rdfs:label xml:lang="en">has region</rdfs:label>
    <rdfs:comment xml:lang="en">The geographic region of a meme's origin or
primary circulation.</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}GeographicRegion"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasTimePeriod">
    <rdfs:label xml:lang="en">has time period</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}TimePeriod"/>
    <meme:documentaryLevel rdf:resource="{ns}DocumentaryLevel"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasFileFormat">
    <rdfs:label xml:lang="en">has file format</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}FileFormat"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <owl:ObjectProperty rdf:about="{ns}hasAnimationStatus">
    <rdfs:label xml:lang="en">has animation status</rdfs:label>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="{ns}AnimationStatus"/>
    <meme:frbrLevel rdf:resource="{ns}Manifestation"/>
    <meme:semanticLevel rdf:resource="{ns}PreIconographical"/>
  </owl:ObjectProperty>

  <!-- ════════════════════════════════════════════════════════════════════════
       Datatype properties
       ════════════════════════════════════════════════════════════════════════ -->

  <owl:DatatypeProperty rdf:about="{ns}hasId">
    <rdfs:label xml:lang="en">has ID</rdfs:label>
    <rdfs:comment xml:lang="en">Numeric identifier matching the meme's position
in the scraped dataset (1–5000).</rdfs:comment>
    <rdfs:domain rdf:resource="{ns}MemeConcept"/>
    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#integer"/>
  </owl:DatatypeProperty>

  <owl:DatatypeProperty rdf:about="{ns}clipImageTypeScore">
    <rdfs:label xml:lang="en">CLIP image type score</rdfs:label>
    <rdfs:comment xml:lang="en">Confidence score (0–1) from the CLIP model for
the assigned CanonicalImageType classification.</rdfs:comment>
    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#float"/>
  </owl:DatatypeProperty>

  <owl:DatatypeProperty rdf:about="{ns}clipTextScore">
    <rdfs:label xml:lang="en">CLIP text score</rdfs:label>
    <rdfs:comment xml:lang="en">CLIP confidence score (0–1) for the text-presence
classification.</rdfs:comment>
    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#float"/>
  </owl:DatatypeProperty>

  <owl:DatatypeProperty rdf:about="{ns}clipPublicFigureScore">
    <rdfs:label xml:lang="en">CLIP public figure score</rdfs:label>
    <rdfs:comment xml:lang="en">CLIP confidence score (0–1) estimating the
likelihood that the image depicts a recognisable public figure.</rdfs:comment>
    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#float"/>
  </owl:DatatypeProperty>

""".format(base=BASE, ns=NS)

# ─────────────────────────────────────────────────────────────────────────────
# The new <rdf:RDF> opening tag with all needed namespaces
# ─────────────────────────────────────────────────────────────────────────────
NEW_RDF_OPEN = """<rdf:RDF
   xml:base="{base}"
   xmlns:meme="http://www.semanticweb.org/meme-ontology#"
   xmlns:owl="http://www.w3.org/2002/07/owl#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
   xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:dcterms="http://purl.org/dc/terms/"
>""".format(base=BASE)

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
print("Reading", IN_F, "...")
with open(IN_F, encoding="utf-8") as f:
    content = f.read()

# Guard: don't double-apply
if "<owl:Ontology" in content:
    print("owl:Ontology already present — aborting to avoid duplication.")
    raise SystemExit(1)

# Replace the opening <rdf:RDF ...> tag
old_open_start = content.index("<rdf:RDF")
old_open_end   = content.index(">", old_open_start) + 1
old_open       = content[old_open_start:old_open_end]

# Find where the first individual starts so we insert schema before it
first_desc = content.index("<rdf:Description", old_open_end)

# Build the new content:
# xml header + new rdf:RDF tag + schema block + original individual data
xml_header = content[:old_open_start]  # <?xml version...>
individuals = content[first_desc:]      # all <rdf:Description> blocks + </rdf:RDF>

new_content = xml_header + NEW_RDF_OPEN + "\n" + SCHEMA + individuals

out_f = IN_F
tmp_f = IN_F + ".tmp"
with open(tmp_f, "w", encoding="utf-8") as f:
    f.write(new_content)

import os
os.replace(tmp_f, out_f)

print("Done. Written to", out_f)
print("  Original length:", len(content), "chars")
print("  New length:     ", len(new_content), "chars")
print("  Added schema block:", len(SCHEMA), "chars")
