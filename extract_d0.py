"""
extract_d0.py
-------------
Build meme_ontology_d0.owl / .ttl — the D0 subset ontology.

Contents:
  TBox  — all class and property declarations from meme_ontology_unpopulated.owl
  ABox  — 50 D0 MemeConcept individuals (with all their properties)
          50 linked MemeIdea individuals (43 full + 7 stubs)
         391 VariantInstance individuals (with transformation annotations)
         116 CulturalReference individuals (with hasReference / isReferencedIn)
          83 controlled-vocabulary individuals (MemeFormat, ImageType, TimePeriod…)
         D0-referenced GeographicRegion and OriginPlatform individuals only

Excluded: the remaining 4,950 MemeConcepts, ~867 OriginWork individuals,
          and region/platform individuals not used by D0 memes.

Usage:
    python extract_d0.py [--populated meme_ontology.owl]
                         [--schema   meme_ontology_unpopulated.owl]
                         [--out-owl  meme_ontology_d0.owl]
                         [--out-ttl  meme_ontology_d0.ttl]
"""

import argparse
import json
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal, XSD

MEME   = Namespace("https://purl.org/memo#")
WD     = Namespace("http://www.wikidata.org/entity/")
WDP    = Namespace("http://www.wikidata.org/prop/direct/")
SCHEMA = Namespace("https://schema.org/")
FRBRER = Namespace("http://iflastandards.info/ns/fr/frbr/frbrer/")

# Classes that mark data-derived (non-schema) ABox individuals
DATA_CLASSES = {
    MEME.MemeConcept,
    MEME.MemeIdea,
    MEME.VariantInstance,
    MEME.CulturalReference,   # was WD.Q96622155
    MEME.OriginWork,           # was WD.Q386724
    SCHEMA.TVSeries, SCHEMA.Movie, SCHEMA.VideoGame,
    SCHEMA.ComicSeries, SCHEMA.MusicAlbum, SCHEMA.Book,
}
for _sub in ["PoliticalEvent", "MediaProperty", "WebCulture",
             "PublicFigure", "HistoricalEvent", "SocialPhenomenon"]:
    DATA_CLASSES.add(MEME[_sub])

GEO_PLAT_TYPES = {MEME.GeographicRegion, MEME.OriginPlatform}  # was WD.Q82794 / WD.Q3220391


def _inject_owl_xmlns(xml_str: str) -> str:
    CANDIDATES = [
        ('frbrer', 'http://iflastandards.info/ns/fr/frbr/frbrer/'),
        ('wd',     'http://www.wikidata.org/entity/'),
        ('wdp',    'http://www.wikidata.org/prop/direct/'),
        ('schema', 'https://schema.org/'),
        ('prov',   'http://www.w3.org/ns/prov#'),
    ]
    rdf_start = xml_str.find('<rdf:RDF')
    rdf_end   = xml_str.find('>', rdf_start)
    rdf_block = xml_str[rdf_start:rdf_end]
    to_add = [
        f'xmlns:{prefix}="{uri}"'
        for prefix, uri in CANDIDATES
        if f'xmlns:{prefix}=' not in rdf_block
    ]
    if not to_add:
        return xml_str
    extra = '   ' + '\n   '.join(to_add) + '\n'
    return xml_str.replace("<rdf:RDF\n", f"<rdf:RDF\n{extra}", 1)


