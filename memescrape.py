import os
import re
import sys
import time
import random
import json
import shutil
import argparse
import subprocess
from urllib.parse import urljoin
from datetime import datetime, timezone

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def save_sampling_cache(cache_file, data):
    try:
        tmp = cache_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, cache_file)
    except Exception as e:
        print(f"Warning: failed to save sampling cache {cache_file}: {e}")


def load_sampling_cache(cache_file):
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: failed to load sampling cache {cache_file}: {e}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw = f.read()
            header_match = re.search(r'"base_url":\s*"([^"]+)"', raw)
            total_match = re.search(r'"total_needed":\s*(\d+)', raw)
            maxp_match = re.search(r'"max_pages":\s*(\d+)', raw)
            nextp_match = re.search(r'"next_page":\s*(\d+)', raw)
            if not (header_match and total_match):
                return None
            sl_start = raw.find('"seen_links": [')
            sa_start = raw.find('"sampled_links": [')
            seen_links, sampled_links = [], []
            if sl_start != -1:
                end = sa_start if sa_start != -1 else len(raw)
                seen_body = raw[sl_start + len('"seen_links": ['):end]
                seen_links = list(dict.fromkeys(re.findall(r'"(https://[^"]+)"', seen_body)))
            if sa_start != -1:
                samp_body = raw[sa_start + len('"sampled_links": ['):]
                sampled_links = re.findall(r'"(https://[^"]+)"', samp_body)
            total_needed = int(total_match.group(1))
            if len(sampled_links) < total_needed and len(seen_links) > len(sampled_links):
                sampled_links = list(seen_links)
            recovered = {
                'base_url': header_match.group(1),
                'total_needed': total_needed,
                'max_pages': int(maxp_match.group(1)) if maxp_match else 5000,
                'next_page': int(nextp_match.group(1)) if nextp_match else 1,
                'unique_seen': len(seen_links),
                'no_new_page_streak': 0,
                'seen_links': seen_links,
                'sampled_links': sampled_links,
            }
            print(
                f"Recovered cache via regex: seen={len(seen_links)}, "
                f"sampled={len(sampled_links)}, next_page={recovered['next_page']}"
            )
            return recovered
        except Exception as e2:
            print(f"Cache recovery also failed: {e2}")
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)


def is_ui_or_icon_image(img_tag):
    alt = (img_tag.get('alt') or '').lower()
    src = (img_tag.get('src') or '').lower()
    classes = ' '.join(img_tag.get('class', []))
    ui_keywords = [
        'newsletter', 'facebook', 'instagram', 'tiktok', 'twitter', 'youtube',
        'discord', 'snapchat', 'avatar', 'icon', 'profile', 'logo', 'stamp',
        'user', 'svg', 'button', 'badge', 'submit', 'favorite', 'kym', 'deadpool',
    ]
    for keyword in ui_keywords:
        if keyword in alt or keyword in src or keyword in classes:
            return True
    if img_tag.has_attr('width') and img_tag.has_attr('height'):
        try:
            if int(img_tag['width']) <= 64 and int(img_tag['height']) <= 64:
                return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def make_session(proxy=None):
    """Return a curl_cffi session that impersonates Chrome124."""
    proxies = {'http': proxy, 'https': proxy} if proxy else None
    session = cf_requests.Session(
        impersonate='chrome124',
        proxies=proxies,
        headers={
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://knowyourmeme.com/',
        },
    )
    return session


def fetch_html(session, url, retries=4):
    """Fetch a page and return its HTML, or None on permanent failure."""
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=25, allow_redirects=True)
            if r.status_code == 403:
                # Check for hard IP ban vs Cloudflare rate limit
                if 'has been banned' in r.text:
                    print(
                        f"ERROR: Your IP has been banned by KYM. "
                        f"Connect via VPN/proxy and pass --proxy <url> to resume."
                    )
                    return None
                wait = 15 * (attempt + 1)
                print(f"403 on attempt {attempt+1} for {url} — backing off {wait}s")
                time.sleep(wait)
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"Rate limited (429) — backing off {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"Request attempt {attempt+1} failed for {url}: {e} — retrying in {wait}s")
            time.sleep(wait)
    print(f"All retries exhausted for {url}")
    return None


