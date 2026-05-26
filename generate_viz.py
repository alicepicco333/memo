"""Generate meme_data.json for the visualization page."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


with open("metadata_merged.json", encoding="utf-8") as f:
    data = json.load(f)


def extract_slug(image_filename):
    if not image_filename:
        return ""
    stem = Path(image_filename).stem
    return re.sub(r"^\d{4}_", "", stem)


def normalize_period(raw_period):
    mapping = {
        "Pre2010": "Pre2010",
        "Period2010to2015": "2010-2015",
        "Period2016to2020": "2016-2020",
        "Period2021toPresent": "2021-present",
        "Unknown": "Unknown",
    }
    if not raw_period:
        return "Unknown"
    return mapping.get(str(raw_period), str(raw_period))


PERIOD_ORDER = ["Pre2010", "2010-2015", "2016-2020", "2021-present"]
IMAGE_TYPE_ORDER = ["Photograph", "Cartoon", "Drawing", "Illustration", "Painting"]


# Meme lookup used by all pages.
memes = {}
for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    if not slug:
        continue
    candidate = {
        "id": entry.get("id"),
        "slug": slug,
        "title": entry.get("title", slug),
        "imageFilename": entry.get("image_filename", ""),
        "memeUrl": entry.get("meme_url", ""),
        "year": entry.get("year"),
        "tags": entry.get("tags") or [],
        "hasImageType": entry.get("hasImageType"),
        "clipImageTypeScore": entry.get("clipImageTypeScore"),
        "hasTextPresence": entry.get("hasTextPresence"),
        "clipTextScore": entry.get("clipTextScore"),
        "hasColorMode": entry.get("hasColorMode"),
        "hasSubjectMatter": entry.get("hasSubjectMatter"),
        "clipPublicFigureScore": entry.get("clipPublicFigureScore"),
        "ocrSnippet": entry.get("ocrSnippet"),
        "hasFormat": entry.get("hasFormat") or [],
        "hasOriginPlatform": entry.get("hasOriginPlatform"),
        "hasOriginWork": entry.get("hasOriginWork"),
        "hasRegion": entry.get("hasRegion"),
        "hasTimePeriod": entry.get("hasTimePeriod"),
        "hasFileFormat": entry.get("hasFileFormat"),
        "hasAnimationStatus": entry.get("hasAnimationStatus"),
        "popularityViews": entry.get("views"),
        "description": entry.get("description", ""),
    }

    # Some slugs can appear more than once; keep non-empty fields when possible.
    existing = memes.get(slug)
    if existing:
        if existing.get("popularityViews") not in (None, "") and candidate.get("popularityViews") in (None, ""):
            candidate["popularityViews"] = existing.get("popularityViews")
        if (existing.get("description") or "").strip() and not (candidate.get("description") or "").strip():
            candidate["description"] = existing.get("description")

    memes[slug] = candidate


# 1) Temporal distribution of format (existing timeline kept).
year_counts = Counter()
year_format = defaultdict(Counter)
year_to_memes = defaultdict(list)
time_fmt_to_memes = defaultdict(list)

for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    try:
        year_value = int(str(entry.get("year", "")).strip())
    except (ValueError, TypeError):
        continue

    if year_value < 1995 or year_value > 2026:
        continue

    year_counts[year_value] += 1
    if slug:
        year_to_memes[str(year_value)].append(slug)

    for meme_format in (entry.get("hasFormat") or []):
        if meme_format and meme_format != "Unknown":
            year_format[year_value][meme_format] += 1

format_total = Counter()
for format_counter in year_format.values():
    format_total.update(format_counter)

# Keep the chart readable by showing the most common formats.
top_time_formats = {fmt for fmt, _ in format_total.most_common(14)}

for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    if not slug:
        continue
    for meme_format in (entry.get("hasFormat") or []):
        if meme_format in top_time_formats:
            time_fmt_to_memes[meme_format].append(slug)

time_nodes = [
    {"id": str(year_value), "count": count, "group": "year", "year": year_value}
    for year_value, count in sorted(year_counts.items())
]
for meme_format in top_time_formats:
    time_nodes.append({"id": meme_format, "count": format_total[meme_format], "group": "format"})

time_links = [
    {"source": str(year_value), "target": meme_format, "value": count}
    for year_value, format_counter in year_format.items()
    for meme_format, count in format_counter.items()
    if meme_format in top_time_formats and count >= 2
]
time_node_to_memes = {**year_to_memes, **time_fmt_to_memes}


# 2) Popularity x format (avg views + entry count).
format_all_count = Counter()
format_views_sum = Counter()
format_views_count = Counter()
format_to_memes = defaultdict(list)

for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    formats = [fmt for fmt in (entry.get("hasFormat") or []) if fmt and fmt != "Unknown"]
    if not formats:
        continue

    views = entry.get("views")
    try:
        views = int(views)
    except (TypeError, ValueError):
        views = None

    for meme_format in formats:
        format_all_count[meme_format] += 1
        if slug:
            format_to_memes[meme_format].append(slug)
        if views is not None and views >= 0:
            format_views_sum[meme_format] += views
            format_views_count[meme_format] += 1

format_popularity_points = []
for meme_format, total_entries in format_all_count.items():
    if format_views_count[meme_format] == 0:
        avg_views = 0
    else:
        avg_views = format_views_sum[meme_format] / format_views_count[meme_format]

    format_popularity_points.append({
        "format": meme_format,
        "avgViews": avg_views,
        "entries": total_entries,
        "entriesWithViews": format_views_count[meme_format],
    })

format_popularity_points.sort(key=lambda row: row["avgViews"], reverse=True)


# 3) CLIP image type x format heatmap.
heat_counts = defaultdict(Counter)
heat_combo_to_memes = defaultdict(list)
heat_row_to_memes = defaultdict(list)
heat_col_to_memes = defaultdict(list)
all_formats_in_heat = Counter()

for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    image_type = entry.get("hasImageType")
    if image_type not in IMAGE_TYPE_ORDER:
        continue

    formats = [fmt for fmt in (entry.get("hasFormat") or []) if fmt and fmt != "Unknown"]
    if not formats:
        continue

    if slug:
        heat_row_to_memes[image_type].append(slug)

    for meme_format in formats:
        heat_counts[image_type][meme_format] += 1
        all_formats_in_heat[meme_format] += 1
        if slug:
            heat_col_to_memes[meme_format].append(slug)
            heat_combo_to_memes[f"{image_type}||{meme_format}"] .append(slug)

# Keep most represented formats to avoid an unreadable matrix.
heat_formats = [fmt for fmt, _ in all_formats_in_heat.most_common(16)]

heat_cells = []
for image_type in IMAGE_TYPE_ORDER:
    for meme_format in heat_formats:
        count = heat_counts[image_type][meme_format]
        if count > 0:
            heat_cells.append({
                "imageType": image_type,
                "format": meme_format,
                "count": count,
            })


# 4) Platform origin x time period stacked distribution.
MODERN_PLATFORMS = {"TikTok", "Instagram", "Snapchat", "Twitch", "Discord"}
platform_period_counts = defaultdict(Counter)
period_platform_totals = defaultdict(Counter)
period_totals = Counter()
platform_totals = Counter()
period_to_memes = defaultdict(list)
platform_to_memes = defaultdict(list)
platform_period_to_memes = defaultdict(list)

for entry in data:
    slug = extract_slug(entry.get("image_filename", ""))
    period = normalize_period(entry.get("hasTimePeriod"))
    platform = entry.get("hasOriginPlatform") or "Unknown"

    if period not in PERIOD_ORDER:
        continue
    if platform in ("Unknown", "None", None):
        continue
    if platform in MODERN_PLATFORMS and period == "Pre2010":
        continue

    platform_period_counts[platform][period] += 1
    period_platform_totals[period][platform] += 1
    period_totals[period] += 1
    platform_totals[platform] += 1

    if slug:
        period_to_memes[period].append(slug)
        platform_to_memes[platform].append(slug)
        platform_period_to_memes[f"{period}||{platform}"] .append(slug)

# Use top platforms overall and fold others into "Other" for readable stacks.
TOP_PLATFORM_LIMIT = 8
top_platforms = [p for p, _ in platform_totals.most_common(TOP_PLATFORM_LIMIT)]

period_rows = []
for period in PERIOD_ORDER:
    total = period_totals[period]
    if total == 0:
        continue

    row = {"period": period, "total": total, "segments": []}
    other_count = 0

    for platform in top_platforms:
        c = period_platform_totals[period][platform]
        if c <= 0:
            continue
        row["segments"].append({
            "platform": platform,
            "count": c,
            "ratio": c / total,
        })

    for platform, c in period_platform_totals[period].items():
        if platform not in top_platforms:
            other_count += c

    if other_count > 0:
        row["segments"].append({
            "platform": "Other",
            "count": other_count,
            "ratio": other_count / total,
        })

    # stable order: top platforms first, then Other
    order = {name: idx for idx, name in enumerate(top_platforms)}
    order["Other"] = len(top_platforms)
    row["segments"].sort(key=lambda s: order.get(s["platform"], 999))

    period_rows.append(row)


all_node_to_memes = {}
all_node_to_memes.update(time_node_to_memes)
all_node_to_memes.update({k: v for k, v in format_to_memes.items()})
all_node_to_memes.update({k: v for k, v in heat_row_to_memes.items()})
all_node_to_memes.update({k: v for k, v in heat_col_to_memes.items()})
all_node_to_memes.update({k: v for k, v in period_to_memes.items()})
all_node_to_memes.update({k: v for k, v in platform_to_memes.items()})

# combo maps are namespaced so keys do not collide.
combo_to_memes = {
    f"heat::{k}": v for k, v in heat_combo_to_memes.items()
}
combo_to_memes.update({
    f"period_platform::{k}": v for k, v in platform_period_to_memes.items()
})


year_min = min(year_counts) if year_counts else 1995
year_max = max(year_counts) if year_counts else 2026

output = {
    "meta": {
        "yearMin": year_min,
        "yearMax": year_max,
        "totalMemes": len(memes),
    },
    "memes": memes,
    "graphs": {
        "time": {
            "nodes": time_nodes,
            "links": time_links,
            "nodeToMemes": dict(time_node_to_memes),
        },
        "popularity": {
            "points": format_popularity_points,
            "nodeToMemes": dict(format_to_memes),
        },
        "heatmap": {
            "imageTypes": IMAGE_TYPE_ORDER,
            "formats": heat_formats,
            "cells": heat_cells,
            "rowToMemes": dict(heat_row_to_memes),
            "colToMemes": dict(heat_col_to_memes),
            "comboToMemes": dict(heat_combo_to_memes),
        },
        "platformTime": {
            "periods": period_rows,
            "topPlatforms": top_platforms,
            "nodeToMemes": {
                **dict(period_to_memes),
                **dict(platform_to_memes),
            },
            "comboToMemes": dict(platform_period_to_memes),
        },
        "allNodeToMemes": all_node_to_memes,
        "allComboToMemes": combo_to_memes,
    },
}

with open("meme_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

size_kb = Path("meme_data.json").stat().st_size // 1024
print(f"meme_data.json written ({size_kb} KB)")
print(f"Memes: {len(memes)}")
print(f"Time graph: {len(time_nodes)} nodes / {len(time_links)} links")
print(f"Popularity points: {len(format_popularity_points)}")
print(f"Heatmap cells: {len(heat_cells)}")
print(f"Platform-time periods: {len(period_rows)}")
