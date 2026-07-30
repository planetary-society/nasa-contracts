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

TARGETS = {target.output_state: target for target in fetch_contracts.DEFAULT_TARGETS}


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
    """Synthetic row exercising quoting, casing, and whitespace edge cases.

    Some of these shapes are not present in NPDV's exports (see the NPDV-*
    fixtures below for real rows); they guard the transport decoding itself.
    """
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


# The NPDV_* fixtures below are real NPDV rows transcribed back into source
# order and transport quoting. Each is followed by the row it produces in the
# committed CSVs, so the pair pins the parser against real exports. NPDV emits
# the contractor-type indicators under its "Award Type" header and the award
# type under its "Contractor Type - Indicators" header; the parser swaps them.
NPDV_MODERN_SOURCE_ROW = [
    '"CH2M HILL, INC."',
    "80MSFC24F0112 Modification P00001",
    "MSFC - Marshall Space Flight Center",
    '"HUNTSVILLE, AL (District 05)"',
    "12/17/2025",
    "09/30/2025",
    '"Other Than Small Business - Corporate Entity Not Tax Exempt, For Profit Organization"',
    '"Delivery Order, Firm Fixed Price"',
    '"$-16,915"',
    '"$-16,915"',
    "541330",
    "",
    "80MSFC19D0021",
    "N/A",
    '"TASK ORDER#80MSFC24F0112 PROJECT# JAC089 "MAF PROGRAM SUPPORT CY25""',
]
NPDV_MODERN_OUTPUT_ROW = [
    "AL",
    "AL-05",
    "CH2M HILL, INC.",
    "80MSFC24F0112 Modification P00001",
    "MSFC - Marshall Space Flight Center",
    "HUNTSVILLE, AL (District 05)",
    "12/17/2025",
    "09/30/2025",
    "Delivery Order, Firm Fixed Price",
    "Other Than Small Business - Corporate Entity Not Tax Exempt, For Profit Organization",
    "-16915",
    "-16915",
    "541330",
    "",
    "80MSFC19D0021",
    "N/A",
    'TASK ORDER#80MSFC24F0112 PROJECT# JAC089 "MAF PROGRAM SUPPORT CY25"',
]

NPDV_LEGACY_SOURCE_ROW = [
    "ATMOSPHERIC RESEARCH CORP",
    "NAG511578 Modification 3",
    "GSFC - Goddard Space Flight Center",
    '"Pittsford, VT (District 00)"',
    "10/29/2004",
    "01/31/2005",
    '"Small Business ONLY - "',
    '"Small Business,, Grant For Research"',
    '"$35,000"',
    '"$35,000"',
    "[None Indicated]",
    "N/A",
    "N/A",
    "'LAND-SURFACE ATMOSPHER STUDIES DIRECTED TO FORE- CAST & CLIMATE MODEL IMPROVEMENT'",
]
NPDV_LEGACY_OUTPUT_ROW = [
    "VT",
    "VT-00",
    "ATMOSPHERIC RESEARCH CORP",
    "NAG511578 Modification 3",
    "GSFC - Goddard Space Flight Center",
    "Pittsford, VT (District 00)",
    "10/29/2004",
    "01/31/2005",
    "Small Business,, Grant For Research",
    "Small Business ONLY - ",
    "35000",
    "35000",
    "[None Indicated]",
    "N/A",
    "N/A",
    "'LAND-SURFACE ATMOSPHER STUDIES DIRECTED TO FORE- CAST & CLIMATE MODEL IMPROVEMENT'",
]


def make_http_response(text):
    response = requests.Response()
    response.status_code = 200
    response._content = text.encode("ISO-8859-1")
    response.encoding = "utf-8"
    response.headers["Content-Type"] = "text/html; charset=ISO-8859-1"
    return response


class QueryTargetTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_default_targets_include_dc_and_international(self):
        self.assertTrue(hasattr(fetch_contracts, "QueryTarget"))

        targets = TARGETS
        self.assertEqual(52, len(targets))
        self.assertEqual(
            {
                "AK": "02",
                "AL": "01",
                "AR": "05",
                "AZ": "04",
                "CA": "06",
                "CO": "08",
                "CT": "09",
                "DC": "11",
                "DE": "10",
                "FL": "12",
                "GA": "13",
                "HI": "15",
                "IA": "19",
                "ID": "16",
                "IL": "17",
                "IN": "18",
                "KS": "20",
                "KY": "21",
                "LA": "22",
                "MA": "25",
                "MD": "24",
                "ME": "23",
                "MI": "26",
                "MN": "27",
                "MO": "29",
                "MS": "28",
                "MT": "30",
                "NC": "37",
                "ND": "38",
                "NE": "31",
                "NH": "33",
                "NJ": "34",
                "NM": "35",
                "NV": "32",
                "NY": "36",
                "OH": "39",
                "OK": "40",
                "OR": "41",
                "PA": "42",
                "RI": "44",
                "SC": "45",
                "SD": "46",
                "TN": "47",
                "TX": "48",
                "UT": "49",
                "VA": "51",
                "VT": "50",
                "WA": "53",
                "WI": "55",
                "WV": "54",
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

    def test_build_post_data_uses_target_values(self):
        domestic = {
            "bus_cat": "ALL",
            "fy": "FY 26",
            "recovery": "0",
            "v_center": "ALL",
            "v_database": "FY26",
            "v_district": "ALL",
            "v_end_date": "2026-09-30",
            "v_start_date": "2025-10-01",
            "action": "Export to Excel",
        }
        cases = (
            ("AK", {"v_code": "02", "v_state": "ALASKA", "v_state2": "AK"}),
            ("DC", {"v_code": "11", "v_state": "WASHINGTON D.C.", "v_state2": "DC"}),
            (
                "International",
                {
                    "bus_cat": "",
                    "recovery": "",
                    "v_code": "xx",
                    "v_district": "",
                    "v_state": "OUTSIDE US",
                    "v_state2": "WORLD",
                },
            ),
        )

        for state, expected in cases:
            with self.subTest(state=state):
                self.assertEqual(
                    {**domestic, **expected},
                    self.fetcher._build_post_data(2026, TARGETS[state]),
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
        modern = (
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
            "TAS Code",
            "Solicitation ID",
            "Solicitation POC",
            "Description",
        )

        self.assertEqual(legacy, fetch_contracts.source_header_for_year(2005))
        self.assertEqual(legacy, fetch_contracts.source_header_for_year(2008))
        self.assertEqual(modern, fetch_contracts.source_header_for_year(2009))
        self.assertEqual(modern, fetch_contracts.source_header_for_year(2026))

    def test_source_schema_rejects_fiscal_years_before_fy2005(self):
        with self.assertRaises(ValueError):
            fetch_contracts.source_header_for_year(2004)


class DistrictTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_districts_follow_source_tokens(self):
        cases = (
            ("MT", "BOZEMAN, MT (District 00)", "MT-00"),
            ("MT", "BOZEMAN, MT (District 01)", "MT-01"),
            ("MT", "MISSOULA, MT (District 02)", "MT-02"),
            ("DC", "WASHINGTON, DC (District 98)", "DC-98"),
            ("TX", "HOUSTON, TX", ""),
            ("International", "GERMANY", ""),
        )

        for state, place_of_performance, expected in cases:
            with self.subTest(state=state, place=place_of_performance):
                self.assertEqual(
                    expected,
                    self.fetcher._determine_district(
                        TARGETS[state], place_of_performance
                    ),
                )

    def test_invalid_district_tokens_are_not_emitted(self):
        for place_of_performance in (
            "BOZEMAN, MT (District 1)",
            "BOZEMAN, MT (District ABC)",
            "BOZEMAN, MT (District NA)",
            "BOZEMAN, MT (District 99)",
        ):
            with self.subTest(place=place_of_performance):
                self.assertEqual(
                    "",
                    self.fetcher._determine_district(
                        TARGETS["MT"], place_of_performance
                    ),
                )


class ResponseParsingTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_domestic_response_preserves_text_and_reorders_semantic_columns(self):
        source_row = modern_source_row()
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [source_row]
        )

        rows = self.fetcher._parse_response(2026, TARGETS["MT"], response_text)

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
            2026, TARGETS["International"], response_text
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

        rows = self.fetcher._parse_response(2008, TARGETS["MT"], response_text)

        self.assertEqual(16, len(rows[0]))
        self.assertEqual('MIXED Case AS "Quoted"  ', rows[0][-1])

    def test_unexpected_header_is_rejected(self):
        bad_header = list(fetch_contracts.MODERN_SOURCE_HEADER)
        bad_header[11] = "Unexpected Column"
        response_text = make_export_response(bad_header, [modern_source_row()])

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(2026, TARGETS["MT"], response_text)

    def test_bad_row_width_is_rejected(self):
        short_row = modern_source_row()[:-1]
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [short_row]
        )

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(2026, TARGETS["MT"], response_text)

    def test_reported_record_count_mismatch_is_rejected(self):
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER,
            [modern_source_row()],
            reported_count=2,
        )

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(2026, TARGETS["MT"], response_text)

    def test_rejected_query_page_is_rejected(self):
        # NPDV answers a malformed query with an error page instead of an export.
        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(
                2026, TARGETS["MT"], "<html>Invalid Entry - please try again</html>"
            )

    def test_missing_record_count_is_rejected(self):
        response_text = "\n".join(
            [
                "STATE OF MONTANA",
                "\t".join(fetch_contracts.MODERN_SOURCE_HEADER),
                "\t".join(modern_source_row()),
            ]
        )

        with self.assertRaises(fetch_contracts.DataValidationError):
            self.fetcher._parse_response(2026, TARGETS["MT"], response_text)