_CT_EXT = {
    'image/gif':  '.gif',
    'image/png':  '.png',
    'image/jpeg': '.jpg',
    'image/webp': '.webp',
    'image/bmp':  '.bmp',
}
_VALID_EXTS = {'.gif', '.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def _resolve_ext(image_url, content_type):
    """Return the correct file extension, preserving .gif so animations are not lost."""
    url_ext = os.path.splitext(image_url.split('?')[0])[1].lower()
    if url_ext in _VALID_EXTS:
        return url_ext
    ct_base = content_type.split(';')[0].strip()
    return _CT_EXT.get(ct_base, '.jpg')


def download_image(image_url, session, image_id, meme_folder):
    try:
        r = session.get(image_url, allow_redirects=True, timeout=20)
        r.raise_for_status()
        content_type = r.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            print(f"Skipped non-image content: {image_url}")
            return None
        os.makedirs(meme_folder, exist_ok=True)
        ext = _resolve_ext(image_url, content_type)
        title_for_filename = sanitize_filename(image_url.split('/')[-1].split('?')[0])
        image_filename = f"{image_id:04}_{title_for_filename}{ext}"
        image_path = os.path.join(meme_folder, image_filename)
        with open(image_path, 'wb') as fh:
            fh.write(r.content)
        print(f"Downloaded image: {image_url} -> {meme_folder}")
        return {
            'id': image_id,
            'title': title_for_filename,
            'image_filename': image_filename,
            'image_path': image_path,
            'image_url': image_url,
        }
    except Exception as e:
        print(f"Error downloading image {image_url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

def scrape_sidebar_metadata(soup):
    sidebar = None
    for a in soup.find_all('aside'):
        if (
            a.find('dl', id='entry_tags')
            or a.find('a', class_='entry-category-badge')
            or a.find(class_='entry_origin_link')
            or a.find('a', class_='entry-type-link')
        ):
            sidebar = a
            break
    if not sidebar:
        sidebar = soup.find('aside')
    if not sidebar:
        return {}

    meta = {}
    badge = sidebar.find('a', class_='entry-category-badge')
    if badge:
        meta['category'] = badge.get_text(strip=True)

    for dl in sidebar.find_all('dl'):
        for dt in dl.find_all('dt'):
            label = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling()
            while dd and dd.name != 'dd':
                dd = dd.find_next_sibling()
            if not dd:
                continue
            dd_text = dd.get_text(strip=True)
            dd_classes = dd.get('class') or []

            if 'type' in label and 'type' not in meta:
                type_links = dd.find_all('a', class_='entry-type-link')
                meta['type'] = [a.get_text(strip=True) for a in type_links] if type_links else dd_text

            if 'year' in label and 'year' not in meta:
                year_link = dd.find('a')
                meta['year'] = year_link.get_text(strip=True) if year_link else dd_text

            if 'origin' in label and 'origin' not in meta:
                if 'entry_origin_link' in dd_classes:
                    meta['origin'] = dd_text
                else:
                    origin_link = dd.find(class_='entry_origin_link')
                    meta['origin'] = origin_link.get_text(strip=True) if origin_link else dd_text

            if 'region' in label and 'region' not in meta:
                region_link = dd.find('a')
                meta['region'] = region_link.get_text(strip=True) if region_link else dd_text

            if 'tags' in label and 'tags' not in meta:
                meta['tags'] = [a.get_text(strip=True) for a in dd.find_all('a') if a.get_text(strip=True)]

    if 'tags' not in meta:
        tags_dl = sidebar.find('dl', id='entry_tags')
        if tags_dl:
            tags_dd = tags_dl.find('dd')
            if tags_dd:
                meta['tags'] = [a.get_text(strip=True) for a in tags_dd.find_all('a') if a.get_text(strip=True)]

    return meta


def parse_views_count(text):
    if not text:
        return None
    m = re.search(r'(\d[\d,\.]*)', text)
    if not m:
        return None
    raw = m.group(1)
    cleaned = raw.replace(',', '').replace('.', '')
    try:
        return int(cleaned)
    except Exception:
        return None


def scrape_page_extras(soup):
    extras = {
        'views': None,
        'videos': None,
        'photos': None,
        'comments': None,
        'description': '',
    }

    # Stats: div.cols > aside.stats.right > dl > dd[class] title attribute
    for css_class in ('views', 'videos', 'photos', 'comments'):
        for dd in soup.select(f'div.cols aside.stats.right dl dd.{css_class}'):
            val = parse_views_count(dd.get('title', '') or dd.get_text(' ', strip=True))
            if val is not None:
                extras[css_class] = val
                break

    # Description: first <p> after <h2 id="about">.
    about_h2 = soup.find('h2', id='about')
    if about_h2 and 'about' in about_h2.get_text(' ', strip=True).lower():
        p = about_h2.find_next('p')
        if p:
            extras['description'] = p.get_text(' ', strip=True)

    return extras


# ---------------------------------------------------------------------------
# Meme page scraping
# ---------------------------------------------------------------------------

_UI_GIF_PATTERNS = ('blank', 'deadpool', 'assets/', 'profiles/icons', 'tiny/', 'small/')


def _find_gif_in_page(soup, raw_html):
    """Return a GIF URL only if it is the meme's own entry icon (entries/icons/ path).

    Gallery submissions (photos/images/, photos/newsfeed/, etc.) are explicitly
    excluded — they belong to individual users, not the canonical meme image.
    """
    # DOM scan: entry icon GIFs embedded via img/source tags
    for tag in soup.find_all(['img', 'source']):
        for attr in ('src', 'data-src', 'data-original', 'data-lazy-src', 'data-url'):
            val = tag.get(attr, '')
            if not val or not val.lower().endswith('.gif'):
                continue
            lower = val.lower()
            if 'i.kym-cdn.com/entries/icons/' not in lower:
                continue
            if any(p in lower for p in _UI_GIF_PATTERNS):
                continue
            return val

    # Fallback: regex scan for entry-icon GIF URLs in script/JSON blobs
    for m in re.finditer(
        r'https://i\.kym-cdn\.com/entries/icons/[^\s"\'\\]+\.gif', raw_html
    ):
        val = m.group(0)
        if not any(p in val.lower() for p in _UI_GIF_PATTERNS):
            return val

    return None


def scrape_images(url, session, downloaded_images, image_count, meme_folder):
    print(f"Scraping meme page: {url}")
    html = fetch_html(session, url)
    if not html:
        return [], image_count, {}

    soup = BeautifulSoup(html, 'html.parser')
    main_image = None

    # 1. Prefer an animated GIF found anywhere in the page over the static og:image
    gif_candidate = _find_gif_in_page(soup, html)
    if gif_candidate:
        main_image = gif_candidate
        print(f"Found GIF in page content: {main_image}")

    # 2. Fall back to og:image / twitter:image (typically static)
    if not main_image:
        og = soup.find('meta', property='og:image')
        if og and og.get('content'):
            main_image = og['content']

    if not main_image:
        tw = soup.find('meta', property='twitter:image')
        if tw and tw.get('content'):
            main_image = tw['content']

    if not main_image:
        section = soup.find('section', class_='entry-section')
        if section:
            imgs = [i for i in section.find_all('img') if not is_ui_or_icon_image(i)]
            if imgs:
                main_image = imgs[0].get('src')

    if main_image:
        fname = os.path.basename(main_image)
        if 'deadpool' in fname or fname.startswith('kym') or fname == 'kym.png':
            print(f"Banned image (deadpool/kym): {main_image}")
            return [], image_count, {}

    if not main_image:
        print(f"No main meme image found for: {url}")
        return [], image_count, {}

    sidebar_meta = scrape_sidebar_metadata(soup)
    page_extras = scrape_page_extras(soup)
    sidebar_meta.update(page_extras)

    if main_image not in downloaded_images:
        print(f"Found main meme image: {main_image}")
        image_count += 1
        result = download_image(main_image, session, image_count, meme_folder)
        if result:
            downloaded_images.add(main_image)
            return (
                [{'id': image_count, 'title': os.path.basename(main_image),
                  'image_url': main_image, 'image_filename': result['image_filename'],
                  'image_path': result['image_path']}],
                image_count, sidebar_meta,
            )

    return [], image_count, sidebar_meta


# ---------------------------------------------------------------------------
# Category listing / link discovery
# ---------------------------------------------------------------------------

def save_debug_snapshot(soup, page, debug_dir):
    os.makedirs(debug_dir, exist_ok=True)
    try:
        with open(os.path.join(debug_dir, f"debug_category_page_{page}.html"), 'w', encoding='utf-8') as f:
            f.write(str(soup)[:200000])
    except Exception:
        pass


def extract_meme_links(soup):
    nodes = soup.select('a.item[href^="/memes/"]') or soup.select('a[href^="/memes/"]')
    links = []
    for node in nodes:
        href = node.get('href', '')
        if href.startswith('/memes/') and len(href.split('/')) > 2:
            links.append(urljoin('https://knowyourmeme.com', href))
    return links


def detect_max_category_page(soup):
    max_page = 1
    for a in soup.select('a[href*="/categories/meme?page="]'):
        m = re.search(r'[?&]page=(\d+)', a.get('href', ''))
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def scrape_memes_list(session, total_needed=5000, max_pages=None, debug_dir='debug', cache_file='sample_cache.json'):
    base_url = "https://knowyourmeme.com/categories/meme"
    stop_on_stale_pages = max_pages is None
    seen_links = set()
    sampled_links = []
    unique_seen = 0
    no_new_page_streak = 0
    start_page = 1

    cache = load_sampling_cache(cache_file)
    if cache and cache.get('base_url') == base_url and cache.get('total_needed') == total_needed:
        seen_links = set(cache.get('seen_links', []))
        sampled_links = cache.get('sampled_links', [])
        unique_seen = int(cache.get('unique_seen', len(seen_links)))
        no_new_page_streak = int(cache.get('no_new_page_streak', 0))
        start_page = int(cache.get('next_page', 1))
        if max_pages is None:
            max_pages = int(cache.get('max_pages', 5000))
        print(f"Resuming discovery cache from page {start_page} (unique_seen={unique_seen}, sample_size={len(sampled_links)})")

    if len(sampled_links) >= total_needed and unique_seen >= int(total_needed * 1.3):
        print(f"Cache already has {len(sampled_links)} sampled / {unique_seen} unique seen — skipping discovery.")
        random.shuffle(sampled_links)
        return sampled_links

    if max_pages is None:
        first_url = f"{base_url}?page=1"
        print(f"Fetching meme category page: {first_url}")
        first_html = fetch_html(session, first_url)
        if first_html:
            first_soup = BeautifulSoup(first_html, 'html.parser')
            save_debug_snapshot(first_soup, 1, debug_dir)
            detected = detect_max_category_page(first_soup)
            max_pages = detected if detected > 1 else 5000
            if start_page <= 1:
                for full_url in extract_meme_links(first_soup):
                    if full_url in seen_links:
                        continue
                    seen_links.add(full_url)
                    unique_seen += 1
                    if len(sampled_links) < total_needed:
                        sampled_links.append(full_url)
                    else:
                        idx = random.randrange(unique_seen)
                        if idx < total_needed:
                            sampled_links[idx] = full_url
                start_page = 2
        else:
            if start_page <= 1:
                print("Failed to fetch the first category page.")
                return []
            max_pages = 5000

    print(f"Sampling across {max_pages} category pages.")

    def checkpoint(next_page):
        save_sampling_cache(cache_file, {
            'base_url': base_url, 'total_needed': total_needed, 'max_pages': max_pages,
            'next_page': next_page, 'unique_seen': unique_seen,
            'no_new_page_streak': no_new_page_streak,
            'seen_links': list(seen_links), 'sampled_links': sampled_links,
        })

    def consider_links(page_links):
        nonlocal unique_seen
        for full_url in page_links:
            if full_url in seen_links:
                continue
            seen_links.add(full_url)
            unique_seen += 1
            if len(sampled_links) < total_needed:
                sampled_links.append(full_url)
            else:
                idx = random.randrange(unique_seen)
                if idx < total_needed:
                    sampled_links[idx] = full_url

    for page in range(start_page, max_pages + 1):
        url = f"{base_url}?page={page}"
        print(f"Fetching meme category page: {url}")
        html = fetch_html(session, url)
        if not html:
            print(f"Failed to fetch page {page}; skipping")
            if stop_on_stale_pages:
                no_new_page_streak += 1
                checkpoint(page + 1)
                if no_new_page_streak >= 5:
                    print("Stopping early after 5 failed/stale pages.")
                    break
            continue
        soup = BeautifulSoup(html, 'html.parser')
        save_debug_snapshot(soup, page, debug_dir)
        page_links = extract_meme_links(soup)
        print(f"Found {len(page_links)} meme entries on category page {page}")
        before = unique_seen
        consider_links(page_links)
        no_new_page_streak = 0 if unique_seen != before else no_new_page_streak + 1
        print(f"Unique meme links seen: {unique_seen}; sample size: {len(sampled_links)}")
        checkpoint(page + 1)
        if stop_on_stale_pages and no_new_page_streak >= 5:
            print("Stopping early — 5 pages without new links.")
            break
        if len(sampled_links) >= total_needed and no_new_page_streak >= 3:
            print(f"Reservoir full and no new links for {no_new_page_streak} pages — ending discovery.")
            break
        if len(sampled_links) >= total_needed and unique_seen >= int(total_needed * 1.3):
            print(f"Saw {unique_seen} unique links (>= 1.3x target) — ending discovery early.")
            break
        time.sleep(random.uniform(0.5, 1.5))

    random.shuffle(sampled_links)
    checkpoint(max_pages + 1)
    print(f"Total unique meme links seen: {unique_seen}")
    print(f"Returning random sample of {len(sampled_links)} meme links")
    return sampled_links


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def clear_existing_outputs(json_filename, images_dir, images_flat_dir, debug_dir):
    for folder in (images_dir, images_flat_dir, debug_dir):
        if os.path.isdir(folder):
            print(f"Removing folder: {folder}")
            shutil.rmtree(folder)
    if os.path.exists(json_filename):
        print(f"Removing file: {json_filename}")
        os.remove(json_filename)


def sync_extras_to_merged(metadata_list, merged_filename='metadata_merged.json'):
    if not os.path.exists(merged_filename):
        return
    try:
        with open(merged_filename, 'r', encoding='utf-8') as f:
            merged_data = json.load(f)
    except Exception as e:
        print(f"Warning: couldn't read {merged_filename}: {e}")
        return

    by_id = {m.get('id'): m for m in metadata_list}
    changed = 0
    for item in merged_data:
        src = by_id.get(item.get('id'))
        if not src:
            continue

        new_views    = src.get('views')
        new_videos   = src.get('videos')
        new_photos   = src.get('photos')
        new_comments = src.get('comments')
        new_about    = src.get('description') or ''

        for field, new_val in [
            ('views',       new_views),
            ('videos',      new_videos),
            ('photos',      new_photos),
            ('comments',    new_comments),
            ('description', new_about),
        ]:
            if item.get(field) != new_val:
                item[field] = new_val
                changed += 1

    if changed:
        tmp = merged_filename + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, merged_filename)
        print(f"Updated {merged_filename} with popularity/about fields.")


def main():
    parser = argparse.ArgumentParser(description='Scrape a random sample of Know Your Meme entries.')
    parser.add_argument('--total', type=int, default=5000)
    parser.add_argument('--max-pages', type=int, default=None)
    parser.add_argument('--metadata-file', default='metadata.json')
    parser.add_argument('--images-dir', default='images')
    parser.add_argument('--images-flat-dir', default='images_flat')
    parser.add_argument('--debug-dir', default='debug')
    parser.add_argument('--sample-cache', default='sample_cache.json')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--backfill-only', action='store_true',
                        help='Only backfill popularity/about fields for existing metadata entries, do not discover new memes.')
    parser.add_argument('--backfill-limit', type=int, default=None,
                        help='Optional max number of existing entries to backfill in this run.')
    parser.add_argument(
        '--proxy',
        default=None,
        help='HTTP/SOCKS proxy URL, e.g. http://user:pass@host:port or socks5://host:port',
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        print(f"Using random seed: {args.seed}")

    if args.fresh:
        clear_existing_outputs(args.metadata_file, args.images_dir, args.images_flat_dir, args.debug_dir)
        if os.path.exists(args.sample_cache):
            os.remove(args.sample_cache)

    total_memes = args.total
    downloaded_images = set()
    metadata_list = []
    image_count = 0
    json_filename = args.metadata_file

    def save_metadata_atomic(data):
        tmp = json_filename + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as jf:
                json.dump(data, jf, indent=2, ensure_ascii=False)
            os.replace(tmp, json_filename)
        except Exception as e:
            print(f"Failed to save metadata: {e}")

    if os.path.exists(json_filename):
        try:
            with open(json_filename, 'r', encoding='utf-8') as jf:
                metadata_list = json.load(jf)
                for m in metadata_list:
                    m.setdefault('image_path', '')
                    m.setdefault('scraped_at', '')
                    m.setdefault('views', None)
                    m.setdefault('videos', None)
                    m.setdefault('photos', None)
                    m.setdefault('comments', None)
                    m.setdefault('description', '')
                downloaded_images = set(m.get('image_url') for m in metadata_list if m.get('image_url'))
                if metadata_list:
                    image_count = max(m.get('id', 0) for m in metadata_list)
        except Exception as e:
            print(f"Warning: couldn't read existing metadata.json: {e}")
            metadata_list, downloaded_images, image_count = [], set(), 0

    os.makedirs(args.images_dir, exist_ok=True)
    os.makedirs(args.debug_dir, exist_ok=True)

    session = make_session(proxy=args.proxy)

    # Quick connectivity check before committing to a long run
    print("Checking connectivity to KYM...")
    test = fetch_html(session, 'https://knowyourmeme.com', retries=1)
    if not test:
        print(
            "\nCannot reach KYM. If your IP is banned, connect through a VPN or proxy:\n"
            "  python memescrape.py --proxy http://user:pass@host:port\n"
            "  python memescrape.py --proxy socks5://host:port\n"
        )
        return

    try:
        existing_meme_urls = set(m.get('meme_url') for m in metadata_list if m.get('meme_url'))

        # Backfill new metadata fields for existing entries.
        backfilled_count = 0
        for i, entry in enumerate(metadata_list):
            meme_url = entry.get('meme_url', '')
            if not meme_url:
                continue

            raw_popularity = entry.get('views')
            needs_popularity = raw_popularity in (None, '', 'null', 'None')
            if not needs_popularity and isinstance(raw_popularity, str):
                normalized = raw_popularity.replace(',', '').replace('.', '').strip()
                needs_popularity = not normalized.isdigit()
            needs_videos   = entry.get('videos')   is None
            needs_photos   = entry.get('photos')   is None
            needs_comments = entry.get('comments') is None
            needs_about = not entry.get('description')
            if not (needs_popularity or needs_videos or needs_photos or needs_comments or needs_about):
                continue

            if args.backfill_limit is not None and backfilled_count >= args.backfill_limit:
                print(f"Backfill limit reached ({args.backfill_limit}).")
                break

            print(f"Backfilling extras for existing entry {i+1}/{len(metadata_list)}: {meme_url}")
            html = fetch_html(session, meme_url)
            if not html:
                continue
            soup = BeautifulSoup(html, 'html.parser')
            extras = scrape_page_extras(soup)
            if needs_popularity:
                entry['views']    = extras.get('views')
            if needs_videos:
                entry['videos']   = extras.get('videos')
            if needs_photos:
                entry['photos']   = extras.get('photos')
            if needs_comments:
                entry['comments'] = extras.get('comments')
            if needs_about:
                entry['description'] = extras.get('description') or ''
            save_metadata_atomic(metadata_list)
            backfilled_count += 1
            if backfilled_count % 100 == 0:
                sync_extras_to_merged(metadata_list)
                subprocess.run([sys.executable, 'generate_viz.py'], check=False)
                print(f'[auto] Regenerated meme_data.json after {backfilled_count} backfilled entries.')
            time.sleep(random.uniform(1.0, 2.0))

        if args.backfill_only:
            print(f"Backfill-only mode complete. Updated {backfilled_count} entries.")
            save_metadata_atomic(metadata_list)
            sync_extras_to_merged(metadata_list)
            return

        sampled_links = scrape_memes_list(
            session,
            total_needed=total_memes,
            max_pages=args.max_pages,
            debug_dir=args.debug_dir,
            cache_file=args.sample_cache,
        )
        pending_links = [u for u in sampled_links if u not in existing_meme_urls]
        if len(pending_links) < total_memes - len(metadata_list):
            print(f"Warning: only {len(existing_meme_urls) + len(pending_links)} unique links available.")

        for meme_url in pending_links:
            if len(metadata_list) >= total_memes:
                break
            meme_title = meme_url.split('/')[-1]
            meme_folder = os.path.join(args.images_dir, sanitize_filename(meme_title))
            os.makedirs(meme_folder, exist_ok=True)

            images, image_count, sidebar_meta = scrape_images(
                meme_url, session, downloaded_images, image_count, meme_folder,
            )

            if images:
                for image in images:
                    if not any(m.get('image_filename') == image['image_filename'] for m in metadata_list):
                        metadata_list.append({
                            'id': image['id'],
                            'title': image['title'],
                            'image_filename': image['image_filename'],
                            'image_path': image.get('image_path', ''),
                            'image_url': image.get('image_url', ''),
                            'meme_url': meme_url,
                            'type': sidebar_meta.get('type') or [],
                            'year': sidebar_meta.get('year') or '',
                            'origin': sidebar_meta.get('origin') or '',
                            'region': sidebar_meta.get('region') or '',
                            'tags': sidebar_meta.get('tags') or [],
                            'views':    sidebar_meta.get('views'),
                            'videos':   sidebar_meta.get('videos'),
                            'photos':   sidebar_meta.get('photos'),
                            'comments': sidebar_meta.get('comments'),
                            'description': sidebar_meta.get('description') or '',
                            'scraped_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        })
                        save_metadata_atomic(metadata_list)
                    downloaded_images.add(image.get('image_url', image['image_filename']))
            else:
                if os.path.exists(meme_folder) and not os.listdir(meme_folder):
                    os.rmdir(meme_folder)

            time.sleep(random.uniform(2.0, 5.0))

    finally:
        session.close()

    save_metadata_atomic(metadata_list)
    sync_extras_to_merged(metadata_list)
    print(f"Finished. {len(metadata_list)} entries saved to {json_filename}")


if __name__ == "__main__":
    main()
