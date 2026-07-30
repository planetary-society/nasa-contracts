#!/usr/bin/env python3
"""
Fetch NASA Procurement Data View exports for specified fiscal years.

Each fiscal year is written to a separate CSV with derived State and District
columns and the two currency columns rewritten as plain whole-dollar integers.
Source field text is otherwise preserved verbatim.
"""

import argparse
import csv
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import List, Tuple

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass(frozen=True)
class QueryTarget:
    output_state: str
    request_state: str
    request_code: str
    request_state2: str
    international: bool = False


DEFAULT_TARGETS: List[QueryTarget] = [
    QueryTarget("AK", "ALASKA", "02", "AK"),
    QueryTarget("AL", "ALABAMA", "01", "AL"),
    QueryTarget("AR", "ARKANSAS", "05", "AR"),
    QueryTarget("AZ", "ARIZONA", "04", "AZ"),
    QueryTarget("CA", "CALIFORNIA", "06", "CA"),
    QueryTarget("CO", "COLORADO", "08", "CO"),
    QueryTarget("CT", "CONNECTICUT", "09", "CT"),
    QueryTarget("DC", "WASHINGTON D.C.", "11", "DC"),
    QueryTarget("DE", "DELAWARE", "10", "DE"),
    QueryTarget("FL", "FLORIDA", "12", "FL"),
    QueryTarget("GA", "GEORGIA", "13", "GA"),
    QueryTarget("HI", "HAWAII", "15", "HI"),
    QueryTarget("IA", "IOWA", "19", "IA"),
    QueryTarget("ID", "IDAHO", "16", "ID"),
    QueryTarget("IL", "ILLINOIS", "17", "IL"),
    QueryTarget("IN", "INDIANA", "18", "IN"),
    QueryTarget("KS", "KANSAS", "20", "KS"),
    QueryTarget("KY", "KENTUCKY", "21", "KY"),
    QueryTarget("LA", "LOUISIANA", "22", "LA"),
    QueryTarget("MA", "MASSACHUSETTS", "25", "MA"),
    QueryTarget("MD", "MARYLAND", "24", "MD"),
    QueryTarget("ME", "MAINE", "23", "ME"),
    QueryTarget("MI", "MICHIGAN", "26", "MI"),
    QueryTarget("MN", "MINNESOTA", "27", "MN"),
    QueryTarget("MO", "MISSOURI", "29", "MO"),
    QueryTarget("MS", "MISSISSIPPI", "28", "MS"),
    QueryTarget("MT", "MONTANA", "30", "MT"),
    QueryTarget("NC", "NORTH CAROLINA", "37", "NC"),
    QueryTarget("ND", "NORTH DAKOTA", "38", "ND"),
    QueryTarget("NE", "NEBRASKA", "31", "NE"),
    QueryTarget("NH", "NEW HAMPSHIRE", "33", "NH"),
    QueryTarget("NJ", "NEW JERSEY", "34", "NJ"),
    QueryTarget("NM", "NEW MEXICO", "35", "NM"),
    QueryTarget("NV", "NEVADA", "32", "NV"),
    QueryTarget("NY", "NEW YORK", "36", "NY"),
    QueryTarget("OH", "OHIO", "39", "OH"),
    QueryTarget("OK", "OKLAHOMA", "40", "OK"),
    QueryTarget("OR", "OREGON", "41", "OR"),
    QueryTarget("PA", "PENNSYLVANIA", "42", "PA"),
    QueryTarget("RI", "RHODE ISLAND", "44", "RI"),
    QueryTarget("SC", "SOUTH CAROLINA", "45", "SC"),
    QueryTarget("SD", "SOUTH DAKOTA", "46", "SD"),
    QueryTarget("TN", "TENNESSEE", "47", "TN"),
    QueryTarget("TX", "TEXAS", "48", "TX"),
    QueryTarget("UT", "UTAH", "49", "UT"),
    QueryTarget("VA", "VIRGINIA", "51", "VA"),
    QueryTarget("VT", "VERMONT", "50", "VT"),
    QueryTarget("WA", "WASHINGTON", "53", "WA"),
    QueryTarget("WI", "WISCONSIN", "55", "WI"),
    QueryTarget("WV", "WEST VIRGINIA", "54", "WV"),
    QueryTarget("WY", "WYOMING", "56", "WY"),
    QueryTarget("International", "OUTSIDE US", "xx", "WORLD", True),
]

