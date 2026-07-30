import contextlib
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import award_stats


class AwardStatsTests(unittest.TestCase):
    def test_legacy_award_types_use_trailing_descriptor(self):
        with tempfile.TemporaryDirectory() as data_dir_name:
            csv_path = Path(data_dir_name) / "nasa_awards_2005.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=award_stats.STATS_COLUMNS)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "Award Date": "10/01/2004",
                            "Obligations": "100",
                            "Contract/Mod Number": (
                                "CONTRACT-1 Modification 0 (Base Record)"
                            ),
                            "Award Type": "Small Business,, Firm Fixed Price",
                        },
                        {
                            "Award Date": "10/02/2004",
                            "Obligations": "200",
                            "Contract/Mod Number": (
                                "GRANT-1 Modification 0 (Base Record)"
                            ),
                            "Award Type": (
                                "Educational Institution,, Grant For Research"
                            ),
                        },
                        {
                            "Award Date": "10/03/2004",
                            "Obligations": "300",
                            "Contract/Mod Number": (
                                "OTHER-1 Modification 0 (Base Record)"
                            ),
                            "Award Type": "[No Vendor Indicators Found], Other",
                        },
                        {
                            "Award Date": "10/04/2004",
                            "Obligations": "400",
                            "Contract/Mod Number": (
                                "CONTRACT-2 Modification 0 (Base Record)"
                            ),
                            "Award Type": (
                                "[No Vendor Indicators Found], "
                                "Fixed Price Redetermination"
                            ),
                        },
                    ]
                )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                export = award_stats.process_fiscal_year(
                    2005,
                    Path(data_dir_name),
                    export=True,
                )

        self.assertEqual(2, export["October"]["contract_count"])
        self.assertEqual(500, export["October"]["contract_value"])
        self.assertEqual(1, export["October"]["grant_count"])
        self.assertEqual(200, export["October"]["grant_value"])
        self.assertIn(
            "remain Other and are excluded from exported contract/grant columns",
            output.getvalue(),
        )

    def test_modern_award_types_still_use_leading_vehicle(self):
        self.assertEqual(
            "Contracts",
            award_stats.get_award_category(
                "Delivery Order, Firm Fixed Price",
                fiscal_year=2009,
            ),
        )
        self.assertEqual(
            "Other",
            award_stats.get_award_category(
                "Other, Firm Fixed Price",
                fiscal_year=2009,
            ),
        )

    def test_missing_file_warning_uses_awards_filename(self):
        with tempfile.TemporaryDirectory() as data_dir_name:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                award_stats.process_fiscal_year(
                    2026,
                    Path(data_dir_name),
                )

        self.assertIn("nasa_awards_2026.csv not found", output.getvalue())

    def test_export_argument_requires_and_returns_a_path(self):
        argv = [
            "award_stats.py",
            "--fys",
            "2026",
            "--export",
            "local_dir/output_name.csv",
        ]
        try:
            with patch.object(sys, "argv", argv):
                args = award_stats.parse_arguments()
        except SystemExit as error:
            self.fail(f"--export path was rejected with status {error.code}")

        self.assertEqual(Path("local_dir/output_name.csv"), args.export)

    def test_bare_export_retains_generated_filename(self):
        argv = ["award_stats.py", "--fys", "2026", "2024", "--export"]
        try:
            with patch.object(sys, "argv", argv):
                args = award_stats.parse_arguments()
            output_path = award_stats.resolve_export_path(args.export, args.fys)
        except (AttributeError, SystemExit) as error:
            self.fail(f"bare --export compatibility was lost: {error}")

        self.assertEqual(Path("new_awards_2024_to_2026.csv"), output_path)

    def test_export_writes_exact_path_and_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as output_dir_name:
            output_path = (
                Path(output_dir_name) / "nested" / "reports" / "custom-name.csv"
            )
            all_data = {
                2026: {
                    "October": {
                        "contract_count": 2,
                        "contract_value": 123456,
                        "grant_count": 1,
                        "grant_value": 789,
                    }
                }
            }

            try:
                result = award_stats.create_combined_awards_csv(
                    all_data,
                    [2026, 9999],
                    output_path,
                )
            except TypeError as error:
                self.fail(f"custom output path was rejected: {error}")

            self.assertEqual(output_path, result)
            self.assertTrue(output_path.is_file())
            with output_path.open(newline="", encoding="utf-8") as csvfile:
                rows = list(csv.DictReader(csvfile))

            self.assertNotIn("FY 9999 New Contract Awards", rows[0])
            self.assertEqual("2", rows[0]["FY 2026 New Contract Awards"])
            self.assertEqual("123456", rows[0]["FY 2026 Contract Awards Value"])

    def test_export_fails_when_no_requested_year_has_data(self):
        with tempfile.TemporaryDirectory() as output_dir_name:
            output_path = Path(output_dir_name) / "should-not-exist.csv"
            argv = [
                "award_stats.py",
                "--fys",
                "9999",
                "--export",
                str(output_path),
            ]

            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(
                    SystemExit,
                    "No fiscal-year data available",
                ):
                    award_stats.main()

            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
