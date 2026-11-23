import unittest

from webcollect.table import TableExtractor, find_header, extract, normalize, to_number


class TestNormalize(unittest.TestCase):
    def test_collapse_whitespace(self):
        self.assertEqual(normalize("  a\n\t b  "), "a b")

    def test_nbsp(self):
        self.assertEqual(normalize("a\u00a0b"), "a b")

    def test_none(self):
        self.assertEqual(normalize(None), "")


class TestFindHeader(unittest.TestCase):
    def test_finds_by_contains(self):
        rows = [["#", "Cost (¥)", "ROI"], ["A", "100", "2.5"]]
        got = find_header(rows, ["Cost", "ROI"])
        self.assertIsNotNone(got)
        self.assertEqual(got[0], 0)
        self.assertEqual(got[1]["Cost"], 1)

    def test_exact_match(self):
        rows = [["Cost", "Cost per day"], ["1", "2"]]
        got = find_header(rows, ["Cost"], match="exact")
        self.assertEqual(got[1]["Cost"], 0)

    def test_requires_all_labels(self):
        rows = [["Cost", "Name"], ["1", "A"]]
        self.assertIsNone(find_header(rows, ["Cost", "ROI"]))

    def test_empty(self):
        self.assertIsNone(find_header([], ["Cost"]))


class TestExtract(unittest.TestCase):
    def test_extract_with_converter(self):
        rows = [
            ["Name", "Cost", "ROI"],
            ["A", "1,234.5", "2.5%"],
            ["B", "bad", "3.0"],
        ]
        header = find_header(rows, ["Name", "Cost", "ROI"])
        fields = {
            "name": ("Name", None),
            "cost": ("Cost", to_number),
            "roi": ("ROI", to_number),
        }
        got = extract(rows, header, fields)
        self.assertEqual(got[0]["name"], "A")
        self.assertEqual(got[0]["cost"], 1234.5)
        self.assertEqual(got[1]["roi"], 3.0)

    def test_skip_junk_rows(self):
        rows = [["Cost"], ["100"], ["Total 999"], ["80"]]
        header = find_header(rows, ["Cost"])
        got = extract(rows, header, {"cost": ("Cost", to_number)},
                      skip=lambda r: "Total" in " ".join(r))
        self.assertEqual(got, [{"cost": 100.0}, {"cost": 80.0}])


class TestToNumber(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(to_number("1,234.5"), 1234.5)

    def test_percent(self):
        self.assertEqual(to_number("12.3%"), 12.3)

    def test_currency(self):
        self.assertEqual(to_number("¥89"), 89.0)

    def test_garbage(self):
        self.assertEqual(to_number("abc"), None)
        self.assertEqual(to_number(""), None)


class TestTableExtractor(unittest.TestCase):
    def test_end_to_end(self):
        ext = TableExtractor(
            labels=["Cost", "ROI"],
            fields={"cost": ("Cost", to_number), "roi": ("ROI", to_number)},
        )
        rows = [["x", "Cost", "ROI"], ["y", "100", "2.0"], ["z", "200", "3.0"]]
        self.assertEqual(len(ext(rows)), 2)
        self.assertEqual(ext(rows)[1]["roi"], 3.0)

    def test_no_header_returns_empty(self):
        ext = TableExtractor(labels=["Cost"], fields={"c": ("Cost", None)})
        self.assertEqual(ext([["a", "b"]]), [])


if __name__ == "__main__":
    unittest.main()
