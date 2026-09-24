"""Build thesis.html — the full dissertation as an indexed, searchable web page.

Usage:
    python build_thesis.py [path/to/Towards_An_Ontology_Of_Memes.pdf]

Default PDF location is the parent folder of this repo (Desktop/DHDK/memo/).
Structure is recovered from the PDF's typography:
    18 pt            -> chapter (h2)
    16/14 pt + N.N   -> section (h3), N.N.N -> subsection (h4)
    14 pt unnumbered -> subsection (h4)
    Courier New      -> code
Figures are rendered to thesis_assets/fig-N.jpg; the printed page number of
every page is kept as a citable marker (#p-N).
"""
import html
import os
import re
import sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PDF = os.path.join(HERE, '..', 'Towards_An_Ontology_Of_Memes.pdf')
OUT_HTML = os.path.join(HERE, 'thesis.html')
ASSET_DIR = os.path.join(HERE, 'thesis_assets')
TEMPLATE = os.path.join(HERE, 'thesis_template.html')

SKIP_PAGES = {1, 2, 5, 6}          # cover, blank, printed index (rebuilt from headings)
SENTENCE_END = re.compile(r'[.:;!?”"\')\]]$')
URL = re.compile(r'(https?://[^\s<]+[^\s<.,;:)\]])')


def slugify(text):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return s[:60] or 'section'


def is_code(span):
    return 'Courier' in span['font']


def is_italic(span):
    return bool(span['flags'] & 2) or 'Italic' in span['font']


def span_html(spans):
    """Render a run of spans with <em>/<code>, merging adjacent same-style runs."""
    out, cur_style, buf = [], None, []

    def flush():
        if not buf:
            return
        text = html.escape(''.join(buf))
        if cur_style == 'code':
            out.append(f'<code>{text}</code>')
        elif cur_style == 'em':
            out.append(f'<em>{text}</em>')
        else:
            out.append(text)

    for s in spans:
        style = 'code' if is_code(s) else ('em' if is_italic(s) else None)
        if style != cur_style:
            flush()
            buf, cur_style = [], style
        buf.append(s['text'])
    flush()
    return ''.join(out)


def block_lines(block):
    """Return [(line_text, spans)] for a text block."""
    lines = []
    for l in block['lines']:
        spans = [s for s in l['spans'] if s['text']]
        if spans:
            lines.append((''.join(s['text'] for s in spans), spans))
    return lines


def join_lines(lines):
    """Join PDF lines into one run of spans, repairing spaces at line breaks."""
    spans = []
    for i, (text, ls) in enumerate(lines):
        if i and spans:
            prev = spans[-1]['text']
            if not prev.endswith((' ', '-', '/', '–', '—')):
                spans.append({**ls[0], 'text': ' '})
        spans.extend(ls)
    return spans


def heading_level(text, size):
    """Numbering decides the level; font size only matters for unnumbered headings."""
    t = text.strip()
    if re.match(r'^\d+\.\d+\.\d+\s', t):
        return 4
    if re.match(r'^\d+\.\d+\s', t):
        return 3
    if size >= 17.5:
        return 2
    if size >= 13.5 and len(t) < 90:
        return 4
    return None


