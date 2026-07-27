"""Unit tests for build.py (the static site generator).

Run from the repo root:  python3 -m unittest discover -s tests
Standard library only, matching build.py.
"""
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
        self.assertNotIn("year", build.base_ctx("", "t"))
        self.assertIn("site_year", build.base_ctx("", "t"))
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


if __name__ == "__main__":
    unittest.main()
