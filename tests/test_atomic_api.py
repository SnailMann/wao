from __future__ import annotations

import unittest

from daily_cli.tools.trend import TREND_SOURCE_CHOICES, list_trend_specs


class AtomicApiTests(unittest.TestCase):
    def test_trend_public_module_exports_expected_sources(self) -> None:
        self.assertEqual(TREND_SOURCE_CHOICES, ("auto", "google", "baidu", "github", "all"))

    def test_trend_public_module_lists_three_atomic_specs(self) -> None:
        specs = list_trend_specs()
        self.assertEqual([spec.key for spec in specs], ["trend-google", "trend-baidu", "trend-github"])


if __name__ == "__main__":
    unittest.main()