def build_d0(populated_path, schema_path, out_owl, out_ttl):
    print(f"Loading populated  : {populated_path}")
    g = Graph()
    g.parse(str(populated_path), format="xml")
    print(f"  {len(g):,} triples")

    print(f"Loading schema     : {schema_path}")
    g_schema = Graph()
    g_schema.parse(str(schema_path), format="xml")
    print(f"  {len(g_schema):,} triples")

    # ── Identify D0 MemeConcepts ──────────────────────────────────────────────
    d0 = set()
    for s in g.subjects(MEME.conceptualizes, None):
        if (s, RDF.type, MEME.MemeConcept) in g:
            d0.add(s)
    for s in g.subjects(WDP.P527, None):          # hasVariant
        if (s, RDF.type, MEME.MemeConcept) in g:
            d0.add(s)
    for s in g.subjects(MEME.hasReference, None):
        if (s, RDF.type, MEME.MemeConcept) in g:
            d0.add(s)
    print(f"D0 MemeConcepts    : {len(d0)}")

    # ── Load metadata for stub MemeIdea descriptions ─────────────────────────
    meta_path = populated_path.parent / "metadata_merged.json"
    meta_by_slug: dict = {}
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as _f:
            for _entry in json.load(_f):
                _fn = _entry.get("image_filename", "") or ""
                _slug = re.sub(r"^\d{4}_", "", Path(_fn).stem) if _fn else ""
                if _slug:
                    meta_by_slug[_slug] = _entry

    # ── Collect linked ABox individuals ───────────────────────────────────────
    ideas    = {o for d in d0 for o in g.objects(d, MEME.conceptualizes)}
    variants = {o for d in d0 for o in g.objects(d, WDP.P527)}
    refs     = {o for d in d0 for o in g.objects(d, MEME.hasReference)}

    # Stub MemeIdea individuals for D0 memes that have no conceptualizes link
    d0_without_idea = {d for d in d0 if not list(g.objects(d, MEME.conceptualizes))}
    stub_ideas: dict[URIRef, dict] = {}
    for _meme_uri in d0_without_idea:
        _local = str(_meme_uri).split("#")[-1]
        _idea_uri = MEME[f"{_local}_idea"]
        _meta = meta_by_slug.get(_local, {})
        _label = _meta.get("title", _local) + " (idea)"
        _desc  = (_meta.get("description") or "").strip()
        stub_ideas[_idea_uri] = {"meme_uri": _meme_uri, "label": _label, "desc": _desc}
        ideas.add(_idea_uri)

    print(f"MemeIdea           : {len(ideas)} ({len(stub_ideas)} stubs)")
    print(f"VariantInstance    : {len(variants)}")
    print(f"CulturalReference  : {len(refs)}")

    # ── D0-referenced OriginWork individuals ─────────────────────────────────
    d0_works = {o for d in d0 for o in g.objects(d, MEME.hasOriginWork)}
    print(f"D0 OriginWork      : {len(d0_works)}")

    # ── D0-referenced region and platform individuals only ────────────────────
    d0_geo  = {o for d in d0 for o in g.objects(d, WDP.P495)}   # hasRegion
    d0_plat = {o for d in d0 for o in g.objects(d, WDP.P123)}   # hasOriginPlatform
    print(f"D0 GeographicRegion: {len(d0_geo)}")
    print(f"D0 OriginPlatform  : {len(d0_plat)}")

    # ── Controlled vocabulary individuals ─────────────────────────────────────
    vocab = set()
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        if not isinstance(ind, URIRef):
            continue
        types = set(g.objects(ind, RDF.type))
        if types & DATA_CLASSES:
            continue
        if types & GEO_PLAT_TYPES:
            # Keep only if D0-referenced or is a universal sentinel (Unknown / Worldwide)
            label = str(next(g.objects(ind, RDFS.label), ""))
            if ind in d0_geo or ind in d0_plat or label in ("Unknown", "Worldwide"):
                vocab.add(ind)
            continue
        vocab.add(ind)
    print(f"Vocab individuals  : {len(vocab)}")

    # ── Build D0 graph ────────────────────────────────────────────────────────
    all_included = d0 | ideas | variants | refs | vocab | d0_works

    # Non-D0 MemeConcepts — used to filter inverse links
    all_memes   = {s for s in g.subjects(RDF.type, MEME.MemeConcept)}
    non_d0_memes = all_memes - d0

    out = Graph()
    for prefix, ns in g_schema.namespaces():
        out.bind(prefix, ns, override=True)
    # Explicitly bind wd:, wdt:, frbrer: — lost when parsing from RDF/XML
    out.bind("wd",     WD,     override=True)
    out.bind("wdp",    WDP,    override=True)
    out.bind("frbrer", FRBRER, override=True)

    # Copy TBox from schema
    for triple in g_schema:
        out.add(triple)
    tbox_count = len(out)

    # schema.org subtype URIs used in populated file
    SCHEMA_SUBTYPES = {
        URIRef("https://schema.org/TVSeries"), URIRef("https://schema.org/Movie"),
        URIRef("https://schema.org/VideoGame"), URIRef("https://schema.org/ComicSeries"),
        URIRef("https://schema.org/MusicAlbum"), URIRef("https://schema.org/Book"),
    }

    # Copy ABox for every included individual, filtering cross-links to non-D0 memes
    for uri in all_included:
        if uri in stub_ideas:
            continue  # stubs are written separately below
        for s, p, o in g.triples((uri, None, None)):
            if isinstance(o, URIRef) and o in non_d0_memes:
                continue  # drop inverse link to non-D0 MemeConcept
            out.add((s, p, o))

    # Write stub MemeIdea individuals for D0 memes that had no conceptualizes link
    for idea_uri, info in stub_ideas.items():
        meme_uri = info["meme_uri"]
        out.add((idea_uri, RDF.type,   OWL.NamedIndividual))
        out.add((idea_uri, RDF.type,   MEME.MemeIdea))
        out.add((idea_uri, RDFS.label, Literal(info["label"])))
        if info["desc"]:
            out.add((idea_uri, MEME.conceptDescription, Literal(info["desc"], datatype=XSD.string)))
        out.add((meme_uri, MEME.conceptualizes,     idea_uri))
        out.add((idea_uri, MEME.isConceptualizedAs, meme_uri))

    # Annotate OriginWork individuals that could not be typed to a schema.org subclass
    for ow in d0_works:
        types = set(out.objects(ow, RDF.type))
        if not (types & SCHEMA_SUBTYPES):
            out.add((ow, RDFS.comment, Literal(
                "Typed as OriginWork (wd:Q386724) only. No schema.org media subclass "
                "could be automatically inferred from the KYM origin string.",
                lang="en")))

    print(f"\nTBox triples       : {tbox_count}")
    print(f"Total triples      : {len(out)}")

    out_owl.write_text(_inject_owl_xmlns(out.serialize(format="xml")), encoding="utf-8")
    print(f"Written            : {out_owl}")
    if out_ttl:
        out.serialize(destination=str(out_ttl), format="turtle")
        print(f"Written            : {out_ttl}")


def main():
    parser = argparse.ArgumentParser(description="Build D0-subset MEMO ontology")
    parser.add_argument("--populated", default="meme_ontology.owl")
    parser.add_argument("--schema",    default="meme_ontology_unpopulated.owl")
    parser.add_argument("--out-owl",   default="meme_ontology_d0.owl")
    parser.add_argument("--out-ttl",   default="meme_ontology_d0.ttl")
    args = parser.parse_args()
    build_d0(Path(args.populated), Path(args.schema),
             Path(args.out_owl), Path(args.out_ttl))


if __name__ == "__main__":
    main()