class NPDVSourceFidelityTests(unittest.TestCase):
    """Parse real NPDV rows and compare against the committed CSV output."""

    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.fetcher = fetch_contracts.NASADataFetcher(
            fetch_contracts.Config(output_dir=self.output_dir.name)
        )

    def test_modern_row_matches_committed_output(self):
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [NPDV_MODERN_SOURCE_ROW]
        )

        rows = self.fetcher._parse_response(2026, TARGETS["AL"], response_text)

        self.assertEqual([NPDV_MODERN_OUTPUT_ROW], rows)

    def test_legacy_row_matches_committed_output(self):
        response_text = make_export_response(
            fetch_contracts.LEGACY_SOURCE_HEADER, [NPDV_LEGACY_SOURCE_ROW]
        )

        rows = self.fetcher._parse_response(2005, TARGETS["VT"], response_text)

        self.assertEqual([NPDV_LEGACY_OUTPUT_ROW], rows)

    def test_award_type_and_indicator_columns_stay_oriented(self):
        # Every committed row has " - " in the indicator column and none in the
        # award type column; the parser's swap is what keeps that true.
        cases = (
            (2026, "AL", fetch_contracts.MODERN_SOURCE_HEADER, NPDV_MODERN_SOURCE_ROW),
            (2005, "VT", fetch_contracts.LEGACY_SOURCE_HEADER, NPDV_LEGACY_SOURCE_ROW),
        )

        for year, state, header, source_row in cases:
            with self.subTest(year=year):
                rows = self.fetcher._parse_response(
                    year, TARGETS[state], make_export_response(header, [source_row])
                )
                self.assertNotIn(" - ", rows[0][2 + header.index("Award Type")])
                self.assertIn(
                    " - ",
                    rows[0][2 + header.index("Contractor Type - Indicators")],
                )

    def test_currency_columns_become_whole_dollar_integers(self):
        header = fetch_contracts.MODERN_SOURCE_HEADER
        obligations = 2 + header.index("Obligations")
        change = 2 + header.index("Change in Award Value")
        cases = (
            ('"$0"', "0"),
            ('"$250"', "250"),
            ('"$-16,915"', "-16915"),
            ('"$1,234,567"', "1234567"),
        )

        for source_value, expected in cases:
            with self.subTest(source=source_value):
                source_row = list(NPDV_MODERN_SOURCE_ROW)
                source_row[8] = source_row[9] = source_value
                rows = self.fetcher._parse_response(
                    2026,
                    TARGETS["AL"],
                    make_export_response(header, [source_row]),
                )
                self.assertEqual(expected, rows[0][obligations])
                self.assertEqual(expected, rows[0][change])

    def test_unexpected_currency_value_is_rejected(self):
        for source_value in ('"1,000"', '"$1,000.50"', '""', '"N/A"'):
            with self.subTest(source=source_value):
                source_row = list(NPDV_MODERN_SOURCE_ROW)
                source_row[8] = source_value
                with self.assertRaises(fetch_contracts.DataValidationError):
                    self.fetcher._parse_response(
                        2026,
                        TARGETS["AL"],
                        make_export_response(
                            fetch_contracts.MODERN_SOURCE_HEADER, [source_row]
                        ),
                    )

    def test_place_of_performance_without_district_token(self):
        # NPDV reports "UNITED STATES, <ST>" for 3,273 committed rows.
        source_row = list(NPDV_MODERN_SOURCE_ROW)
        source_row[3] = '"UNITED STATES, AL"'
        response_text = make_export_response(
            fetch_contracts.MODERN_SOURCE_HEADER, [source_row]
        )

        rows = self.fetcher._parse_response(2026, TARGETS["AL"], response_text)

        self.assertEqual(["AL", ""], rows[0][:2])
        self.assertEqual("UNITED STATES, AL", rows[0][5])

    def test_international_rows_drop_domestic_district_tokens(self):
        # NPDV's Outside U.S. export reports domestic districts for some rows,
        # e.g. "GERMANY, MD (District 05)" for MICROWORKS GMBH in FY2008.
        source_row = list(NPDV_LEGACY_SOURCE_ROW)
        source_row[3] = '"GERMANY, MD (District 05)"'
        response_text = make_export_response(
            fetch_contracts.LEGACY_SOURCE_HEADER, [source_row], international=True
        )

        rows = self.fetcher._parse_response(
            2008, TARGETS["International"], response_text
        )

        self.assertEqual(["International", ""], rows[0][:2])
        self.assertEqual("GERMANY, MD (District 05)", rows[0][5])

    def test_embedded_quotes_survive_transport_decoding(self):
        # Real descriptions carry balanced quotes, and some carry an unbalanced
        # leading quote (FY2005 UNIV ALASKA FAIRBANKS, NAG55418).
        cases = (
            (
                '"SERVICE ENTITLED, "SYSTEMS MANAGEMENT TOOL DEVELOPMENT"."',
                'SERVICE ENTITLED, "SYSTEMS MANAGEMENT TOOL DEVELOPMENT".',
            ),
            (
                '""CASCADES-THE CHANGING AURORA: IN SITU AND CAMERA ANALYSIS"',
                '"CASCADES-THE CHANGING AURORA: IN SITU AND CAMERA ANALYSIS',
            ),
        )

        for source_value, expected in cases:
            with self.subTest(source=source_value):
                source_row = list(NPDV_LEGACY_SOURCE_ROW)
                source_row[-1] = source_value
                rows = self.fetcher._parse_response(
                    2005,
                    TARGETS["VT"],
                    make_export_response(
                        fetch_contracts.LEGACY_SOURCE_HEADER, [source_row]
                    ),
                )
                self.assertEqual(expected, rows[0][-1])


class AtomicFetchTests(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.output_dir.cleanup)
        self.mt = TARGETS["MT"]
        self.international = TARGETS["International"]

    def test_failed_target_does_not_replace_existing_file(self):
        destination = Path(self.output_dir.name) / "nasa_awards_2026.csv"
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
            fetcher.session,
            "post",
            side_effect=[mt_response, requests.ConnectionError("offline")],
        ):
            with self.assertRaises(requests.RequestException):
                fetcher.fetch_and_save_data()

        self.assertEqual(b"existing complete data\n", destination.read_bytes())
        self.assertEqual([destination], list(Path(self.output_dir.name).iterdir()))

    def test_validation_failure_does_not_replace_existing_file(self):
        destination = Path(self.output_dir.name) / "nasa_awards_2026.csv"
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
            fetcher.session,
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
                make_export_response(fetch_contracts.MODERN_SOURCE_HEADER, [mt_row])
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

        with mock.patch.object(fetcher.session, "post", side_effect=responses):
            fetcher.fetch_and_save_data()

        destination = Path(self.output_dir.name) / "nasa_awards_2026.csv"
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
