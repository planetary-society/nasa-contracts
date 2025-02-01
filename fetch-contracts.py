#!/usr/bin/env python3
"""
A Python script to query NASA contract data for specified fiscal years,
apply custom transformations, and write the returned data (for all states)
to a single CSV file with "State" and "District" columns prepended.

Transformations applied:
    1. Swap the columns for Award Type (index 6) and Contractor Type - Indicators (index 7).
    2. Convert Description (index 14) to sentence case.
    3. Remove extra surrounding quotes from certain fields.

Intended usage in a GitHub repository:
    - CSV files are written to a configurable output directory (e.g. data/)
    - A GitHub Action may regularly run this script (or a wrapper) to update the CSV files.
"""

import os
import csv
import logging
import re
import requests
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Pattern, Optional
import argparse
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# A constant list of default states: all 50 states + DC, PR, VI.
DEFAULT_STATES: List[Tuple[str, str]] = [
    ("AK", "Alaska"), ("AL", "Alabama"), ("AR", "Arkansas"), ("AZ", "Arizona"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DC", "District of Columbia"),
    ("DE", "Delaware"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
    ("IA", "Iowa"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("MA", "Massachusetts"),
    ("MD", "Maryland"), ("ME", "Maine"), ("MI", "Michigan"), ("MN", "Minnesota"),
    ("MO", "Missouri"), ("MS", "Mississippi"), ("MT", "Montana"), ("NC", "North Carolina"),
    ("ND", "North Dakota"), ("NE", "Nebraska"), ("NH", "New Hampshire"), ("NJ", "New Jersey"),
    ("NM", "New Mexico"), ("NV", "Nevada"), ("NY", "New York"), ("OH", "Ohio"),
    ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("PR", "Puerto Rico"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"),
    ("TX", "Texas"), ("UT", "Utah"), ("VA", "Virginia"), ("VI", "Virgin Islands"),
    ("VT", "Vermont"), ("WA", "Washington"), ("WI", "Wisconsin"), ("WV", "West Virginia"),
    ("WY", "Wyoming")
]


@dataclass
class Config:
    """
    Configuration for NASA data retrieval and CSV export.
    """
    output_base_filename: str = "nasa_contracts"    # Base name for the output file.
    output_dir: str = "data"                          # Default output directory.
    fiscal_years: List[int] = field(default_factory=list)  # e.g. [2025]
    states: List[Tuple[str, str]] = field(default_factory=list)
    url: str = "https://prod.nais.nasa.gov/cgibin/npdv/usmap05.cgi"
    normalizer_reference_filepath: str = None

    def __post_init__(self) -> None:
        if not self.states:
            self.states = DEFAULT_STATES
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

class TextNormalizer:
    """
    A class for normalizing NASA acronyms and definitions in a given text.

    This class loads a reference CSV file (expected to have "Acronym" and "Definition" columns)
    that contains NASA acronyms and their corresponding definitions. It then uses this data to
    replace any occurrences of these phrases in the text with their properly capitalized forms.
    """

    def __init__(self, csv_filepath: Optional[str]) -> None:
        """
        Initialize the AcronymNormalizer with the provided CSV file, or None if not using one.

        Args:
            csv_filepath: Path to the CSV file containing NASA acronyms and definitions.
        """
        self.mapping: Dict[str, str] = {}
        self.pattern: Pattern[str] = None  # Will be set after loading data.
        if csv_filepath:
            self._load_data(csv_filepath)

    def _load_data(self, filepath: str) -> None:
        """
        Load acronyms and definitions from the given CSV file into a lookup dictionary and compile
        a regex pattern for fast matching.

        The CSV file is expected to have headers "Acronym" and "Definition".

        Args:
            filepath: Path to the CSV file.
        """
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                acronym = row.get("Acronym", "").strip()
                definition = row.get("Definition", "").strip()
                if acronym:
                    # Store acronym with its proper capitalization
                    self.mapping[acronym.lower()] = acronym.upper()
                if definition:
                    # Also map the definition (phrase) in its proper capitalization.
                    self.mapping[definition.lower()] = definition

        # Sort keys by length descending to ensure longer phrases are matched before shorter ones.
        sorted_keys = sorted(self.mapping.keys(), key=len, reverse=True)
        # Build a regex pattern that matches any key.
        # Using negative lookbehind/lookahead ensures we match whole words/phrases.
        # Note: Adjust the boundaries if your data may include punctuation or non-alphanumeric context.
        pattern_str = r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, sorted_keys)) + r")(?![A-Za-z0-9])"
        self.pattern = re.compile(pattern_str, re.IGNORECASE)

    @staticmethod
    def _sentence_case(text: str) -> str:
        """
        Convert text to sentence case: first letter uppercase, rest lowercase,
        while correcting common abbreviations (e.g., "u.s." -> "U.S.").
        
        Args:
            text: The input text to be converted.
        
        Returns:
            A sentence-cased version of the text with corrected abbreviation casing.
        """
        text = text.strip()
        if not text:
            return text

        # Convert the entire text to lowercase.
        text_lower = text.lower()

        # Capitalize the first character.
        sentence_cased = text_lower[0].upper() + text_lower[1:]

        # Define a dictionary for abbreviations that require special casing.
        abbreviation_fixes = {
            "u.s.": "U.S.",
            "ii": "II",
            "iii": "III"
        }
        
        # Add all relevant fiscal years
        current_year = datetime.datetime.now().year
        for fy in range(2005, current_year + 1):
            fy_str = str(current_year)[2:]
            abbreviation_fixes[f"fy{fy_str}"] = f"FY{fy_str}"

        # Replace each abbreviation in the text using a case-insensitive search.
        for wrong, correct in abbreviation_fixes.items():
            # The \b ensures that we match whole words (or phrases) only.
            pattern = r'\b' + re.escape(wrong) + r'\b'
            sentence_cased = re.sub(pattern, correct, sentence_cased, flags=re.IGNORECASE)

        return sentence_cased

    def normalize(self, text: str) -> str:
        """
        Replace occurrences of known NASA acronyms and definitions in the provided text with their
        properly capitalized forms.

        Args:
            text: The input text (e.g., a contract description) to process.

        Returns:
            The text with all recognized phrases normalized.
        """
        
        text = self._sentence_case(text)
        
        # If no pattern was built (because no CSV file was provided), return text unchanged.
        if not self.pattern:
            return text

        def replacement(match: re.Match) -> str:
            matched_text = match.group(0)
            return self.mapping.get(matched_text.lower(), matched_text)

        return self.pattern.sub(replacement, text)

class NASADataFetcher:
    """
    Responsible for fetching NASA contract data and writing a transformed CSV.
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize with the given configuration.
        """
        self.config = config
        self.normalizer = TextNormalizer(self.config.normalizer_reference_filepath)
        
    @staticmethod
    def _sentence_case(text: str) -> str:
        """
        Convert text to sentence case: first letter uppercase, rest lowercase.
        """
        text = text.strip()
        if not text:
            return text
        return text[0].upper() + text[1:].lower()

    def _sanitize_row(self, row: List[str]) -> None:
        """
        Apply custom transformations on a row:
            - Swap Award Type (index 6) with Contractor Type - Indicators (index 7).
            - Remove extra quotes from selected fields.
            - Convert Description (index 14) to sentence case.
        """
        # Swap Award Type (6) and Contractor Type (7) if available
        if len(row) > 7:
            row[6], row[7] = row[7], row[6]

        # Indices to strip quotes from: Contractor (0), Place of Performance (3),
        # Award Type (6), Contractor Type (7), Obligations (8), Change in Award Value (9),
        # Solicitation POC (13), and Description (14).
        indices_to_strip = [0, 3, 6, 7, 8, 9, 13, 14]
        for i in indices_to_strip:
            if i < len(row):
                row[i] = row[i].strip('"')

        # Titleize the Contractor name
        if len(row) > 0:
            row[0] = row[0].title()
        
        # Sentence-case the description at index 14 and renormalize any standard acronyms or program names
        if len(row) > 14:
            row[14] = self.normalizer.normalize(row[14])

    def _build_post_data(self, year: int, st_code: str, st_name: str) -> dict:
        """
        Build the form data payload for the POST request.
        """
        fy_str = f"FY {str(year)[-2:]}"
        start_date = f"{year - 1}-10-01"
        end_date = f"{year}-09-30"

        return {
            'bus_cat': 'ALL',
            'fy': fy_str,
            'recovery': '0',
            'v_center': 'ALL',
            'v_database': fy_str.replace(" ", ""),
            'v_code': '53',
            'v_district': 'ALL',
            'v_end_date': end_date,
            'v_start_date': start_date,
            'v_state': st_name.upper(),
            'v_state2': st_code,
            'action': 'Export to Excel'
        }

    def _determine_district(self, st_code: str, place_of_performance: str) -> str:
        """
        Determine the congressional district string (e.g. "WA-07" or "MT-00").
        For at-large states (e.g. AK, WY, MT, ND, SD, VT, DE), always return XX-00.
        Otherwise, try to extract the district number from the place of performance.
        """
        at_large_states = {"AK", "WY", "MT", "ND", "SD", "VT", "DE"}
        if st_code in at_large_states:
            return f"{st_code}-00"

        # Attempt to extract two digits from the expected location in the string.
        if len(place_of_performance) >= 4:
            district_number = place_of_performance[-4:-2]
            if district_number.isdigit() and int(district_number) != 0:
                return f"{st_code}-{district_number}"
        return ""

    def fetch_and_save_data(self) -> None:
        """
        Fetch data for each fiscal year/state combination and write a single CSV file.
        """
        fy_part = "_".join(str(y) for y in self.config.fiscal_years)
        filename = f"{self.config.output_base_filename}_{fy_part}.csv"
        full_path = os.path.join(self.config.output_dir, filename)

        headers_written = False

        try:
            with open(full_path, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Loop through each fiscal year and state combination.
                for year in self.config.fiscal_years:
                    for st_code, st_name in self.config.states:
                        logging.info("Downloading contract data for %s...", st_name)
                        form_data = self._build_post_data(year, st_code, st_name)
                        try:
                            response = requests.post(
                                self.config.url,
                                data=form_data,
                                timeout=30  # seconds
                            )
                            response.raise_for_status()
                        except requests.RequestException as err:
                            logging.error("Request failed for %s: %s", st_name, err)
                            continue

                        # Check if response indicates an error
                        if "Invalid Entry" in response.text:
                            logging.warning("Invalid Entry for %s; skipping.", st_name)
                            continue

                        lines = response.text.splitlines()
                        if len(lines) < 7:
                            logging.warning("Unexpected response format for %s.", st_name)
                            continue

                        # Use enumerate to iterate over lines (starting at 1 for clarity)
                        for row_index, line in enumerate(lines, start=1):
                            # The 7th line is the NASA export header.
                            if row_index == 7:
                                if not headers_written:
                                    original_header = line.split("\t")
                                    new_header = ["State", "District"] + original_header
                                    writer.writerow(new_header)
                                    headers_written = True
                                continue

                            # Process data rows after the header.
                            if row_index > 7:
                                raw_data = line.split("\t")
                                district_str = ""
                                if len(raw_data) > 3:
                                    district_str = self._determine_district(st_code, raw_data[3])
                                self._sanitize_row(raw_data)
                                csv_row = [st_code, district_str] + raw_data
                                writer.writerow(csv_row)
                        logging.info("Finished. Found %d contracts", len(lines)-7)
            logging.info("File written to: %s", full_path)
        except IOError as err:
            logging.error("Failed to write CSV file: %s", err)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Fetch NASA contract data for the specified fiscal year(s) and export to CSV."
    )
    parser.add_argument(
        "-fy", "--fiscal-year",
        type=int,
        nargs="+",
        required=True,
        help="One or more 4-digit fiscal years (e.g., 2025)"
    )
    parser.add_argument(
        "-dir", "--output-dir",
        type=str,
        default="data",
        help="Output directory for CSV file (default: data)"
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
        output_base_filename="nasa_contracts",
        output_dir=args.output_dir,
        fiscal_years=args.fiscal_year,
        normalizer_reference_filepath="reference/nasa_acronyms.csv"
    )
    fetcher = NASADataFetcher(config)
    fetcher.fetch_and_save_data()


if __name__ == "__main__":
    main()