import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "fetch-contracts.py"
SPEC = importlib.util.spec_from_file_location("fetch_contracts", SCRIPT_PATH)
fetch_contracts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fetch_contracts
SPEC.loader.exec_module(fetch_contracts)


def make_export_response(header, rows, international=False, reported_count=None):
    if reported_count is None:
        reported_count = len(rows)
    if international:
        preamble = [
            "",
            "Outside US",
            "NASA Center: ALL",
            "Fiscal Year: FY26",
            f"{reported_count} Records found",
        ]
    else:
        preamble = [
            "STATE OF MONTANA",
            "NASA Center: ALL",
            "Fiscal Year: FY 26",
            "Congressional District: ALL",
            "Business Category: ALL",
            f"{reported_count} Records found",
        ]
    return "\n".join(preamble + ["\t".join(header)] + ["\t".join(row) for row in rows])


def modern_source_row():
    return [
        '" Russia Space Agency "',
        "80TEST Modification 0 (Base Record)",
        "GSFC - Goddard Space Flight Center",
        '"MISSOULA, MT (District 02)"',
        "10/01/2025",
        "09/30/2026",
        '"SMALL BUSINESS - Contractor Indicator"',
        '" Cooperative Agreement, Cost No Fee"',
        '"$1,000"',
        '"$250"',
        "541715",
        "",
        "N/A",
        '"N/A"',
        '"MIXED Case AS "Quoted"  "',
    ]


def make_http_response(text):
    response = requests.Response()
    response.status_code = 200
    response._content = text.encode("ISO-8859-1")
    response.encoding = "utf-8"
    response.headers["Content-Type"] = "text/html; charset=ISO-8859-1"
    return response


class QueryTargetTests(unittest.TestCase):
    def test_default_targets_include_dc_and_international(self):
        self.assertTrue(hasattr(fetch_contracts, "QueryTarget"))

        targets = {target.output_state: target for target in fetch_contracts.DEFAULT_TARGETS}
        self.assertEqual(52, len(targets))
        self.assertEqual(
            {
                "AK": "02", "AL": "01", "AR": "05", "AZ": "04", "CA": "06",
                "CO": "08", "CT": "09", "DC": "11", "DE": "10", "FL": "12",
                "GA": "13", "HI": "15", "IA": "19", "ID": "16", "IL": "17",
                "IN": "18", "KS": "20", "KY": "21", "LA": "22", "MA": "25",
                "MD": "24", "ME": "23", "MI": "26", "MN": "27", "MO": "29",
                "MS": "28", "MT": "30", "NC": "37", "ND": "38", "NE": "31",
                "NH": "33", "NJ": "34", "NM": "35", "NV": "32", "NY": "36",
                "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
                "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
                "VA": "51", "VT": "50", "WA": "53", "WI": "55", "WV": "54",
                "WY": "56",
            },
            {
                state: target.request_code
                for state, target in targets.items()
                if state != "International"
            },
        )
        self.assertEqual(
            ("WASHINGTON D.C.", "11", "DC", False),
            (
                targets["DC"].request_state,
                targets["DC"].request_code,
                targets["DC"].request_state2,
                targets["DC"].international,
            ),
        )
        self.assertEqual(
            ("OUTSIDE US", "xx", "WORLD", True),
            (
                targets["International"].request_state,
                targets["International"].request_code,
                targets["International"].request_state2,
                targets["International"].international,
            ),
        )
        self.assertNotIn("PR", targets)
        self.assertNotIn("VI", targets)

    def test_build_post_data_uses_domestic_target_values(self):
        with tempfile.TemporaryDirectory() as output_dir:
            fetcher = fetch_contracts.NASADataFetcher(
                fetch_contracts.Config(output_dir=output_dir)
            )
            alaska = next(
                target
                for target in fetch_contracts.DEFAULT_TARGETS
                if target.output_state == "AK"
            )

            payload = fetcher._build_post_data(2026, alaska)

        self.assertEqual(
            {
                "bus_cat": "ALL",
                "fy": "FY 26",
                "recovery": "0",
                "v_center": "ALL",
                "v_database": "FY26",
                "v_code": "02",
                "v_district": "ALL",
                "v_end_date": "2026-09-30",
                "v_start_date": "2025-10-01",
                "v_state": "ALASKA",
                "v_state2": "AK",
                "action": "Export to Excel",
            },
            payload,
        )

    def test_build_post_data_uses_dc_target_values(self):
        with tempfile.TemporaryDirectory() as output_dir:
            fetcher = fetch_contracts.NASADataFetcher(
                fetch_contracts.Config(output_dir=output_dir)
            )
            dc = next(
                target
                for target in fetch_contracts.DEFAULT_TARGETS
                if target.output_state == "DC"
            )

            payload = fetcher._build_post_data(2026, dc)

        self.assertEqual(
            {
                "bus_cat": "ALL",
                "fy": "FY 26",
                "recovery": "0",
                "v_center": "ALL",
                "v_database": "FY26",
                "v_code": "11",
                "v_district": "ALL",
                "v_end_date": "2026-09-30",
                "v_start_date": "2025-10-01",
                "v_state": "WASHINGTON D.C.",
                "v_state2": "DC",
                "action": "Export to Excel",
            },
            payload,
        )

    def test_build_post_data_uses_international_target_values(self):
        with tempfile.TemporaryDirectory() as output_dir:
            fetcher = fetch_contracts.NASADataFetcher(
                fetch_contracts.Config(output_dir=output_dir)
            )
            international = next(
                target
                for target in fetch_contracts.DEFAULT_TARGETS
                if target.output_state == "International"
            )

            payload = fetcher._build_post_data(2026, international)

        self.assertEqual(
            {
                "bus_cat": "",
                "fy": "FY 26",
                "recovery": "",
                "v_center": "ALL",
                "v_database": "FY26",
                "v_code": "xx",
                "v_district": "",
                "v_end_date": "2026-09-30",
                "v_start_date": "2025-10-01",
                "v_state": "OUTSIDE US",
                "v_state2": "WORLD",
                "action": "Export to Excel",
            },
            payload,
        )


