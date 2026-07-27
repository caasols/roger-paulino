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
`content` and `jsonld` are raw (not HTML-escaped) so page bodies and JSON-LD
script blocks pass through verbatim.
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
RAW_KEYS = {"content", "jsonld"}  # substituted without HTML-escaping


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
    """Sort key for `dateStart`, newest-first when used with reverse=True.

    Accepts YYYY, YYYY-MM, YYYY-MM-DD, and a YYYY-YYYY range (which sorts by its
    start year). Unknown month/day default to 0, so a partial date sorts just
    below a fully dated show in the same period. Returns an (int, int, int)
    tuple, so comparison never depends on string zero-padding.
    """
    parts = str(show.get("dateStart", "0")).split("-")
    year = int(parts[0]) if parts[0].isdigit() else 0
    month = day = 0
    # a 4-digit second token is a range end-year, not a month, so ignore it
    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) <= 2:
        month = int(parts[1])
        if len(parts) >= 3 and parts[2].isdigit():
            day = int(parts[2])
    return (year, month, day)


# --- content + site-wide values ---------------------------------------------

SITE = load_json(CONTENT / "site.json")
YEAR = str(date.today().year)
SITE_URL = SITE.get("siteUrl", "").rstrip("/")
DEFAULT_OG_IMAGE = f"{SITE_URL}/assets/og/og-default.jpg"


def abs_url(path=""):
    """Absolute URL for a site-root-relative path ('' -> site root)."""
    return f"{SITE_URL}/{path}" if path else f"{SITE_URL}/"


def truncate(text, limit=160):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def jsonld_script(obj):
    # replace </ so a value can never close the <script> tag early
    data = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>'


def person_ld():
    p = SITE.get("person", {})
    obj = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE["name"],
        "url": abs_url(),
        "jobTitle": SITE.get("role", "Visual artist"),
        "description": SITE.get("metaDescription", ""),
        "sameAs": [SITE["instagram"]] + p.get("sameAs", []),
    }
    if p.get("birthDate"):
        obj["birthDate"] = p["birthDate"]
    if p.get("birthPlace"):
        obj["birthPlace"] = {"@type": "Place", "name": p["birthPlace"]}
    if p.get("homeLocation"):
        obj["homeLocation"] = {"@type": "Place", "name": p["homeLocation"]}
        obj["workLocation"] = {"@type": "Place", "name": p["homeLocation"]}
    if p.get("knowsAbout"):
        obj["knowsAbout"] = p["knowsAbout"]
    if p.get("alumniOf"):
        obj["alumniOf"] = [{"@type": "EducationalOrganization", "name": a} for a in p["alumniOf"]]
    if p.get("award"):
        obj["award"] = p["award"]
    return obj


def exhibition_ld(show, image):
    place = {"@type": "Place", "name": show.get("venue") or show.get("city") or SITE["name"]}
    if show.get("city"):
        place["address"] = show["city"]
    obj = {
        "@context": "https://schema.org",
        "@type": "ExhibitionEvent",
        "name": show["title"],
        "url": abs_url(f"exhibitions/{show['slug']}/"),
        "performer": {"@type": "Person", "name": SITE["name"]},
        "location": place,
    }
    if show.get("dateStart"):
        obj["startDate"] = show["dateStart"]
    if show.get("dateEnd"):
        obj["endDate"] = show["dateEnd"]
    if image:
        obj["image"] = image
    return obj


def show_description(show):
    type_label = TYPE_LABELS.get(show.get("type", ""), "exhibition").lower()
    tail = [f"a {type_label}"]
    place = place_label(show)
    if place:
        tail.append(f"at {place}")
    if show.get("dateLabel"):
        tail.append(f"({show['dateLabel']})")
    return truncate(f"{show['title']}, " + " ".join(tail) + ".")


def load_exhibitions():
    shows = []
    for path in sorted((CONTENT / "exhibitions").glob("*.json")):
        if path.name.startswith("_"):
            continue
        shows.append(load_json(path))
    shows.sort(key=sort_key, reverse=True)
    return shows


