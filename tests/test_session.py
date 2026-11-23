import json
import os
import tempfile
import unittest

from webcollect.session import (cookies_logged_in, is_fresh, load_state,
                                save_state, state_path)


class FakeContext:
    """Minimal context mimicking playwright's storage_state/add_cookies API."""

    def __init__(self):
        self.cookies_list = []
        self.saved = None
        self.local = {}

    def storage_state(self, path):
        self.saved = {"cookies": self.cookies_list, "origins": self.local}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.saved, f)

    def add_cookies(self, cookies):
        self.cookies_list.extend(cookies)

    def set_local_storage(self, origin, entries):
        self.local.setdefault(origin, entries)


class TestSession(unittest.TestCase):
    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = FakeContext()
            ctx.cookies_list = [{"name": "auth_token", "value": "secret", "domain": "x.com"}]
            path = save_state(ctx, "profileA", state_dir=d)
            self.assertTrue(os.path.isfile(path))

            fresh = FakeContext()
            ok = load_state(fresh, "profileA", state_dir=d)
            self.assertTrue(ok)
            self.assertEqual(fresh.cookies_list[0]["name"], "auth_token")

    def test_load_missing_returns_false(self):
        ctx = FakeContext()
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(load_state(ctx, "nope", state_dir=d))

    def test_load_corrupt_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            p = state_path("bad", state_dir=d)
            with open(p, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertFalse(load_state(FakeContext(), "bad", state_dir=d))

    def test_state_path_safe_name(self):
        p = state_path("a:b*c", state_dir="states")
        name = os.path.basename(p)
        self.assertEqual(name, "a_b_c.json")

    def test_is_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as f:
                f.write("{}")
            self.assertTrue(is_fresh(p, max_age_days=1))

    def test_cookies_logged_in(self):
        cookies = [{"name": "sid"}, {"name": "other"}]
        self.assertTrue(cookies_logged_in(cookies, ["sid"]))
        self.assertFalse(cookies_logged_in(cookies, ["missing"]))


if __name__ == "__main__":
    unittest.main()