class SchemaTests(unittest.TestCase):
    def test_source_schema_changes_only_after_fy2008(self):
        legacy = (
            "Contractor",
            "Contract/Mod Number",
            "NASA Center",
            "Place of Performance",
            "Award Date",
            "Completion Date",
            "Award Type",
            "Contractor Type - Indicators",
            "Obligations",
            "Change in Award Value",
            "NAICS Code",
            "Solicitation ID",
            "Solicitation POC",
            "Description",
        )
        modern = legacy[:11] + ("TAS Code",) + legacy[11:]

        self.assertEqual(legacy, fetch_contracts.source_header_for_year(2005))
        self.assertEqual(legacy, fetch_contracts.source_header_for_year(2008))
        self.assertEqual(modern, fetch_contracts.source_header_for_year(2009))
        self.assertEqual(modern, fetch_contracts.source_header_for_year(2026))

    def test_source_schema_rejects_fiscal_years_before_fy2005(self):
        with self.assertRaises(ValueError):
            fetch_contracts.source_header_for_year(2004)


class DistrictTests(unittest.TestCase):
    def test_districts_follow_source_tokens(self):
        with tempfile.TemporaryDirectory() as output_dir:
            fetcher = fetch_contracts.NASADataFetcher(
                fetch_contracts.Config(output_dir=output_dir)
            )
            targets = {
                target.output_state: target
                for target in fetch_contracts.DEFAULT_TARGETS
            }

            cases = (
                ("MT", "BOZEMAN, MT (District 00)", "MT-00"),
                ("MT", "BOZEMAN, MT (District 01)", "MT-01"),
                ("MT", "MISSOULA, MT (District 02)", "MT-02"),
                ("DC", "WASHINGTON, DC (District 98)", "DC-98"),
                ("TX", "HOUSTON, TX (District NA)", "TX-NA"),
                ("TX", "HOUSTON, TX", ""),
                ("International", "GERMANY", ""),
            )

            for state, place_of_performance, expected in cases:
                with self.subTest(state=state, place=place_of_performance):
                    self.assertEqual(
                        expected,
                        fetcher._determine_district(
                            targets[state], place_of_performance
                        ),
                    )

    def test_invalid_district_tokens_are_not_emitted(self):
        with tempfile.TemporaryDirectory() as output_dir:
            fetcher = fetch_contracts.NASADataFetcher(
                fetch_contracts.Config(output_dir=output_dir)
            )
            montana = next(
                target
                for target in fetch_contracts.DEFAULT_TARGETS
                if target.output_state == "MT"
            )

            for place_of_performance in (
                "BOZEMAN, MT (District 1)",
                "BOZEMAN, MT (District ABC)",
            ):
                with self.subTest(place=place_of_performance):
                    self.assertEqual(
                        "",
                        fetcher._determine_district(
                            montana, place_of_performance
                        ),
                    )


class ResponseParsingTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )
        self.targets = {
            target.output_state: target for target in fetch_contracts.DEFAULT_TARGETS
        }

    def test_domestic_response_preserves_text_and_reorders_semantic_columns(self):
        source_row = modern_source_row()
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [source_row]
        )

        rows = self.fetcher._parse_response(
            2026, self.targets["MT"], response_text
        )

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(["MT", "MT-02"], row[:2])
        self.assertEqual(" Russia Space Agency ", row[2])
        self.assertEqual(" Cooperative Agreement, Cost No Fee", row[8])
        self.assertEqual("SMALL BUSINESS - Contractor Indicator", row[9])
        self.assertEqual('MIXED Case AS "Quoted"  ', row[-1])

    def test_international_response_uses_dynamic_header_location(self):
        source_row = modern_source_row()
        source_row[3] = '"GERMANY"'
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER,
            [source_row],
            international=True,
        )

        rows = self.fetcher._parse_response(
            2026, self.targets["International"], response_text
        )

        self.assertEqual("International", rows[0][0])
        self.assertEqual("", rows[0][1])
        self.assertEqual("GERMANY", rows[0][5])

    def test_legacy_response_keeps_legacy_width_and_description_position(self):
        source_row = modern_source_row()
        del source_row[11]
        response_text = make_export_response(
            fetch_contracts.LEGACY_SOURCE_HEADER, [source_row]
        )

        rows = self.fetcher._parse_response(
            2008, self.targets["MT"], response_text
        )

        self.assertEqual(16, len(rows[0]))
        self.assertEqual('MIXED Case AS "Quoted"  ', rows[0][-1])

    def test_unexpected_header_is_rejected(self):
        bad_header = list(fetch_contracts.MODERN_SOURCE_HEADER)
        bad_header[11] = "Unexpected Column"
        response_text = make_export_response(bad_header, [modern_source_row()])

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(
                2026, self.targets["MT"], response_text
            )

    def test_bad_row_width_is_rejected(self):
        short_row = modern_source_row()[:-1]
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [short_row]
        )

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(
                2026, self.targets["MT"], response_text
            )

    def test_reported_record_count_mismatch_is_rejected(self):
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER,
            [modern_source_row()],
            reported_count=2,
        )

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(
                2026, self.targets["MT"], response_text
            )


class AtomicFetchTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        targets = {
            target.output_state: target for target in fetch_contracts.DEFAULT_TARGETS
        }
        self.mt = targets["MT"]
        self.international = targets["International"]

    def test_failed_target_does_not_replace_existing_file(self):
        destination = Path(self.output_dir.name) / "nasa_contracts_2026.csv"
        destination.write_bytes(b"existing complete data\n")
        mt_response = make_http_response(
            make_export_response(
                fetch_contracts.MODERN_SOURCE_HEADER, [modern_source_row()]
            )
        )
        config = fetch_contracts.Config(
            output_dir=self.output_dir.name,
            fiscal_years=[2026],
            targets=[self.mt, self.international],
        )
        fetcher = fetch_contracts.NASADataFetcher(config)

        with mock.patch.object(
            fetch_contracts.requests,
            "post",
            side_effect=[mt_response, requests.ConnectionError("offline")],
        ):
            with self.assertRaises(requests.RequestException):
                fetcher.fetch_and_save_data()

        self.assertEqual(b"existing complete data\n", destination.read_bytes())
        self.assertEqual([destination], list(Path(self.output_dir.name).iterdir()))

    def test_validation_failure_does_not_replace_existing_file(self):
        destination = Path(self.output_dir.name) / "nasa_contracts_2026.csv"
        destination.write_bytes(b"existing complete data\n")
        invalid_response = make_http_response(
            make_export_response(
                fetch_contracts.MODERN_SOURCE_HEADER,
                [modern_source_row()],
                reported_count=2,
            )
        )
        config = fetch_contracts.Config(
            output_dir=self.output_dir.name,
            fiscal_years=[2026],
            targets=[self.mt],
        )
        fetcher = fetch_contracts.NASADataFetcher(config)

        with mock.patch.object(
            fetch_contracts.requests,
            "post",
            return_value=invalid_response,
        ):
            with self.assertRaises(fetch_contracts.DataValidationError):
                fetcher.fetch_and_save_data()

        self.assertEqual(b"existing complete data\n", destination.read_bytes())
        self.assertEqual([destination], list(Path(self.output_dir.name).iterdir()))

    def test_successful_year_is_written_with_validated_schema_and_text(self):
        mt_row = modern_source_row()
        mt_row[-1] = '"CAFÉ MIXED Case"'
        international_row = modern_source_row()
        international_row[3] = '"GERMANY"'
        responses = [
            make_http_response(
                make_export_response(
                    fetch_contracts.MODERN_SOURCE_HEADER, [mt_row]
                )
            ),
            make_http_response(
                make_export_response(
                    fetch_contracts.MODERN_SOURCE_HEADER,
                    [international_row],
                    international=True,
                )
            ),
        ]
        config = fetch_contracts.Config(
            output_dir=self.output_dir.name,
            fiscal_years=[2026],
            targets=[self.mt, self.international],
        )
        fetcher = fetch_contracts.NASADataFetcher(config)

        with mock.patch.object(
            fetch_contracts.requests, "post", side_effect=responses
        ):
            fetcher.fetch_and_save_data()

        destination = Path(self.output_dir.name) / "nasa_contracts_2026.csv"
        with destination.open(newline="", encoding="utf-8") as csvfile:
            rows = list(csv.reader(csvfile))

        self.assertEqual(
            ["State", "District"] + list(fetch_contracts.MODERN_SOURCE_HEADER),
            rows[0],
        )
        self.assertEqual("CAFÉ MIXED Case", rows[1][-1])
        self.assertEqual(["MT", "MT-02"], rows[1][:2])
        self.assertEqual(["International", ""], rows[2][:2])


if __name__ == "__main__":
    unittest.main()
