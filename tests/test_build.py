"""Unit tests for build.py (the static site generator).

Run from the repo root:  python3 -m unittest discover -s tests
Standard library only, matching build.py.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402


class TestRender(unittest.TestCase):
    def test_var_is_html_escaped(self):
        self.assertEqual(build.render("{{ x }}", {"x": "a & b <c> \"q\""}),
                         "a &amp; b &lt;c&gt; &quot;q&quot;")

    def test_missing_var_becomes_empty(self):
        self.assertEqual(build.render("[{{ nope }}]", {}), "[]")

    def test_content_key_is_raw(self):
        # `content` is the injected page body and must not be escaped
        self.assertEqual(build.render("{{ content }}", {"content": "<p>hi</p>"}), "<p>hi</p>")

    def test_list_and_dict_vars_render_empty(self):
        self.assertEqual(build.render("{{ xs }}", {"xs": [1, 2]}), "")

    def test_if_truthy_and_falsy(self):
        self.assertEqual(build.render("<!-- IF:a -->Y<!-- ENDIF:a -->", {"a": 1}), "Y")
        self.assertEqual(build.render("<!-- IF:a -->Y<!-- ENDIF:a -->", {"a": 0}), "")
        self.assertEqual(build.render("<!-- IF:a -->Y<!-- ENDIF:a -->", {}), "")

    def test_if_tests_collection_truthiness(self):
        # the refactor relies on empty list = falsy, non-empty = truthy
        self.assertEqual(build.render("<!-- IF:xs -->has<!-- ENDIF:xs -->", {"xs": ["a"]}), "has")
        self.assertEqual(build.render("<!-- IF:xs -->has<!-- ENDIF:xs -->", {"xs": []}), "")

    def test_nested_if(self):
        tpl = "<!-- IF:a -->o<!-- IF:b -->i<!-- ENDIF:b --><!-- ENDIF:a -->"
        self.assertEqual(build.render(tpl, {"a": 1, "b": 1}), "oi")
        self.assertEqual(build.render(tpl, {"a": 1, "b": 0}), "o")
        self.assertEqual(build.render(tpl, {"a": 0, "b": 1}), "")

    def test_loop_over_dicts(self):
        tpl = "<!-- LOOP:xs -->[{{ n }}]<!-- ENDLOOP:xs -->"
        self.assertEqual(build.render(tpl, {"xs": [{"n": "1"}, {"n": "2"}]}), "[1][2]")

    def test_loop_over_strings_exposes_value(self):
        tpl = "<!-- LOOP:xs -->{{ value }};<!-- ENDLOOP:xs -->"
        self.assertEqual(build.render(tpl, {"xs": ["a", "b"]}), "a;b;")

    def test_loop_empty(self):
        self.assertEqual(build.render("<!-- LOOP:xs -->x<!-- ENDLOOP:xs -->", {"xs": []}), "")

    def test_substituted_value_is_not_reprocessed(self):
        # a value that itself looks like a placeholder must not be re-substituted
        out = build.render("{{ x }}", {"x": "{{ y }}", "y": "SECRET"})
        self.assertNotIn("SECRET", out)


class TestYearCollisionRegression(unittest.TestCase):
    def test_footer_year_does_not_leak_into_loop_items(self):
        # base_ctx exposes the footer year as site_year (not year), so a loop
        # item without its own `year` must render blank, not the site year.
        self.assertNotIn("year", build.base_ctx("", "", "t"))
        self.assertIn("site_year", build.base_ctx("", "", "t"))
        tpl = "<!-- LOOP:works -->{{ title }}<!-- IF:year -->({{ year }})<!-- ENDIF:year -->|<!-- ENDLOOP:works -->"
        ctx = {"site_year": "2026", "works": [{"title": "A"}, {"title": "B", "year": "2025"}]}
        out = build.render(tpl, ctx)
        self.assertEqual(out, "A|B(2025)|")
        self.assertNotIn("2026", out)


class TestSortKey(unittest.TestCase):
    def test_orders_newest_first(self):
        shows = [
            {"dateStart": "2023-06-01"},
            {"dateStart": "2026-02"},
            {"dateStart": "2026-07-10"},
            {"dateStart": "2025-11-08"},
            {"dateStart": "2026-05-23"},
            {"dateStart": "2025-11-15"},
        ]
        ordered = [s["dateStart"] for s in sorted(shows, key=build.sort_key, reverse=True)]
        self.assertEqual(ordered, ["2026-07-10", "2026-05-23", "2026-02",
                                   "2025-11-15", "2025-11-08", "2023-06-01"])

    def test_year_range_uses_start_year_not_a_giant_month(self):
        # "2013-2014" is a range starting in 2013, so it must sort BELOW a real
        # dated show in the same year, not above it.
        shows = [{"dateStart": "2013-2014"}, {"dateStart": "2013-06-01"}]
        ordered = [s["dateStart"] for s in sorted(shows, key=build.sort_key, reverse=True)]
        self.assertEqual(ordered, ["2013-06-01", "2013-2014"])

    def test_year_only_sorts_below_month_dated_show_same_year(self):
        shows = [{"dateStart": "2024"}, {"dateStart": "2024-03"}]
        ordered = [s["dateStart"] for s in sorted(shows, key=build.sort_key, reverse=True)]
        self.assertEqual(ordered, ["2024-03", "2024"])

    def test_missing_datestart_sorts_last(self):
        shows = [{"dateStart": "2020-01-01"}, {"slug": "x"}]
        ordered = sorted(shows, key=build.sort_key, reverse=True)
        self.assertEqual(ordered[0]["dateStart"], "2020-01-01")


class TestPathHelpers(unittest.TestCase):
    def test_thumb_for_with_folder(self):
        self.assertEqual(build.thumb_for("assets/x/a.jpg"), "assets/x/thumb-a.jpg")

    def test_thumb_for_without_slash_does_not_crash(self):
        self.assertEqual(build.thumb_for("a.jpg"), "thumb-a.jpg")

    def test_poster_for_with_folder(self):
        self.assertEqual(build.poster_for("assets/x/v.mp4"), "assets/x/v-poster.jpg")

    def test_poster_for_without_slash_does_not_crash(self):
        self.assertEqual(build.poster_for("v.mp4"), "v-poster.jpg")


class TestPlaceLabel(unittest.TestCase):
    def test_venue_and_city(self):
        self.assertEqual(build.place_label({"venue": "Galeria 111", "city": "Lisboa"}),
                         "Galeria 111, Lisboa")

    def test_empty_venue_no_leading_comma(self):
        self.assertEqual(build.place_label({"venue": "", "city": "Berlin"}), "Berlin")

    def test_no_fields(self):
        self.assertEqual(build.place_label({}), "")


class TestSeoHelpers(unittest.TestCase):
    def test_abs_url_root_and_path(self):
        self.assertEqual(build.abs_url(), build.SITE_URL + "/")
        self.assertEqual(build.abs_url("about/"), build.SITE_URL + "/about/")

    def test_truncate_short_unchanged(self):
        self.assertEqual(build.truncate("hello world", 100), "hello world")

    def test_truncate_long_adds_ellipsis_within_limit(self):
        out = build.truncate("word " * 60, 50)
        self.assertLessEqual(len(out), 51)
        self.assertTrue(out.endswith("…"))

    def test_show_description_composes(self):
        show = {"title": "X", "type": "solo", "venue": "Gal", "city": "Lisboa", "dateLabel": "2025"}
        self.assertEqual(build.show_description(show),
                         "X, a solo exhibition at Gal, Lisboa (2025).")

    def test_jsonld_is_valid_json_and_escapes_closing_tag(self):
        s = build.jsonld_script({"@type": "Person", "name": "A</script>B"})
        prefix = '<script type="application/ld+json">'
        inner = s[len(prefix):-len("</script>")]
        self.assertNotIn("</", inner)  # cannot close the script tag early
        self.assertEqual(json.loads(inner.replace("<\\/", "</"))["name"], "A</script>B")

    def test_person_ld(self):
        obj = build.person_ld()
        self.assertEqual(obj["@type"], "Person")
        self.assertEqual(obj["name"], "Roger Paulino")

    def test_exhibition_ld_omits_missing_fields(self):
        obj = build.exhibition_ld({"slug": "x", "title": "X"}, None)
        self.assertNotIn("startDate", obj)
        self.assertNotIn("image", obj)
        self.assertEqual(obj["@type"], "ExhibitionEvent")

    def test_exhibition_ld_postal_address_when_present(self):
        obj = build.exhibition_ld(
            {"slug": "x", "title": "X", "address": "Schlegelstr. 6, 10115 Berlin-Mitte", "city": "Berlin"}, None)
        addr = obj["location"]["address"]
        self.assertEqual(addr["@type"], "PostalAddress")
        self.assertEqual(addr["streetAddress"], "Schlegelstr. 6, 10115 Berlin-Mitte")
        self.assertEqual(addr["addressLocality"], "Berlin")

    def test_sitemap_and_robots_and_llms(self):
        shows = [{"slug": "foo", "title": "Foo", "dateStart": "2025", "venue": "V", "city": "C", "dateLabel": "2025"}]
        xml = build.build_sitemap(shows)
        self.assertIn(build.abs_url("exhibitions/foo/"), xml)
        self.assertIn("urlset", xml)
        self.assertIn("Sitemap:", build.build_robots())
        txt = build.build_llms(shows)
        self.assertIn("Foo", txt)
        self.assertIn(build.abs_url("exhibitions/foo/"), txt)

    def test_llms_has_about_block_before_exhibitions(self):
        txt = build.build_llms([])
        self.assertIn("## About", txt)
        self.assertLess(txt.index("## About"), txt.index("## Exhibitions"))
        self.assertIn("Leipzig", txt)  # bio grounding fact present


class TestFeedHelpers(unittest.TestCase):
    def test_year_of_variants(self):
        self.assertEqual(build.year_of({"dateStart": "2026-02-10"}), "2026")
        self.assertEqual(build.year_of({"dateStart": "2013-2014"}), "2013")
        self.assertEqual(build.year_of({}), "")

    def test_feed_excerpt_prefers_explicit_field(self):
        show = {"feedExcerpt": "Hand written.", "statement": ["Ignore me."]}
        self.assertEqual(build.feed_excerpt(show), "Hand written.")

    def test_feed_excerpt_derives_from_statement_first_sentence(self):
        show = {"statement": ["A quiet room. A loud idea.", "Second para."]}
        self.assertEqual(build.feed_excerpt(show), "A quiet room.")

    def test_feed_excerpt_empty_when_nothing(self):
        self.assertEqual(build.feed_excerpt({}), "")
        self.assertEqual(build.feed_excerpt({"statement": []}), "")


class TestFeedBlock(unittest.TestCase):
    def test_feed_block_ctx_shapes_a_show(self):
        show = {"slug": "x", "title": "X", "venue": "Gal", "city": "Lisboa",
                "type": "solo", "dateStart": "2025-03", "medium": "linocut",
                "statement": ["A line. B line."], "media": []}
        b = build.feed_block_ctx(show)
        self.assertEqual(b["title"], "X")
        self.assertEqual(b["year"], "2025")
        self.assertEqual(b["place"], "Gal, Lisboa")
        self.assertEqual(b["typeLabel"], "Solo exhibition")
        self.assertEqual(b["medium"], "linocut")
        self.assertEqual(b["excerpt"], "A line.")
        self.assertEqual(b["url"], "exhibitions/x/index.html")
        self.assertTrue(b["noImage"])

    def test_feed_block_hero_when_media_present(self):
        show = {"slug": "y", "title": "Y", "media": [
            {"type": "image", "src": "assets/y/a.jpg", "hero": True, "alt": "A"}]}
        b = build.feed_block_ctx(show)
        self.assertTrue(b["hasImage"])
        self.assertEqual(b["heroSrc"], "assets/y/a.jpg")
        self.assertEqual(b["heroAlt"], "A")


class TestPersonEntity(unittest.TestCase):
    def test_metadescription_says_leipzig_not_portugal(self):
        md = build.SITE["metaDescription"]
        self.assertNotIn("between Germany and Portugal", md)
        self.assertIn("Leipzig", md)

    def test_person_ld_has_grounding_facts(self):
        obj = build.person_ld()
        self.assertEqual(obj["@type"], "Person")
        self.assertEqual(obj["birthDate"], "1986")
        self.assertEqual(obj["birthPlace"]["name"], "Pretoria, South Africa")
        self.assertEqual(obj["homeLocation"]["name"], "Leipzig, Germany")
        self.assertEqual(obj["workLocation"]["name"], "Leipzig, Germany")
        self.assertIn("Printmaking", obj["knowsAbout"])
        self.assertTrue(all(a["@type"] == "EducationalOrganization" for a in obj["alumniOf"]))
        self.assertIn("Studienstiftung", obj["award"])

    def test_person_ld_sameas_includes_instagram_and_press(self):
        obj = build.person_ld()
        self.assertIn(build.SITE["instagram"], obj["sameAs"])
        self.assertGreaterEqual(len(obj["sameAs"]), 4)

    def test_person_ld_omits_unconfirmed_nationality(self):
        self.assertNotIn("nationality", build.person_ld())


if __name__ == "__main__":
    unittest.main()
