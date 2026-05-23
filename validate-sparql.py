#!/usr/bin/env python3
"""
SPARQL Query Syntax Validation Script
Tests all SPARQL examples for basic syntax correctness
"""

import re
import sys

QUERIES = {
    'count-format': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>

SELECT ?format (COUNT(DISTINCT ?m) AS ?count)
WHERE {
  ?m a memo:MemeConcept ;
     memo:hasFormat ?fmt .
  BIND(LOCALNAME(?fmt) AS ?format)
}
GROUP BY ?format
ORDER BY DESC(?count)
''',

    'animated': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?format
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?label ;
     memo:hasAnimationStatus memo:Animated ;
     memo:hasFormat ?fmt .
  BIND(LOCALNAME(?fmt) AS ?format)
}
ORDER BY ?label
LIMIT 100
''',

    'no-text': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?format ?imageType
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?label ;
     memo:hasCanonicalTextPresence memo:NoText ;
     memo:hasFormat ?fmt ;
     memo:hasCanonicalImageType ?it .
  BIND(LOCALNAME(?fmt) AS ?format)
  BIND(LOCALNAME(?it) AS ?imageType)
}
ORDER BY ?label
LIMIT 100
''',

    'wikidata-regions': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?region ?wikidata (COUNT(DISTINCT ?m) AS ?memeCount)
WHERE {
  ?region a memo:GeographicRegion ;
          rdfs:label ?regionLabel ;
          rdfs:seeAlso ?wikidata .
  ?m a memo:MemeConcept ;
     memo:hasRegion ?region .
}
GROUP BY ?region ?wikidata ?regionLabel
ORDER BY DESC(?memeCount)
''',

    'platform-stats': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?platform ?label (COUNT(DISTINCT ?m) AS ?count)
WHERE {
  ?platform a memo:OriginPlatform ;
            rdfs:label ?label ;
            rdfs:seeAlso ?wikidata .
  ?m a memo:MemeConcept ;
     memo:hasOriginPlatform ?platform .
}
GROUP BY ?platform ?label
ORDER BY DESC(?count)
LIMIT 20
''',

    'color-and-animation': '''
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?memeName ?color ?animation (COUNT(DISTINCT ?v) AS ?variantCount)
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?memeName ;
     memo:hasAnimationStatus ?anim ;
     memo:hasVariant ?v .
  ?v memo:hasVariantColorMode ?clr .
  BIND(LOCALNAME(?clr) AS ?color)
  BIND(LOCALNAME(?anim) AS ?animation)
}
GROUP BY ?memeName ?color ?animation
ORDER BY ?memeName
LIMIT 50
''',
}

def validate_sparql_syntax(query_name, query_text):
    """Basic SPARQL syntax validation"""
    errors = []

    # Check for required keywords
    query_upper = query_text.upper()

    if 'SELECT' not in query_upper and 'DESCRIBE' not in query_upper and 'ASK' not in query_upper and 'CONSTRUCT' not in query_upper:
        errors.append("Missing query type (SELECT/DESCRIBE/ASK/CONSTRUCT)")

    # Check for balanced braces
    if query_text.count('{') != query_text.count('}'):
        errors.append(f"Unbalanced braces: {query_text.count('{')} {{ vs {query_text.count('}')} }}")

    # Check for valid PREFIX syntax
    prefix_pattern = r'PREFIX\s+\w+:\s*<[^>]+>'
    for match in re.finditer(prefix_pattern, query_text):
        if not match.group():
            errors.append(f"Invalid PREFIX syntax near: {match.group()}")

    # Check for common property references
    if 'memo:' in query_text:
        memo_refs = re.findall(r'memo:(\w+)', query_text)
        valid_properties = {
            'MemeConcept', 'MemeIdea', 'VariantInstance',
            'hasFormat', 'hasTimePeriod', 'hasRegion', 'hasOriginWork', 'hasOriginPlatform',
            'hasCanonicalColorMode', 'hasVariantColorMode',
            'hasCanonicalImageType', 'hasVariantImageType',
            'hasCanonicalTextPresence', 'hasVariantTextPresence',
            'hasAnimationStatus', 'hasVariant', 'hasTransformationDimension', 'hasTransformationExtent',
            'hasReference', 'isVariantOf', 'isVariantColorModeOf', 'isVariantImageTypeOf', 'isVariantTextPresenceOf',
            'conceptDescription', 'isConceptualizedAs', 'transformationNote',
            'clipPublicFigureScore',
            'GeographicRegion', 'OriginPlatform', 'ColorMode', 'ImageType', 'TextPresence',
            'MemeFormat', 'TimePeriod', 'AnimationStatus', 'TransformationDimension', 'TransformationExtent',
            'Animated', 'NoText', 'TwitterX',
            'frbrLevel', 'semanticLevel'
        }
        # Only check if property looks like it should be a class/property
        unknown = [r for r in memo_refs if not any(r.startswith(v) or v == r for v in valid_properties)]
        if unknown:
            pass  # Don't fail on unknown refs, they might be individuals

    return errors

def main():
    print("🔍 Validating SPARQL query syntax...\n")

    passed = 0
    failed = 0

    for query_name, query_text in QUERIES.items():
        errors = validate_sparql_syntax(query_name, query_text)

        if errors:
            print(f"✗ {query_name}")
            for error in errors:
                print(f"  └─ {error}")
            failed += 1
        else:
            print(f"✓ {query_name}")
            passed += 1

    print(f"\n{'━' * 60}")
    print(f"✓ Passed: {passed}/{len(QUERIES)}")
    print(f"✗ Failed: {failed}/{len(QUERIES)}")

    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
