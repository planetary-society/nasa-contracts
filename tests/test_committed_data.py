"""Check the committed CSVs in data/ against the guarantees the scraper makes.

These tests read real NPDV output, so they catch drift between the parser and
the files it has already produced. By default one file per source schema is
scanned row by row; set NPDV_FULL_DATA_TESTS=1 to scan every fiscal year.
"""

import csv
import os
import re
import tempfile
import unittest
from pathlib import Path

from test_fetch_contracts import TARGETS, fetch_contracts


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DISTRICT_PATTERN = re.compile(r"^([0-8]\d|9[0-8])$")
FULL_SCAN = os.environ.get("NPDV_FULL_DATA_TESTS") == "1"


def data_files():
    return sorted(DATA_DIR.glob("nasa_contracts_[0-9][0-9][0-9][0-9].csv"))


def fiscal_year_of(path):
    return int(path.stem.rsplit("_", 1)[1])


def scanned_files():
    """Every fiscal year under NPDV_FULL_DATA_TESTS, else one file per schema."""
    paths = data_files()
    if FULL_SCAN:
        return paths
    by_schema = {}
    for path in paths:
        header = fetch_contracts.source_header_for_year(fiscal_year_of(path))
        by_schema[header] = path
    return sorted(by_schema.values())


class CommittedDataTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_every_supported_fiscal_year_is_committed(self):
        years = [fiscal_year_of(path) for path in data_files()]

        self.assertTrue(years, f"no NPDV exports found in {DATA_DIR}")
        self.assertEqual(2005, min(years))
        self.assertEqual(list(range(min(years), max(years) + 1)), years)

    def test_headers_match_the_schema_for_their_year(self):
        for path in data_files():
            with self.subTest(path=path.name):
                year = fiscal_year_of(path)
                with path.open(newline="", encoding="utf-8") as csvfile:
                    header = next(csv.reader(csvfile))

                self.assertEqual(
                    ["State", "District"]
                    + list(fetch_contracts.source_header_for_year(year)),
                    header,
                )

    def test_rows_match_what_the_parser_would_emit_today(self):
        for path in scanned_files():
            year = fiscal_year_of(path)
            width = 2 + len(fetch_contracts.source_header_for_year(year))
            with self.subTest(path=path.name):
                with path.open(newline="", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile)
                    next(reader)
                    for line_number, row in enumerate(reader, start=2):
                        self.assertEqual(
                            width,
                            len(row),
                            f"{path.name} line {line_number} has {len(row)} columns",
                        )
                        state, district, place = row[0], row[1], row[5]
                        self.assertIn(state, TARGETS, f"{path.name}:{line_number}")
                        # The derived district must still follow from the
                        # source-reported place of performance.
                        self.assertEqual(
                            district,
                            self.fetcher._determine_district(TARGETS[state], place),
                            f"{path.name} line {line_number}: {place!r}",
                        )
                        if district:
                            prefix, _, token = district.partition("-")
                            self.assertEqual(state, prefix)
                            self.assertRegex(token, DISTRICT_PATTERN)

    def test_no_field_carries_transport_control_characters(self):
        # Tabs and newlines inside a field would have broken the tab-delimited
        # export; their absence is what makes the parser's line/field split safe.
        for path in scanned_files():
            with self.subTest(path=path.name):
                with path.open(newline="", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile)
                    next(reader)
                    for line_number, row in enumerate(reader, start=2):
                        for value in row:
                            self.assertNotRegex(
                                value,
                                r"[\t\r\n]",
                                f"{path.name} line {line_number}",
                            )


if __name__ == "__main__":
    unittest.main()
