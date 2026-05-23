# Local Widoco Documentation Generation

Since Widoco's web interface has CORS restrictions when working with local files, use this local setup instead.

## Option 1: Use pyLODE (Recommended - No CORS Issues)

pyLODE generates documentation directly without browser CORS restrictions.

```bash
# Install pyLODE
pip install pylode

# Generate documentation
pylode -i meme_ontology_unpopulated.ttl -o documentation.html

# View the generated documentation
# Open documentation.html in your browser
```

## Option 2: Use Java Widoco (Desktop Application)

Download and run Widoco as a standalone Java application:

1. Download from: https://github.com/dgarijo/Widoco/releases
2. Unzip the archive
3. Run with your ontology:
   ```bash
   java -jar widoco-VERSION-all.jar \
     -inputOntologyURI http://www.semanticweb.org/meme-ontology \
     -ontologyURI file:///path/to/meme_ontology_unpopulated.ttl \
     -outFolder ./docs
   ```

## Option 3: Simple HTTP Server + Web Widoco

If you still prefer the web version:

```bash
# Terminal 1: Start HTTP server
python -m http.server 8000

# Terminal 2: Open Widoco
# Visit: https://w3id.org/widoco/
# Enter URL: http://localhost:8000/meme_ontology_unpopulated.ttl
# Click: "Generate Documentation"
```

## Expected Output

Once documentation generates, you should see:
- Full class hierarchy with 144 classes
- 28 object properties with domain/range
- 19 data properties
- All relationships and inheritance chains
- Full FRBR layer structure

## Troubleshooting

If documentation still shows only metadata:
1. Check browser console (F12) for errors
2. Verify HTTP server is running (port 8000)
3. Test file access: http://localhost:8000/meme_ontology_unpopulated.ttl
4. Try pyLODE instead (bypasses all browser/CORS issues)

## pyLODE Advantages

- No CORS restrictions
- Faster generation
- Cleaner output
- Works offline
- No browser dependencies