def base_ctx(root, path, page_title, description="", og_image=None,
             og_type="website", jsonld=""):
    canonical = abs_url(path)
    ctx = {
        "root": root,
        "canonical": canonical,
        "og_url": canonical,
        "og_type": og_type,
        "og_image": og_image or DEFAULT_OG_IMAGE,
        "jsonld": jsonld,
        "page_title": page_title,
        "meta_description": description or SITE.get("metaDescription", ""),
        "site_name": SITE["name"],
        "site_email": SITE["email"],
        "site_instagram": SITE["instagram"],
        "site_url": SITE_URL,
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
    ctx = base_ctx("", "", f"{SITE['name']}, Visual Artist (Printmaking and Painting)",
                   SITE.get("metaDescription", ""),
                   jsonld=jsonld_script(person_ld()))
    ctx["intro"] = home.get("intro", [])
    ctx["hero"] = home.get("hero", "")
    ctx["heroAlt"] = home.get("heroAlt", "")
    ctx["recent"] = [card_ctx(s) for s in shows[: home.get("recentCount", 3)]]
    return write("index.html", render_page("home.html", ctx))


def build_exhibitions(shows):
    ctx = base_ctx("../", "exhibitions/", f"Exhibitions - {SITE['name']}",
                   f"Selected solo and group exhibitions by the visual artist {SITE['name']}.")
    ctx["shows"] = [card_ctx(s) for s in shows]
    return write("exhibitions/index.html", render_page("exhibitions-index.html", ctx))


def build_show(show):
    media = resolve_media(show)
    imgs = images_of(media)
    hero = hero_of(media)
    hero_abs = abs_url(hero["src"]) if hero else None
    ctx = base_ctx("../../", f"exhibitions/{show['slug']}/",
                   f"{show['title']} - {SITE['name']}",
                   show_description(show),
                   og_image=hero_abs, og_type="article",
                   jsonld=jsonld_script(exhibition_ld(show, hero_abs)))
    gallery = []
    n = 0
    for m in imgs:
        if hero and m is hero:
            continue
        n += 1
        gallery.append({"src": m["src"], "thumb": thumb_for(m["src"]),
                        "alt": m.get("alt") or f"{show['title']}, image {n}"})
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
    bio = about.get("bio", [])
    desc = about.get("metaDescription") or (truncate(bio[0]) if bio else SITE.get("metaDescription", ""))
    ctx = base_ctx("../", "about/", f"About - {SITE['name']}", desc,
                   jsonld=jsonld_script(person_ld()))
    ctx["bio"] = bio
    ctx["exhibitions"] = about.get("selectedExhibitions", [])
    ctx["education"] = about.get("education", [])
    ctx["awards"] = about.get("awards", [])
    ctx["collections"] = about.get("collections", [])
    ctx["press"] = about.get("press", [])
    return write("about/index.html", render_page("about.html", ctx))


# --- SEO / discovery artifacts ----------------------------------------------

def build_sitemap(shows):
    urls = [abs_url(), abs_url("exhibitions/"), abs_url("about/")]
    urls += [abs_url(f"exhibitions/{s['slug']}/") for s in shows]
    items = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{items}\n</urlset>\n")


def build_robots():
    return f"User-agent: *\nAllow: /\n\nSitemap: {abs_url('sitemap.xml')}\n"


def build_llms(shows):
    about = load_json(CONTENT / "about.json")
    bio = about.get("bio", [])
    lines = [f"# {SITE['name']}", "", SITE.get("metaDescription", ""), ""]
    if bio:
        lines += ["## About", "", *bio, ""]
    lines += ["## Exhibitions"]
    for s in shows:
        url = abs_url(f"exhibitions/{s['slug']}/")
        meta = ", ".join(x for x in [place_label(s), s.get("dateLabel", "")] if x)
        lines.append(f"- {s['title']} ({meta}): {url}")
    lines += [
        "",
        "## Pages",
        f"- Home: {abs_url()}",
        f"- Exhibitions: {abs_url('exhibitions/')}",
        f"- About and CV: {abs_url('about/')}",
        "",
        "## Contact",
        f"- Email: {SITE['email']}",
        f"- Instagram: {SITE['instagram']}",
    ]
    return "\n".join(lines) + "\n"


def build():
    shows = load_exhibitions()
    written = [
        build_home(shows),
        build_exhibitions(shows),
        *[build_show(s) for s in shows],
        build_about(),
        write("sitemap.xml", build_sitemap(shows)),
        write("robots.txt", build_robots()),
        write("llms.txt", build_llms(shows)),
    ]
    for path in written:
        print(f"wrote {path}")
    print(f"\n{len(written)} files, {len(shows)} exhibitions.")


if __name__ == "__main__":
    build()
