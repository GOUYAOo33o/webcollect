import os
import tempfile
import unittest

from webcollect.browser import ProfileGuard, ProfileLocked, clean_profile_locks


class TestProfileGuard(unittest.TestCase):
    def test_acquire_release(self):
        with tempfile.TemporaryDirectory() as d:
            g = ProfileGuard(os.path.join(d, "p1"))
            self.assertTrue(g.acquire())
            g.release()
            self.assertFalse(os.path.exists(g.lock))

    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as d:
            with ProfileGuard(os.path.join(d, "p2")):
                pass

    def test_second_acquire_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p3")
            g1 = ProfileGuard(p, stale_after=9999)
            g2 = ProfileGuard(p, stale_after=9999)
            self.assertTrue(g1.acquire())
            self.assertFalse(g2.acquire())
            g1.release()

    def test_stale_lock_reclaimed(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p4")
            g1 = ProfileGuard(p)
            g1.acquire()
            os.utime(g1.lock, (0, 0))  # very old
            g2 = ProfileGuard(p, stale_after=1)
            self.assertTrue(g2.acquire())
            g2.release()


class TestCleanProfileLocks(unittest.TestCase):
    def test_removes_only_known_locks(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("SingletonLock", "lockfile", "data.json"):
                with open(os.path.join(d, name), "w") as f:
                    f.write("x")
            removed = clean_profile_locks(d)
            self.assertIn("SingletonLock", [os.path.basename(x) for x in removed])
            self.assertTrue(os.path.exists(os.path.join(d, "data.json")))

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "SingletonLock")
            with open(p, "w") as f:
                f.write("x")
            removed = clean_profile_locks(d, dry_run=True)
            self.assertEqual(len(removed), 1)
            self.assertTrue(os.path.exists(p))

    def test_missing_dir(self):
        self.assertEqual(clean_profile_locks("/no/such/dir"), [])


if __name__ == "__main__":
    unittest.main()
