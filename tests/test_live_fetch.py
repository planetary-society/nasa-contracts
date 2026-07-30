"""Optional integration tests against the live NPDV endpoint.

Skipped unless NPDV_LIVE_TESTS=1:

    NPDV_LIVE_TESTS=1 python -m unittest discover -s tests -v

They issue four POSTs to prod.nais.nasa.gov, all for Vermont or Outside U.S.,
NPDV's two smallest exports (Vermont returned 14 rows for FY2026). Everything
asserted here held for all 795,393 committed rows, so a failure means NPDV's
export changed rather than that the expectation was speculative.
"""

import csv
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

import requests

from test_fetch_contracts import TARGETS, fetch_contracts


LEGACY_FISCAL_YEAR = 2008
LIVE_TESTS_ENABLED = os.environ.get("NPDV_LIVE_TESTS") == "1"


def current_fiscal_year():
    today = date.today()
    return today.year + 1 if today.month >= 10 else today.year


@unittest.skipUnless(
    LIVE_TESTS_ENABLED, "set NPDV_LIVE_TESTS=1 to query prod.nais.nasa.gov"
)
class LiveExportTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.vermont = TARGETS["VT"]
        self.international = TARGETS["International"]
        self.fiscal_year = current_fiscal_year()

    def fetcher_for(self, fiscal_years, targets):
        return fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(
                output_dir=self.output_dir.name,
                fiscal_years=fiscal_years,
                targets=targets,
            )
        )

    def fetch(self, year, target):
        """Fetch one export, skipping the test when NPDV is unreachable."""
        fetcher = self.fetcher_for([year], [target])
        try:
            return fetcher.fetch_target(year, target)
        except (requests.ConnectionError, requests.Timeout) as error:
            self.skipTest(f"NPDV unreachable: {error}")

    def assert_rows_are_well_formed(self, year, target, rows):
        header = fetch_contracts.source_header_for_year(year)
        column = {name: 2 + index for index, name in enumerate(header)}
        self.assertTrue(
            rows, f"NPDV returned no FY{year} rows for {target.output_state}"
        )

        for row in rows:
            self.assertEqual(2 + len(header), len(row), row)
            self.assertEqual(target.output_state, row[0])
            if target.international:
                self.assertEqual("", row[1], row)
            elif row[1]:
                self.assertRegex(row[1], rf"^{target.output_state}-([0-8]\d|9[0-8])$")
            # The export lists the indicators under its "Award Type" header;
            # only the swapped-back columns satisfy both of these.
            self.assertNotIn(" - ", row[column["Award Type"]])
            self.assertIn(" - ", row[column["Contractor Type - Indicators"]])
            self.assertIn("Modification", row[column["Contract/Mod Number"]])
            for name in ("Award Date", "Completion Date"):
                self.assertRegex(row[column[name]], r"^\d{2}/\d{2}/\d{4}$")
            for name in ("Obligations", "Change in Award Value"):
                self.assertRegex(row[column[name]], r"^\$-?[\d,]+$")
            for value in row:
                self.assertNotRegex(value, r"[\t\r\n]")

    def test_current_fiscal_year_export(self):
        rows = self.fetch(self.fiscal_year, self.vermont)

        self.assert_rows_are_well_formed(self.fiscal_year, self.vermont, rows)
        self.assertEqual(17, len(rows[0]))

    def test_legacy_schema_export(self):
        rows = self.fetch(LEGACY_FISCAL_YEAR, self.vermont)

        self.assert_rows_are_well_formed(LEGACY_FISCAL_YEAR, self.vermont, rows)
        self.assertEqual(16, len(rows[0]))

    def test_international_export(self):
        rows = self.fetch(self.fiscal_year, self.international)

        self.assert_rows_are_well_formed(self.fiscal_year, self.international, rows)

    def test_fetch_and_save_data_writes_a_validated_file(self):
        fetcher = self.fetcher_for([self.fiscal_year], [self.vermont])
        try:
            fetcher.fetch_and_save_data()
        except (requests.ConnectionError, requests.Timeout) as error:
            self.skipTest(f"NPDV unreachable: {error}")

        destination = (
            Path(self.output_dir.name) / f"nasa_contracts_{self.fiscal_year}.csv"
        )
        with destination.open(newline="", encoding="utf-8") as csvfile:
            rows = list(csv.reader(csvfile))

        self.assertEqual(
            ["State", "District"] + list(fetch_contracts.MODERN_SOURCE_HEADER),
            rows[0],
        )
        self.assert_rows_are_well_formed(self.fiscal_year, self.vermont, rows[1:])
        self.assertEqual([destination], list(Path(self.output_dir.name).iterdir()))


@unittest.skipUnless(
    LIVE_TESTS_ENABLED, "set NPDV_LIVE_TESTS=1 to query prod.nais.nasa.gov"
)
class LiveRejectionTests(unittest.TestCase):
    """Confirm NPDV still answers a bad query the way the parser expects."""

    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_unknown_state_code_is_rejected(self):
        bogus = fetch_contracts.QueryTarget("VT", "NOT A STATE", "99", "VT")

        try:
            with self.assertRaises(fetch_contracts.DataValidationError):
                self.fetcher.fetch_target(current_fiscal_year(), bogus)
        except (requests.ConnectionError, requests.Timeout) as error:
            self.skipTest(f"NPDV unreachable: {error}")


if __name__ == "__main__":
    unittest.main()
