import unittest

from webcollect.pagination import PageCollector, wait_stable


class TestPageCollector(unittest.TestCase):
    def test_collects_all_pages(self):
        pages = [
            [{"id": 1}, {"id": 2}],
            [{"id": 3}, {"id": 4}],
        ]
        i = [0]

        def read():
            return pages[i[0]]

        def has_next():
            return i[0] < len(pages) - 1

        def go_next():
            i[0] += 1
            return True

        c = PageCollector(read, has_next, go_next, key=lambda r: r["id"])
        got = c.collect()
        self.assertEqual([r["id"] for r in got], [1, 2, 3, 4])

    def test_dedup_across_pages(self):
        pages = [[{"id": 1}, {"id": 2}], [{"id": 2}, {"id": 3}]]
        i = [0]

        def read():
            return pages[i[0]]

        def has_next():
            return i[0] < len(pages) - 1

        def go_next():
            i[0] += 1
            return True

        c = PageCollector(read, has_next, go_next, key=lambda r: r["id"])
        self.assertEqual([r["id"] for r in c.collect()], [1, 2, 3])

    def test_stops_on_go_next_failure(self):
        def read():
            return [{"id": 1}]

        c = PageCollector(read, lambda: True, lambda: False, key=lambda r: r["id"])
        self.assertEqual(len(c.collect()), 1)

    def test_respects_max_pages(self):
        counter = [0]

        def read():
            counter[0] += 1
            return [{"id": counter[0]}]

        c = PageCollector(read, lambda: True, lambda: True, key=lambda r: r["id"])
        self.assertEqual(len(c.collect(max_pages=3)), 3)

    def test_on_page_callback(self):
        seen = []
        c = PageCollector(lambda: [{"id": 1}], lambda: False, lambda: True,
                          key=lambda r: r["id"])
        c.collect(on_page=lambda n, rows: seen.append(n))
        self.assertEqual(seen, [1])


class TestWaitStable(unittest.TestCase):
    def test_becomes_stable(self):
        vals = iter([1, 2, 2, 2])
        slept = []

        def read():
            try:
                return next(vals)
            except StopIteration:
                return 2

        ok = wait_stable(read, need_stable=2, interval=0.01,
                         sleep=lambda s: slept.append(s))
        self.assertTrue(ok)

    def test_timeout(self):
        def read():
            return object()  # never equal

        ok = wait_stable(read, max_wait=0.05, need_stable=2, interval=0.01,
                         sleep=lambda s: None)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