LEGACY_SOURCE_HEADER = (
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
MODERN_SOURCE_HEADER = (
    LEGACY_SOURCE_HEADER[:11] + ("TAS Code",) + LEGACY_SOURCE_HEADER[11:]
)

# Columns NPDV reports as whole-dollar currency text, e.g. "$0" or "$-16,915".
CURRENCY_COLUMNS = ("Obligations", "Change in Award Value")
CURRENCY_PATTERN = re.compile(r"\$(-?[\d,]+)")


def source_header_for_year(year: int) -> Tuple[str, ...]:
    if year < 2005:
        raise ValueError("NPDV contract exports are supported from FY2005 onward")
    return LEGACY_SOURCE_HEADER if year <= 2008 else MODERN_SOURCE_HEADER


class DataValidationError(RuntimeError):
    """Raised when an NPDV export cannot be validated safely."""


@dataclass
class Config:
    """Configuration for NASA data retrieval and CSV export."""

    output_base_filename: str = "nasa_contracts"
    output_dir: str = "data"
    fiscal_years: List[int] = field(default_factory=list)
    targets: List[QueryTarget] = field(default_factory=lambda: list(DEFAULT_TARGETS))
    url: str = "https://prod.nais.nasa.gov/cgibin/npdv/usmap05.cgi"

    def __post_init__(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)


class NASADataFetcher:
    """Fetch and validate NASA contract data before atomically writing CSVs."""

    def __init__(self, config: Config) -> None:
        self.config = config
        # One session so the 52 targets of each fiscal year reuse a connection.
        self.session = requests.Session()

    def _build_post_data(self, year: int, target: QueryTarget) -> dict:
        """
        Build the form data payload for the POST request.
        """
        fy_str = f"FY {str(year)[-2:]}"
        start_date = f"{year - 1}-10-01"
        end_date = f"{year}-09-30"

        return {
            "bus_cat": "" if target.international else "ALL",
            "fy": fy_str,
            "recovery": "" if target.international else "0",
            "v_center": "ALL",
            "v_database": fy_str.replace(" ", ""),
            "v_code": target.request_code,
            "v_district": "" if target.international else "ALL",
            "v_end_date": end_date,
            "v_start_date": start_date,
            "v_state": target.request_state,
            "v_state2": target.request_state2,
            "action": "Export to Excel",
        }

    def _determine_district(
        self, target: QueryTarget, place_of_performance: str
    ) -> str:
        """
        Determine the congressional district string from the source-reported token.
        """
        if target.international:
            return ""

        # Congressional districts are two-digit numbers: 00 for an at-large
        # jurisdiction through 98 for the District of Columbia's delegate seat.
        match = re.search(
            r"\(District\s+([0-8]\d|9[0-8])\)\s*$",
            place_of_performance,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        return f"{target.output_state}-{match.group(1)}"

    @staticmethod
    def _unwrap_source_field(value: str) -> str:
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    def _parse_response(
        self, year: int, target: QueryTarget, response_text: str
    ) -> List[List[str]]:
        if "Invalid Entry" in response_text:
            raise DataValidationError(
                f"NPDV rejected the request for {target.output_state}"
            )

        count_match = re.search(
            r"([\d,]+)\s+Records?\s+found",
            response_text,
            flags=re.IGNORECASE,
        )
        if not count_match:
            raise DataValidationError(f"Missing record count for {target.output_state}")
        reported_count = int(count_match.group(1).replace(",", ""))

        expected_header = source_header_for_year(year)
        lines = [
            line[:-1] if line.endswith("\r") else line
            for line in response_text.split("\n")
        ]
        for header_index, line in enumerate(lines):
            fields = tuple(line.split("\t"))
            if fields[:2] != expected_header[:2]:
                continue
            if fields != expected_header:
                raise DataValidationError(
                    f"Unexpected FY{year} schema for {target.output_state}"
                )
            break
        else:
            raise DataValidationError(
                f"Missing FY{year} export header for {target.output_state}"
            )

        place_index = expected_header.index("Place of Performance")
        award_type_index = expected_header.index("Award Type")
        indicator_index = expected_header.index("Contractor Type - Indicators")
        currency_indices = [expected_header.index(name) for name in CURRENCY_COLUMNS]

        parsed_rows: List[List[str]] = []
        for line_number, line in enumerate(
            lines[header_index + 1 :], start=header_index + 2
        ):
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != len(expected_header):
                raise DataValidationError(
                    f"FY{year} {target.output_state} line {line_number} has "
                    f"{len(fields)} fields; expected {len(expected_header)}"
                )

            fields = [self._unwrap_source_field(value) for value in fields]
            # The export emits these two columns' values in the opposite order
            # from its own header row.
            fields[award_type_index], fields[indicator_index] = (
                fields[indicator_index],
                fields[award_type_index],
            )
            for index in currency_indices:
                match = CURRENCY_PATTERN.fullmatch(fields[index])
                if not match:
                    raise DataValidationError(
                        f"FY{year} {target.output_state} line {line_number} has "
                        f"unexpected {expected_header[index]} value "
                        f"{fields[index]!r}"
                    )
                fields[index] = match.group(1).replace(",", "")

            district = self._determine_district(target, fields[place_index])
            parsed_rows.append([target.output_state, district] + fields)

        if len(parsed_rows) != reported_count:
            raise DataValidationError(
                f"FY{year} {target.output_state} reported {reported_count} "
                f"records but yielded {len(parsed_rows)} rows"
            )
        return parsed_rows

    def fetch_target(self, year: int, target: QueryTarget) -> List[List[str]]:
        """Request one target's export for one fiscal year and validate its rows."""
        response = self.session.post(
            self.config.url,
            data=self._build_post_data(year, target),
            timeout=30,
        )
        response.raise_for_status()
        return self._parse_response(year, target, response.content.decode("ISO-8859-1"))

    def fetch_and_save_data(self) -> None:
        """Fetch every configured target and atomically publish each fiscal year."""
        # Resolve every schema first so an unsupported year fails before any
        # file is written.
        headers = {
            year: source_header_for_year(year) for year in self.config.fiscal_years
        }
        for year, expected_header in headers.items():
            filename = f"{self.config.output_base_filename}_{year}.csv"
            full_path = os.path.join(self.config.output_dir, filename)
            temporary = tempfile.NamedTemporaryFile(
                mode="w",
                newline="",
                encoding="utf-8",
                prefix=f".{filename}.",
                suffix=".tmp",
                dir=self.config.output_dir,
                delete=False,
            )
            temporary_path = temporary.name
            try:
                with temporary as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["State", "District"] + list(expected_header))

                    for target in self.config.targets:
                        logging.info(
                            "Downloading contract data for %s in fiscal year %s...",
                            target.output_state,
                            year,
                        )
                        rows = self.fetch_target(year, target)
                        writer.writerows(rows)
                        logging.info(
                            "Finished %s for fiscal year %s. Found %d records",
                            target.output_state,
                            year,
                            len(rows),
                        )

                    csvfile.flush()
                    os.fsync(csvfile.fileno())

                os.replace(temporary_path, full_path)
                logging.info("File written to: %s", full_path)
            except BaseException:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
                raise


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Fetch NASA contract data for the specified fiscal year(s) and export to CSV."
    )
    parser.add_argument(
        "-fy",
        "--fiscal-year",
        type=int,
        nargs="+",
        required=True,
        help="One or more 4-digit fiscal years (e.g., 2025)",
    )
    parser.add_argument(
        "-dir",
        "--output-dir",
        type=str,
        default="data",
        help="Output directory for CSV file (default: data)",
    )
    return parser.parse_args()


def main() -> None:
    """
    Main entry point: parse arguments and run the data fetcher.
    """
    args = parse_args()
    logging.info("Fetching NASA contracts for fiscal year(s): %s", args.fiscal_year)

    # Construct configuration.
    config = Config(
        output_dir=args.output_dir,
        fiscal_years=args.fiscal_year,
    )
    fetcher = NASADataFetcher(config)
    fetcher.fetch_and_save_data()


if __name__ == "__main__":
    main()
