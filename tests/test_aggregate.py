import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GH_TOKEN", "offline-test")  # the module exits on import without a token

import language_stats  # noqa: E402


def repo(name, owner="brunosiqp", fork=False):
    return {"full_name": f"{owner}/{name}", "owner": {"login": owner}, "fork": fork}


TREES = {
    # A huge Python project with a tiny PowerShell helper.
    "brunosiqp/big": [{"path": "app.py", "size": 5_000_000}, {"path": "tools/run.ps1", "size": 200}],
    # Small projects.
    "brunosiqp/small-ps": [{"path": "clean.ps1", "size": 900}],
    "brunosiqp/site": [{"path": "index.html", "size": 3000}, {"path": "main.py", "size": 100}],
}


class LanguagesInTests(unittest.TestCase):
    def test_languages_in_returns_each_language_once(self):
        entries = [{"path": "a.py"}, {"path": "b.py"}, {"path": "c.ps1"}, {"path": "README.md"}]
        self.assertEqual(language_stats.languages_in(entries), {"Python", "PowerShell"})

    def test_languages_in_respects_only(self):
        entries = [{"path": "a.py"}, {"path": "c.ps1"}]
        self.assertEqual(language_stats.languages_in(entries, only={"c.ps1"}), {"PowerShell"})

    def test_language_sizes_sums_bytes_per_language(self):
        entries = [{"path": "a.py", "size": 10}, {"path": "b.py", "size": 5}, {"path": "c.ps1", "size": 2}]
        self.assertEqual(language_stats.language_sizes(entries), {"Python": 15, "PowerShell": 2})

    def test_languages_in_ignores_build_output(self):
        self.assertEqual(language_stats.languages_in([{"path": "build/x.py"}]), set())


class AggregateTests(unittest.TestCase):
    def run_aggregate(self, repos):
        with (mock.patch.object(language_stats, "get_tree", side_effect=lambda r: TREES[r["full_name"]]),
              mock.patch.object(language_stats, "get_repo_languages", return_value={}),
              mock.patch("builtins.print")):
            return language_stats.aggregate_languages(repos, "brunosiqp")

    def test_counts_repositories(self):
        by_repos, _ = self.run_aggregate([repo("big"), repo("small-ps"), repo("site")])
        self.assertEqual(by_repos, {"Python": 2, "PowerShell": 2, "HTML": 1})

    def test_also_sums_code_size(self):
        _, by_size = self.run_aggregate([repo("big"), repo("small-ps"), repo("site")])
        self.assertEqual(by_size, {"Python": 5_000_100, "PowerShell": 1100, "HTML": 3000})

    def test_percentages_follow_repository_counts(self):
        by_repos, _ = self.run_aggregate([repo("big"), repo("small-ps"), repo("site")])
        pct = dict(language_stats.to_percentages(by_repos))
        self.assertAlmostEqual(pct["Python"], 40.0)
        self.assertAlmostEqual(pct["HTML"], 20.0)


if __name__ == "__main__":
    unittest.main()
