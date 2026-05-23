#!/usr/bin/env node
/**
 * SPARQL Query Validation Script
 * Tests all SPARQL examples against the populated ontology
 */

const fs = require('fs');
const path = require('path');
const N3 = require('n3');
const { QueryEngine } = require('@comunica/query-sparql');

const QUERIES = {
  'count-format': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>

SELECT ?format (COUNT(DISTINCT ?m) AS ?count)
WHERE {
  ?m a memo:MemeConcept ;
     memo:hasFormat ?fmt .
  BIND(LOCALNAME(?fmt) AS ?format)
}
GROUP BY ?format
ORDER BY DESC(?count)
`,

  'count-period': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>

SELECT ?period (COUNT(DISTINCT ?m) AS ?count)
WHERE {
  ?m a memo:MemeConcept ;
     memo:hasTimePeriod ?tp .
  BIND(LOCALNAME(?tp) AS ?period)
}
GROUP BY ?period
ORDER BY ?period
`,

  'animated': `
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
`,

  'public-figures': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?score
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?label ;
     memo:clipPublicFigureScore ?score .
}
ORDER BY DESC(?score)
LIMIT 25
`,

  'twitter': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?format ?period
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?label ;
     memo:hasOriginWork memo:TwitterX ;
     memo:hasFormat ?fmt ;
     memo:hasTimePeriod ?tp .
  BIND(LOCALNAME(?fmt) AS ?format)
  BIND(LOCALNAME(?tp) AS ?period)
}
ORDER BY ?label
LIMIT 50
`,

  'all-classes': `
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>

SELECT ?class ?label
WHERE {
  ?class a owl:Class .
  OPTIONAL { ?class rdfs:label ?label }
}
ORDER BY ?class
`,

  'no-text': `
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
`,

  'cultural-refs': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?memeName ?refLabel ?refClass
WHERE {
  ?m a memo:MemeConcept ;
     rdfs:label ?memeName ;
     memo:hasReference ?ref .
  ?ref rdfs:label ?refLabel .
  OPTIONAL {
    ?ref a ?refType .
    BIND(LOCALNAME(?refType) AS ?refClass)
  }
}
ORDER BY ?memeName ?refLabel
LIMIT 100
`,

  'meme-ideas': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?ideaLabel ?memeName ?desc
WHERE {
  ?idea a memo:MemeIdea ;
        rdfs:label ?ideaLabel ;
        memo:conceptDescription ?desc ;
        memo:isConceptualizedAs ?m .
  ?m rdfs:label ?memeName .
}
ORDER BY ?memeName
`,

  'transformations': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?variantLabel ?memeName ?dimension ?extent ?note
WHERE {
  ?v a memo:VariantInstance ;
     rdfs:label ?variantLabel ;
     memo:isVariantOf ?m ;
     memo:hasTransformationDimension ?dim ;
     memo:hasTransformationExtent ?ext .
  ?m rdfs:label ?memeName .
  BIND(LOCALNAME(?dim) AS ?dimension)
  BIND(LOCALNAME(?ext) AS ?extent)
  OPTIONAL { ?v memo:transformationNote ?note }
}
ORDER BY ?memeName ?variantLabel
`,

  'wikidata-regions': `
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
`,

  'platform-stats': `
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
`,

  'color-and-animation': `
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
`,

  'transformation-analysis': `
PREFIX memo: <http://www.semanticweb.org/meme-ontology#>

SELECT ?dimension ?extent (COUNT(DISTINCT ?v) AS ?count)
WHERE {
  ?v a memo:VariantInstance ;
     memo:hasTransformationDimension ?dim ;
     memo:hasTransformationExtent ?ext .
  BIND(LOCALNAME(?dim) AS ?dimension)
  BIND(LOCALNAME(?ext) AS ?extent)
}
GROUP BY ?dimension ?extent
ORDER BY DESC(?count)
`
};

async function testQueries() {
  console.log('🔄 Loading ontology...\n');

  const ttlPath = path.join(__dirname, 'meme_ontology.ttl');
  const ttlContent = fs.readFileSync(ttlPath, 'utf-8');

  const store = new N3.Store();
  const parser = new N3.Parser({ baseIRI: 'http://www.semanticweb.org/meme-ontology#' });
  const quads = parser.parse(ttlContent);

  for (const quad of quads) {
    store.addQuad(quad);
  }

  console.log(`✓ Loaded ${store.size.toLocaleString()} triples\n`);

  const engine = new QueryEngine();
  const results = {};
  let passed = 0;
  let failed = 0;

  for (const [name, query] of Object.entries(QUERIES)) {
    try {
      const t0 = Date.now();
      const bindings = await engine.queryBindings(query, { sources: [store] });
      const rows = await bindings.toArray();
      const elapsed = ((Date.now() - t0) / 1000).toFixed(2);

      results[name] = { status: '✓', rows: rows.length, time: elapsed };
      passed++;
      console.log(`✓ ${name.padEnd(30)} ${rows.length} rows in ${elapsed}s`);
    } catch (err) {
      results[name] = { status: '✗', error: err.message };
      failed++;
      console.log(`✗ ${name.padEnd(30)} ERROR: ${err.message}`);
    }
  }

  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`✓ Passed: ${passed}/${Object.keys(QUERIES).length}`);
  console.log(`✗ Failed: ${failed}/${Object.keys(QUERIES).length}`);

  if (failed > 0) {
    console.log(`\nFailed queries:`);
    for (const [name, result] of Object.entries(results)) {
      if (result.status === '✗') {
        console.log(`  - ${name}: ${result.error}`);
      }
    }
    process.exit(1);
  }
}

testQueries().catch(console.error);