def build(pdf_path):
    doc = pymupdf.open(pdf_path)
    os.makedirs(ASSET_DIR, exist_ok=True)
    items = []      # dicts: kind = h / p / code / li / fig / cap / page
    fig_n = 0
    section = None  # current top-level heading text, for class hints

    for pno, page in enumerate(doc, start=1):
        if pno in SKIP_PAGES:
            continue
        # Flatten the page into lines (and images) in reading order
        rows = []
        for b in page.get_text('dict')['blocks']:
            if b['type'] == 1:
                rows.append({'img': True, 'bbox': b['bbox']})
                continue
            for l in b['lines']:
                spans = [sp for sp in l['spans'] if sp['text']]
                text = ''.join(sp['text'] for sp in spans).strip()
                if text:
                    rows.append({'img': False, 'bbox': l['bbox'], 'spans': spans, 'text': text,
                                 'size': max(sp['size'] for sp in spans)})
        rows.sort(key=lambda r: (round(r['bbox'][1], 1), r['bbox'][0]))

        # Bullet glyphs are separate one-character lines; attach each to the text on its baseline
        def is_glyph(r):
            return not r['img'] and len(r['text']) <= 1 and r['spans'][0]['font'].startswith(('Arial', 'Symbol', 'MS Gothic')) \
                and not r['text'].isalnum()
        for g in [r for r in rows if is_glyph(r)]:
            gy = (g['bbox'][1] + g['bbox'][3]) / 2
            target = min((r for r in rows if not r['img'] and r is not g and not is_glyph(r)
                          and r['bbox'][0] > g['bbox'][0] and abs((r['bbox'][1] + r['bbox'][3]) / 2 - gy) < 4),
                         key=lambda r: r['bbox'][0], default=None)
            if target:
                target['bullet'] = True
                rows.remove(g)

        # Printed page number: a lone 1-3 digit line in the top or bottom margin
        ph = page.rect.height
        for r in rows:
            if not r['img'] and re.fullmatch(r'\d{1,3}', r['text']) and (r['bbox'][1] < 80 or r['bbox'][3] > ph - 80):
                items.append({'kind': 'page', 'n': r['text']})
                rows.remove(r)
                break

        page_marked = True
        cur = None      # paragraph/list/code/caption being accumulated
        prev_bottom = None

        def close():
            nonlocal cur
            if cur:
                items.append(cur)
            cur = None

        for r in rows:
            if r['img']:
                close()
                fig_n += 1
                pix = page.get_pixmap(clip=pymupdf.Rect(r['bbox']), dpi=150)
                name = f'fig-{fig_n}.jpg'
                pix.save(os.path.join(ASSET_DIR, name), jpg_quality=82)
                items.append({'kind': 'fig', 'src': f'thesis_assets/{name}', 'w': pix.width, 'h': pix.height})
                prev_bottom = r['bbox'][3]
                continue
            text, spans, size = r['text'], r['spans'], r['size']
            gap = (r['bbox'][1] - prev_bottom) if prev_bottom is not None else 99
            prev_bottom = r['bbox'][3]

            if not page_marked and re.fullmatch(r'\d{1,3}', text) and r['bbox'][1] < 80:
                close()
                items.append({'kind': 'page', 'n': text})
                page_marked = True
                prev_bottom = None
                continue

            lvl = heading_level(text, size) if size >= 13.5 else None
            if lvl:
                close()
                if items and items[-1]['kind'] == 'h' and gap < 4 and items[-1]['level'] == lvl:
                    items[-1]['text'] += ' ' + text      # wrapped heading
                else:
                    if lvl == 2:
                        section = text
                    items.append({'kind': 'h', 'level': lvl, 'text': re.sub(r'\s+', ' ', text)})
                continue

            code = all(is_code(sp) for sp in spans if sp['text'].strip())
            bullet = r.get('bullet') or bool(re.match(r'^[•●▪]', text)) or                 (spans[0]['font'].startswith('Arial') and len(spans[0]['text'].strip()) <= 1)
            caption = bool(re.match(r'^(Fig\.|Figure)\s*\d+', text))
            new_block = gap > 4
            # Bibliography entries are single-spaced inside (gap < 0) with a small space between entries
            if section and section.lower() in ('bibliography', 'sitography') and gap > 1:
                new_block = True

            if code:
                if cur and cur['kind'] == 'code' and gap < 12:
                    cur['lines'].append(text)
                else:
                    close()
                    cur = {'kind': 'code', 'lines': [text]}
                continue
            if caption:
                close()
                cur = {'kind': 'cap', 'lines': [(text, spans)]}
                continue
            if bullet:
                close()
                sp = [x for x in spans if not (x['font'].startswith('Arial') and len(x['text'].strip()) <= 1)]
                if sp:
                    sp[0] = {**sp[0], 'text': re.sub(r'^[•●▪]\s*', '', sp[0]['text']).lstrip()}
                cur = {'kind': 'li', 'lines': [(text, sp)]}
                continue
            if cur and cur['kind'] in ('p', 'li', 'cap') and not new_block:
                cur['lines'].append((text, spans))
                continue
            close()
            cur = {'kind': 'p', 'lines': [(text, spans)], 'section': section, 'page': pno}
        close()

    # Finalise accumulated blocks
    for it in items:
        if it['kind'] in ('p', 'li', 'cap'):
            it['spans'] = join_lines(it['lines'])
            it['raw'] = ' '.join(t for t, _ in it['lines'])
            if it['kind'] != 'p':
                it['html'] = span_html(it['spans'])
            it.setdefault('page', None)
        elif it['kind'] == 'code':
            it['text'] = '\n'.join(it['lines'])

    # Merge paragraphs split across a page break
    merged = []
    for it in items:
        if it['kind'] == 'p' and merged:
            j = len(merged) - 1
            while j >= 0 and merged[j]['kind'] == 'page':
                j -= 1
            prev = merged[j] if j >= 0 else None
            if prev and prev['kind'] == 'p' and prev['page'] != it['page'] \
               and not SENTENCE_END.search(prev['raw']) and re.match(r'^[a-z(\[“"\d,;]', it['raw']):
                sep = [] if prev['raw'].endswith('-') else [{**it['spans'][0], 'text': ' '}]
                prev['spans'] = prev['spans'] + sep + it['spans']
                prev['raw'] = prev['raw'] + ' ' + it['raw']
                # keep the page marker where it was, but move it after the joined paragraph
                if j != len(merged) - 1:
                    markers = merged[j + 1:]
                    del merged[j + 1:]
                    merged.extend(markers)
                    prev['after_markers'] = True
                continue
        merged.append(it)

    # Render
    body, toc, used_ids = [], [], set()
    in_list = False
    open_sections = 0
    words = 0
    bib_mode = False

    def uid(base):
        s, n = base, 2
        while s in used_ids:
            s = f'{base}-{n}'
            n += 1
        used_ids.add(s)
        return s

    for idx, it in enumerate(merged):
        k = it['kind']
        if k != 'li' and in_list:
            body.append('</ul>')
            in_list = False
        if k == 'page':
            body.append(f'<span class="pg" id="p-{it["n"]}" aria-label="page {it["n"]}">{it["n"]}</span>')
        elif k == 'h':
            lvl, text = it['level'], it['text']
            hid = uid(slugify(text))
            if lvl == 2:
                if open_sections:
                    body.append('</section>')
                body.append(f'<section class="th-chapter" aria-labelledby="{hid}">')
                open_sections = 1
                bib_mode = text.lower() in ('bibliography', 'sitography')
            body.append(f'<h{lvl} id="{hid}"><a class="th-anchor" href="#{hid}" aria-hidden="true">#</a>{html.escape(text)}</h{lvl}>')
            toc.append((lvl, text, hid))
        elif k == 'p':
            h = span_html(it['spans'])
            if bib_mode:
                h = URL.sub(r'<a href="\1" target="_blank" rel="noopener">\1</a>', h)
            words += len(it['raw'].split())
            body.append(f'<p{" class=\"th-bib\"" if bib_mode else ""}>{h}</p>')
        elif k == 'li':
            if not in_list:
                body.append('<ul>')
                in_list = True
            words += len(it['raw'].split())
            body.append(f'<li>{it["html"]}</li>')
        elif k == 'code':
            if '\n' in it['text']:
                body.append(f'<pre><code>{html.escape(it["text"])}</code></pre>')
            else:  # a single code line introduces the paragraph that defines it
                body.append(f'<p class="th-term"><code>{html.escape(it["text"])}</code></p>')
        elif k == 'fig':
            cap = ''
            if idx + 1 < len(merged) and merged[idx + 1]['kind'] == 'cap':
                cap = merged[idx + 1]['html']
                merged[idx + 1]['kind'] = 'used'
            alt = re.sub(r'<[^>]+>', '', cap) or 'Figure'
            body.append(f'<figure><img src="{it["src"]}" width="{it["w"]}" height="{it["h"]}" '
                        f'loading="lazy" alt="{html.escape(alt, quote=True)}">'
                        + (f'<figcaption>{cap}</figcaption>' if cap else '') + '</figure>')
        elif k == 'cap':
            body.append(f'<p class="th-caption">{it["html"]}</p>')
    if in_list:
        body.append('</ul>')
    if open_sections:
        body.append('</section>')

    # TOC markup
    toc_html = ['<ol class="th-toc-list">']
    open_sub = False
    for lvl, text, hid in toc:
        if lvl == 2:
            if open_sub:
                toc_html.append('</ol></li>')
                open_sub = False
            else:
                if len(toc_html) > 1:
                    toc_html.append('</li>')
            toc_html.append(f'<li class="toc-ch"><a href="#{hid}">{html.escape(text)}</a>')
        else:
            if not open_sub:
                toc_html.append('<ol>')
                open_sub = True
            toc_html.append(f'<li class="toc-l{lvl}"><a href="#{hid}">{html.escape(text)}</a></li>')
    toc_html.append('</ol></li>' if open_sub else '</li>')
    toc_html.append('</ol>')

    template = open(TEMPLATE, encoding='utf-8').read()
    out = (template
           .replace('{{TOC}}', '\n'.join(toc_html))
           .replace('{{BODY}}', '\n'.join(body))
           .replace('{{WORDS}}', f'{words:,}')
           .replace('{{MINUTES}}', str(round(words / 230)))
           .replace('{{PAGES}}', str(doc.page_count))
           .replace('{{FIGS}}', str(fig_n)))
    open(OUT_HTML, 'w', encoding='utf-8', newline='\n').write(out)
    print(f'thesis.html: {len(toc)} headings, {words:,} words, {fig_n} figures')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF)
