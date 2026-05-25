"""
extract_d0.py
-------------
Build meme_ontology_d0.owl / .ttl — the D0 subset ontology.

Contents:
  TBox  — all class and property declarations from meme_ontology_unpopulated.owl
  ABox  — 50 D0 MemeConcept individuals (with all their properties)
          43 linked MemeIdea individuals
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
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef

MEME   = Namespace("https://purl.org/memo#")
WD     = Namespace("http://www.wikidata.org/entity/")
WDT    = Namespace("http://www.wikidata.org/prop/direct/")
SCHEMA = Namespace("http://schema.org/")

# Classes that mark data-derived (non-schema) ABox individuals
DATA_CLASSES = {
    MEME.MemeConcept,
    MEME.MemeIdea,
    MEME.VariantInstance,
    WD.Q96622155,      # CulturalReference
    WD.Q386724,        # OriginWork
    SCHEMA.TVSeries, SCHEMA.Movie, SCHEMA.VideoGame,
    SCHEMA.ComicSeries, SCHEMA.MusicAlbum, SCHEMA.Book,
}
for _sub in ["PoliticalEvent", "MediaProperty", "WebCulture",
             "PublicFigure", "HistoricalEvent", "SocialPhenomenon"]:
    DATA_CLASSES.add(MEME[_sub])

GEO_PLAT_TYPES = {WD.Q82794, WD.Q3220391}


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
    for s in g.subjects(WDT.P527, None):          # hasVariant
        if (s, RDF.type, MEME.MemeConcept) in g:
            d0.add(s)
    for s in g.subjects(MEME.hasReference, None):
        if (s, RDF.type, MEME.MemeConcept) in g:
            d0.add(s)
    print(f"D0 MemeConcepts    : {len(d0)}")

    # ── Collect linked ABox individuals ───────────────────────────────────────
    ideas    = {o for d in d0 for o in g.objects(d, MEME.conceptualizes)}
    variants = {o for d in d0 for o in g.objects(d, WDT.P527)}
    refs     = {o for d in d0 for o in g.objects(d, MEME.hasReference)}
    print(f"MemeIdea           : {len(ideas)}")
    print(f"VariantInstance    : {len(variants)}")
    print(f"CulturalReference  : {len(refs)}")

    # ── D0-referenced region and platform individuals only ────────────────────
    d0_geo  = {o for d in d0 for o in g.objects(d, WDT.P495)}   # hasRegion
    d0_plat = {o for d in d0 for o in g.objects(d, WDT.P123)}   # hasOriginPlatform
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
    all_included = d0 | ideas | variants | refs | vocab

    # Non-D0 MemeConcepts — used to filter inverse links
    all_memes   = {s for s in g.subjects(RDF.type, MEME.MemeConcept)}
    non_d0_memes = all_memes - d0

    out = Graph()
    for prefix, ns in g_schema.namespaces():
        out.bind(prefix, ns, override=True)

    # Copy TBox from schema
    for triple in g_schema:
        out.add(triple)
    tbox_count = len(out)

    # Copy ABox for every included individual, filtering cross-links to non-D0 memes
    for uri in all_included:
        for s, p, o in g.triples((uri, None, None)):
            if isinstance(o, URIRef) and o in non_d0_memes:
                continue  # drop inverse link to non-D0 MemeConcept
            out.add((s, p, o))

    print(f"\nTBox triples       : {tbox_count}")
    print(f"Total triples      : {len(out)}")

    out.serialize(destination=str(out_owl), format="xml")
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
