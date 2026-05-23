# Using Widoco with Meme Ontology

Widoco requires the ontology file to be accessible via HTTP, not local file. Here are the proper ways to use it:

## Option 1: Use WebVOWL (Recommended for Quick Viewing)

1. Go to https://service.tib.eu/webvowl/
2. Click "Ontology URL"
3. Enter: `https://thememeontology.netlify.app/meme_ontology_unpopulated.owl`
4. Click Load

## Option 2: Local HTTP Server (For Development)

```bash
# Option A: Python 3
python -m http.server 8000

# Option B: Node.js (if you have http-server installed)
npx http-server

# Option C: Any other HTTP server
```

Then access: `http://localhost:8000/meme_ontology_unpopulated.ttl`

And use Widoco: https://w3id.org/widoco/

## Option 3: Online Widoco with Deployed URL

Use: https://w3id.org/widoco/ with the deployed URL from Netlify

## Troubleshooting

If Widoco still shows only metadata:

1. **Clear browser cache** - Widoco caches ontology files
2. **Check Console** - Open browser DevTools (F12) → Console for errors
3. **Verify namespace** - The ontology IRI must match element namespaces
4. **Check file size** - The unpopulated TTL should be ~37KB, OWL ~0.5MB

Current file status:
- `meme_ontology_unpopulated.ttl`: 1,189 triples (69 classes, 56 properties)
- `meme_ontology_unpopulated.owl`: 1,189 triples (same content, XML format)
- `meme_ontology.ttl`: 81,556 triples (populated with 6,440 individuals)
- `meme_ontology.owl`: 81,556 triples (populated, XML format)
