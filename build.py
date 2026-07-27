#!/usr/bin/env python3
"""Static site generator for the Roger Paulino website.

Reads JSON content from content/ and renders it through the HTML templates in
templates/ into static files at the repo root. Standard library only.

Templating (intentionally tiny):
  {{ key }}                         -> escaped value from the context ("" if missing)
  <!-- IF:flag -->...<!-- ENDIF:flag -->      kept only when context[flag] is truthy
  <!-- LOOP:name -->...<!-- ENDLOOP:name -->  repeated for each item in context[name]
Inside a LOOP, dict items expose their fields; string items expose {{ value }}.
Links and asset paths are built relative to each page's depth via {{ root }}, so
the site works from file:// locally and under any GitHub Pages base path.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"

TYPE_LABELS = {
    "solo": "Solo exhibition",
    "group": "Group exhibition",
    "duo": "Duo exhibition",
}

IF_RE = re.compile(r"<!--\s*IF:(\w+)\s*-->(.*?)<!--\s*ENDIF:\1\s*-->", re.S)
LOOP_RE = re.compile(r"<!--\s*LOOP:(\w+)\s*-->(.*?)<!--\s*ENDLOOP:\1\s*-->", re.S)
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
RAW_KEYS = {"content"}  # substituted without HTML-escaping


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render(tpl, ctx):
    """Expand loops, then conditionals, then variables."""
    def loop_sub(m):
        name, body = m.group(1), m.group(2)
        items = ctx.get(name) or []
        parts = []
        for item in items:
            merged = {**ctx, **item} if isinstance(item, dict) else {**ctx, "value": item}
            parts.append(render(body, merged))
        return "".join(parts)

    def if_sub(m):
        flag, body = m.group(1), m.group(2)
        return body if ctx.get(flag) else ""

    def var_sub(m):
        key = m.group(1)
        if key not in ctx:
            return ""
        val = ctx[key]
        if isinstance(val, (list, dict)):
            return ""
        return str(val) if key in RAW_KEYS else html.escape(str(val), quote=True)

    tpl = LOOP_RE.sub(loop_sub, tpl)
    while True:  # loop until stable so nested conditionals resolve
        new = IF_RE.sub(if_sub, tpl)
        if new == tpl:
            break
        tpl = new
    tpl = VAR_RE.sub(var_sub, tpl)
    return tpl


# --- asset path helpers -----------------------------------------------------

def thumb_for(src):
    folder, _, name = src.rpartition("/")
    prefix = f"{folder}/" if folder else ""
    return f"{prefix}thumb-{name}"


def poster_for(src):
    folder, _, name = src.rpartition("/")
    prefix = f"{folder}/" if folder else ""
    stem = name.rsplit(".", 1)[0]
    return f"{prefix}{stem}-poster.jpg"


def sort_key(show):
    """Sort by dateStart descending. Accepts YYYY, YYYY-MM, YYYY-MM-DD."""
    parts = str(show.get("dateStart", "0000")).split("-")
    parts += ["01"] * (3 - len(parts))
    return "-".join(p.zfill(2) if i else p.zfill(4) for i, p in enumerate(parts))


# --- content loading --------------------------------------------------------

SITE = load_json(CONTENT / "site.json")
YEAR = str(date.today().year)


def load_exhibitions():
    shows = []
    for path in sorted((CONTENT / "exhibitions").glob("*.json")):
        if path.name.startswith("_"):
            continue
        shows.append(load_json(path))
    shows.sort(key=sort_key, reverse=True)
    return shows


def base_ctx(root, page_title, description=""):
    ctx = {
        "root": root,
        "page_title": page_title,
        "meta_description": description or SITE.get("metaDescription", ""),
        "site_name": SITE["name"],
        "site_email": SITE["email"],
        "site_instagram": SITE["instagram"],
        "site_year": YEAR,
    }
    for key, value in SITE.get("ui", {}).items():
        ctx[f"ui_{key}"] = value
    return ctx


def autodiscover_media(slug):
    """Fallback media when a show JSON leaves `media` empty: every image in
    assets/<slug>/ (first becomes hero), then any videos."""
    folder = ROOT / "assets" / slug
    media = []
    if not folder.is_dir():
        return media
    for name in sorted(p.name for p in folder.glob("*.jpg")):
        if name.startswith("thumb-") or name.endswith("-poster.jpg"):
            continue
        media.append({"type": "image", "src": f"assets/{slug}/{name}", "hero": not media})
    for p in sorted(folder.glob("*.mp4")):
        media.append({"type": "video", "src": f"assets/{slug}/{p.name}"})
    return media


def resolve_media(show):
    return show.get("media") or autodiscover_media(show["slug"])


def images_of(media):
    return [m for m in media if m.get("type", "image") == "image"]


def hero_of(media):
    imgs = images_of(media)
    if not imgs:
        return None
    for m in imgs:
        if m.get("hero"):
            return m
    return imgs[0]


def show_url(show):
    return f"exhibitions/{show['slug']}/index.html"


def place_label(show):
    return ", ".join(x for x in [show.get("venue", ""), show.get("city", "")] if x)


def card_ctx(show):
    media = resolve_media(show)
    hero = hero_of(media)
    thumb = thumb_for(hero["src"]) if hero else ""
    return {
        "title": show["title"],
        "place": place_label(show),
        "dateLabel": show.get("dateLabel", ""),
        "typeLabel": TYPE_LABELS.get(show.get("type", ""), ""),
        "url": show_url(show),
        "thumb": thumb,
        "noThumb": not thumb,
    }


# --- template rendering ------------------------------------------------------

def render_page(body_tpl_name, ctx):
    body = render((TEMPLATES / body_tpl_name).read_text(encoding="utf-8"), ctx)
    ctx["content"] = body
    return render((TEMPLATES / "base.html").read_text(encoding="utf-8"), ctx)


def write(rel_path, content):
    out = ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return rel_path


# --- page builders ----------------------------------------------------------

def build_home(shows):
    home = load_json(CONTENT / "home.json")
    ctx = base_ctx("", SITE["name"], SITE.get("metaDescription", ""))
    ctx["intro"] = home.get("intro", [])
    ctx["hero"] = home.get("hero", "")
    ctx["heroAlt"] = home.get("heroAlt", "")
    ctx["recent"] = [card_ctx(s) for s in shows[: home.get("recentCount", 3)]]
    return write("index.html", render_page("home.html", ctx))


def build_exhibitions(shows):
    ctx = base_ctx("../", f"Exhibitions - {SITE['name']}")
    ctx["shows"] = [card_ctx(s) for s in shows]
    return write("exhibitions/index.html", render_page("exhibitions-index.html", ctx))


def build_show(show):
    root = "../../"
    ctx = base_ctx(root, f"{show['title']} - {SITE['name']}",
                   " ".join(show.get("statement", []))[:180])
    media = resolve_media(show)
    imgs = images_of(media)
    hero = hero_of(media)
    gallery = []
    for m in imgs:
        if hero and m is hero:
            continue
        gallery.append({"src": m["src"], "thumb": thumb_for(m["src"]), "alt": m.get("alt") or show["title"]})
    videos = []
    for m in media:
        if m.get("type") == "video":
            videos.append({"src": m["src"], "poster": m.get("poster") or poster_for(m["src"])})
    curator = show.get("curatorText") or {}
    co = show.get("coArtists", [])

    ctx.update({
        "title": show["title"],
        "place": place_label(show),
        "dateLabel": show.get("dateLabel", ""),
        "typeLabel": TYPE_LABELS.get(show.get("type", ""), ""),
        "coArtistsLabel": "with " + ", ".join(co) if co else "",
        "heroSrc": hero["src"] if hero else "",
        "heroAlt": (hero.get("alt") or show["title"]) if hero else "",
        "noHero": not hero,
        "statement": show.get("statement", []),
        "gallery": gallery,
        "videos": videos,
        "works": show.get("works", []),
        "curatorBy": curator.get("by", ""),
        "curatorParagraphs": curator.get("paragraphs", []),
        "links": show.get("links", []),
    })
    return write(f"exhibitions/{show['slug']}/index.html", render_page("exhibition.html", ctx))


def build_about():
    about = load_json(CONTENT / "about.json")
    ctx = base_ctx("../", f"About - {SITE['name']}")
    ctx["bio"] = about.get("bio", [])
    ctx["exhibitions"] = about.get("selectedExhibitions", [])
    ctx["education"] = about.get("education", [])
    ctx["awards"] = about.get("awards", [])
    ctx["collections"] = about.get("collections", [])
    ctx["press"] = about.get("press", [])
    return write("about/index.html", render_page("about.html", ctx))


def build():
    shows = load_exhibitions()
    written = [
        build_home(shows),
        build_exhibitions(shows),
        *[build_show(s) for s in shows],
        build_about(),
    ]
    for path in written:
        print(f"wrote {path}")
    print(f"\n{len(written)} pages, {len(shows)} exhibitions.")


if __name__ == "__main__":
    build()
