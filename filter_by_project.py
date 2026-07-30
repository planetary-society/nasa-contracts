#!/usr/bin/env python3
"""
Script to filter large NASA contract CSVs by project-specific keyword batches using chunked processing,
without triggering the “has match groups” warning.

This script will:
  1. Read each configured data/nasa_awards_{year}.csv file once in chunks.
  2. Build searchable row text once per chunk and prefilter rows that match any project keyword.
  3. Apply each project's positive and negative keywords to that smaller candidate set.
  4. Accumulate matches across years and write separate contract and grant CSVs per project.

Dependencies:
  - pandas
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Tuple
import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the projects and their keyword batches.
PROJECTS = {
    "DAVINCI": [
        "DAVINCI+",
        "Deep Atmosphere Venus Investigation of Noble gases, Chemistry, and Imaging",
    ],
    "MSR": ["MSR", "Mars Sample Return"],
    "Chandra": ["Chandra"],
    "MRO": ["MRO", "Mars Reconnaissance Orbiter", "~subscription"],
    "Juno": ["Juno", "~check valve"],
    "Roman": [
        "Roman",
        "Roman Space Telescope",
        "Nancy Grace Roman Space Telescope",
        "WFIRST",
        "Wide Field Infrared Survey Telescope",
    ],
    "New Horizons": ["New Horizons", "~New Horizons Aeronautics, Llc"],
    "MAVEN": ["MAVEN", "Mars Atmosphere and Volatile EvolutioN"],
    "OSIRIS-APEX": ["OSIRIS-APEX", "Apophis Explorer"],
    "Mars Express": ["Mars Express"],
    "Perseverance": ["Perseverance", "Mars 2020", "M2020", "Mars2020"],
    "Mars Odyssey": ["ODY", "Mars Odyssey", "Odyssey", "~Odyssey Space Research"],
    "VERITAS": [
        "VERITAS",
        "Venus Emissivity, Radio Science, InSAR, Topography, and Spectroscopy",
        "~netbackup",
        "~netback up",
        "~Metgreen Solutions Inc",
        "~software",
        "~maintenance",
        "~consulting services",
        "~renew",
        "~licenses",
        "~renewal",
    ],
    "SAGE-III": [
        "SAGE-III",
        "Stratospheric Aerosol and Gas Experiment III",
        "SAGE III",
    ],
    "DSCOVR": [
        "DSCOVR",
        "Deep Space Climate Observatory",
        "DSCOVR EPIC",
        "DSCOVR NISTAR",
    ],
    "Terra": [
        "Terra",
        "Terra EOS",
        "~Terra Ferma Llc",
        "~A-Terra Llc",
        "~Terra Universal, Inc.",
        "~Terra Research Inc.",
        "~gas analyzer",
        "~purge cabinet",
    ],
    "Aqua": ["Aqua"],
    "Aura": ["Aura"],
    "JWST": ["JWST", "James Webb Space Telescope"],
    "OCO-3": ["OCO-3", "Orbiting Carbon Observatory-3", "OCO3"],
    "OCO-2": ["OCO-2", "Orbiting Carbon Observatory-2", "OCO2"],
    "GOLD": ["GOLD", "Global-scale Observations of the Limb and Disk"],
    "Hinode": ["Hinode", "Solar-B", "Hinode NASA"],
    "IBEX": ["IBEX", "Interstellar Boundary Explorer", "~business"],
    "MMS": ["MMS", "Magnetospheric Multiscale"],
    "THEMIS_ARTEMIS": ["THEMIS", "THEMIS-ARTEMIS"],
    "TIMED": ["TIMED", "Thermosphere Ionosphere Mesosphere Energetics Dynamics"],
    "VIPER": [
        "VIPER",
        "Volatiles Investigating Polar Exploration Rover",
        "~versatile imager platform",
        "~VIPER machine",
        "~3d systems",
        "~vxworks VIPER",
        "~VIPER fabrication services",
        "~Eo14042",
        "~warranty",
        "~licenses",
        "~renewal",
    ],
    "Rosalind_Franklin_Rover": [
        "Rosalind Franklin",
        "ExoMars",
        "~trace gas orbiter",
        "~TGO",
    ],
    "COSI": ["COSI", "Compton Spectrometer and Imager"],
    "LISA": ["LISA", "Laser Interferometer Space Antenna", "LISA-T"],
    "ULTRASAT": [
        "ULTRASAT",
        "Ultraviolet Transient Astronomy Satellite",
    ],
    "ARIEL": ["Atmospheric Remote-sensing Infrared Exoplanet Large-survey", "ARIEL"],
    "Pioneers_Missions": ["PUEO", "Pandora", "Aspera", "StarBurst", "TIGERISS"],
    "SBG-VSWIR": [
        "SBG-VSWIR",
        "Surface Biology and Geology VSWIR",
        "VSWIR Spectrometer",
    ],
    "PMM": ["PMM", "Global Precipitation Measurement Mission"],
    "Landsat_Next": ["Landsat Next", "Landsat-Next"],
    "SBG-TIR": ["SBG-TIR", "Surface Biology and Geology TIR", "TIR Radiometer"],
    "EUVST": ["EUVST", "EUV Solar Telescope"],
    "HelioSwarm": ["HelioSwarm", "Helio Swarm"],
    "HERMES": ["HERMES", "Heliospheric Relay and Monitoring Experiment"],
    "GDC": ["GDC", "Geospace Dynamics Constellation"],
    "UVEX": ["UVEX", "Ultraviolet Explorer"],
}

# Number of rows per chunk. Adjust based on your available memory.
CHUNK_SIZE = 100_000


def compile_keyword_pattern(keywords: list[str]) -> Optional[re.Pattern[str]]:
    """Compile keywords into the whole-word, case-insensitive regex used for matching."""
    if not keywords:
        return None

    escaped_keywords = [re.escape(keyword) for keyword in keywords]
    return re.compile(r"(?i)\b(?:" + "|".join(escaped_keywords) + r")\b")


def compile_project_patterns(
    projects: dict[str, list[str]],
) -> tuple[
    dict[str, tuple[Optional[re.Pattern[str]], Optional[re.Pattern[str]]]],
    Optional[re.Pattern[str]],
]:
    """Compile each project's include/exclude patterns and a shared candidate pattern."""
    project_patterns = {}
    all_positives = []

    for project_name, keywords in projects.items():
        positives = [keyword for keyword in keywords if not keyword.startswith("~")]
        negatives = [keyword[1:] for keyword in keywords if keyword.startswith("~")]
        all_positives.extend(positives)
        project_patterns[project_name] = (
            compile_keyword_pattern(positives),
            compile_keyword_pattern(negatives),
        )

    # Avoid making the shared regex larger than necessary when projects reuse terms.
    unique_positives = list(dict.fromkeys(all_positives))
    return project_patterns, compile_keyword_pattern(unique_positives)


def build_search_text(df_chunk: pd.DataFrame) -> pd.Series:
    """Combine searchable columns once for each row in a CSV chunk."""
    return (
        df_chunk.drop(columns=["Contractor"], errors="ignore")
        .astype(str)
        .agg(" ".join, axis=1)
    )


def build_pattern_mask(
    row_strings: pd.Series,
    positive_pattern: Optional[re.Pattern[str]],
    negative_pattern: Optional[re.Pattern[str]],
) -> pd.Series:
    """Build a positional boolean mask from compiled include/exclude patterns."""
    if positive_pattern is None:
        mask = pd.Series(True, index=row_strings.index)
    else:
        mask = row_strings.str.contains(positive_pattern, na=False)

    if negative_pattern is not None and mask.any():
        mask &= ~row_strings.str.contains(negative_pattern, na=False)

    return mask


def build_filter_mask(df_chunk: pd.DataFrame, keywords: list[str]) -> pd.Series:
    """
    Given a DataFrame chunk and a list of keywords (positives and negatives prefixed by "~"),
    return a boolean Series indicating which rows satisfy:
      - They match at least one positive keyword (case-insensitive).
      - They do NOT match any negative keyword.

    We convert each row to a single string and search using two compiled regexes:
      - pos_pattern matches any positive keyword as a whole word.
      - neg_pattern matches any negative keyword as a whole word.
    """
    positives = [kw for kw in keywords if not kw.startswith("~")]
    negatives = [kw[1:] for kw in keywords if kw.startswith("~")]
    row_strings = build_search_text(df_chunk)
    return build_pattern_mask(
        row_strings,
        compile_keyword_pattern(positives),
        compile_keyword_pattern(negatives),
    )


def filter_for_project_and_year(
    year: int, csv_path: Path, keywords: list[str]
) -> pd.DataFrame:
    """
    Read the specified CSV for a given year in chunks, filter rows matching the project's keywords,
    and return a concatenated DataFrame of all matching rows from all chunks.
    If the file does not exist or no matches, return an empty DataFrame.
    """
    if not csv_path.exists():
        print(f"Warning: {csv_path} not found. Skipping year {year}.", file=sys.stderr)
        return pd.DataFrame()

    positives = [keyword for keyword in keywords if not keyword.startswith("~")]
    negatives = [keyword[1:] for keyword in keywords if keyword.startswith("~")]
    positive_pattern = compile_keyword_pattern(positives)
    negative_pattern = compile_keyword_pattern(negatives)
    filtered_chunks = []

    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=CHUNK_SIZE):
        mask = build_pattern_mask(
            build_search_text(chunk),
            positive_pattern,
            negative_pattern,
        )
        if mask.any():
            matching_positions = mask.to_numpy().nonzero()[0]
            df_matched = chunk.iloc[matching_positions].copy()
            df_matched.insert(0, "Year", year)
            filtered_chunks.append(df_matched)

    if not filtered_chunks:
        return pd.DataFrame()

    return pd.concat(filtered_chunks, ignore_index=True)


def iter_project_matches_for_year(
    year: int,
    csv_path: Path,
    project_patterns: dict[
        str, tuple[Optional[re.Pattern[str]], Optional[re.Pattern[str]]]
    ],
    candidate_pattern: Optional[re.Pattern[str]],
) -> Iterator[tuple[str, pd.DataFrame]]:
    """Yield project matches while reading one year's CSV only once."""
    if not csv_path.exists():
        print(f"Warning: {csv_path} not found. Skipping year {year}.", file=sys.stderr)
        return

    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=CHUNK_SIZE):
        row_strings = build_search_text(chunk)
        if candidate_pattern is None:
            candidate_positions = row_strings.iloc[0:0].to_numpy().nonzero()[0]
        else:
            candidate_mask = row_strings.str.contains(candidate_pattern, na=False)
            candidate_positions = candidate_mask.to_numpy().nonzero()[0]

        for project_name, (
            positive_pattern,
            negative_pattern,
        ) in project_patterns.items():
            if positive_pattern is None:
                candidates = row_strings
                project_positions = range(len(row_strings))
            else:
                candidates = row_strings.iloc[candidate_positions]
                project_positions = candidate_positions

            mask = build_pattern_mask(
                candidates,
                positive_pattern,
                negative_pattern,
            )
            if mask.any():
                matching_offsets = mask.to_numpy().nonzero()[0]
                matching_positions = [
                    project_positions[offset] for offset in matching_offsets
                ]
                matched = chunk.iloc[matching_positions].copy()
                matched.insert(0, "Year", year)
                yield project_name, matched


def filter_projects_for_year(
    year: int,
    csv_path: Path,
    project_patterns: dict[
        str, tuple[Optional[re.Pattern[str]], Optional[re.Pattern[str]]]
    ],
    candidate_pattern: Optional[re.Pattern[str]],
) -> dict[str, pd.DataFrame]:
    """Collect one year's streamed project matches into DataFrames."""
    filtered_chunks = {project_name: [] for project_name in project_patterns}

    for project_name, matched in iter_project_matches_for_year(
        year,
        csv_path,
        project_patterns,
        candidate_pattern,
    ):
        filtered_chunks[project_name].append(matched)

    return {
        project_name: (
            pd.concat(project_chunks, ignore_index=True)
            if project_chunks
            else pd.DataFrame()
        )
        for project_name, project_chunks in filtered_chunks.items()
    }


def parse_mod_number(contract_mod_str: Optional[str]) -> Tuple[str, int]:
    """
    Parses a string potentially containing an award ID and a modification identifier.

    Handles formats like:
        - "AWARD_ID Modification P001"
        - "AWARD_ID Modification S022"
        - "AWARD_ID Modification A00002"
        - "AWARD_ID Modification 215"
        - "AWARD_ID Modification 0 (Base Record)"
        - "AWARD_ID" (no modification)

    Args:
        contract_mod_str: The input string to parse.

    Returns:
        A tuple containing:
        - The extracted award ID (string). Returns the original string if no
            " Modification " part is found. Returns empty string if input is None/empty.
        - The extracted modification number (int). Returns 0 if no modification
            part is found, if the modification part doesn't contain digits that can be
            parsed according to the rules, or if the input is None/empty.
    """
    # 1. Handle None or empty input
    if not contract_mod_str:
        return "", 0

    # Ensure input is treated as string and strip whitespace
    contract_mod_str = str(contract_mod_str).strip()
    if (
        not contract_mod_str
    ):  # Check again after potential stripping of whitespace-only string
        return "", 0

    # 2. Split by " Modification" followed by (space or end of string)
    # This correctly handles "AWARD_ID Modification", "AWARD_ID Modification ", and "AWARD_ID Modification P001"
    parts = re.split(
        r"\s+Modification(?:\s+|$)", contract_mod_str, maxsplit=1, flags=re.IGNORECASE
    )

    # 3. If no " Modification" part that matches criteria, parts[0] is original string.
    if len(parts) < 2:
        # This case implies "Modification" was not found in a way that allows splitting off an award ID.
        # e.g. input is just "AWARD_ID" or "SomeText"
        return contract_mod_str, 0

    award_id = parts[0].strip()
    mod_part_full = parts[1].strip()  # This will be "" if "Modification" was at the end

    # Handle case where the part after "Modification" is empty (already handled by mod_part_full = "" from split)
    if not mod_part_full:
        logging.info(
            f"Input '{contract_mod_str}' resulted in empty mod_part_full. Award ID: '{award_id}'. Mod num: 0."
        )
        return award_id, 0

    # 5. Attempt to extract modification number (int) from non-empty mod_part_full
    mod_num = 0
    mod_num_found = False

    # First, try to match leading digits directly (handles "215", "0 (Base Record)")
    match_leading_digits = re.match(r"^(\d+)", mod_part_full)
    if match_leading_digits:
        mod_str = match_leading_digits.group(1)
        try:
            mod_num = int(mod_str)
            mod_num_found = True
        except (ValueError, TypeError):
            # Should be unlikely if regex matched \d+, but handle anyway
            logging.warning(
                f"Failed converting leading digits '{mod_str}' from '{mod_part_full}' in '{contract_mod_str}'."
            )
            # Continue to next check

    # If leading digits weren't found or failed conversion,
    # try stripping leading non-digits (handles "P001", "S022", "A00002")
    if not mod_num_found:
        mod_part_numeric = re.sub(
            r"^\D+", "", mod_part_full
        )  # Remove leading non-digits
        if mod_part_numeric:  # Check if anything numeric remains
            try:
                mod_num = int(mod_part_numeric)
                mod_num_found = True
            except (ValueError, TypeError):
                logging.warning(
                    f"Failed converting digits '{mod_part_numeric}' (after stripping non-digits) from '{mod_part_full}' in '{contract_mod_str}'."
                )
                # Mod num remains 0

    # If no number was found by either method, log a warning
    if not mod_num_found:
        logging.warning(
            f"Could not extract numeric modification from '{mod_part_full}' in '{contract_mod_str}'. Defaulting mod to 0."
        )
        # mod_num is already 0

    # 6. Return the extracted award ID and modification number
    return award_id, mod_num


def filter_latest_modifications(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter DataFrame to only include rows with the highest modification number
    for each unique award ID.

    Args:
        df: DataFrame containing contract data with "Contract/Mod Number" column

    Returns:
        DataFrame with only the latest modification for each award ID
    """
    if df.empty or "Contract/Mod Number" not in df.columns:
        return df

    # Parse award IDs and modification numbers
    parsed_data = df["Contract/Mod Number"].apply(parse_mod_number)
    df_with_parsed = df.copy()
    df_with_parsed["Award_ID"] = [x[0] for x in parsed_data]
    df_with_parsed["Mod_Number"] = [x[1] for x in parsed_data]

    # Group by Award_ID and keep only rows with maximum Mod_Number
    idx = df_with_parsed.groupby("Award_ID")["Mod_Number"].idxmax()
    result = df_with_parsed.loc[idx].drop(columns=["Award_ID", "Mod_Number"])

    return result


def split_contract_mod_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Split the "Contract/Mod Number" column into two separate columns:
    "Contract" and "Mod Number" based on the first space character.

    Args:
        df: DataFrame containing "Contract/Mod Number" column

    Returns:
        DataFrame with split columns, original column removed
    """
    if df.empty or "Contract/Mod Number" not in df.columns:
        return df

    # Create a copy to avoid modifying the original
    result = df.copy()

    # Split on first space, expand=True creates two columns
    # n=1 limits to splitting on first space only
    split_cols = result["Contract/Mod Number"].str.split(" ", n=1, expand=True)

    # Handle cases where there might be no space (no modification)
    result["Contract"] = split_cols[0]
    result["Mod Number"] = split_cols[1] if 1 in split_cols.columns else ""

    # Get the position of the original column
    cols = list(result.columns)
    orig_col_idx = cols.index("Contract/Mod Number")

    # Remove the original column
    result = result.drop(columns=["Contract/Mod Number"])

    # Reorder columns to place new columns where the old one was
    cols_before = cols[:orig_col_idx]
    cols_after = cols[orig_col_idx + 1 :]
    # Remove the new columns from their current positions at the end
    cols_after = [c for c in cols_after if c not in ["Contract", "Mod Number"]]

    # Create new column order
    new_cols = cols_before + ["Contract", "Mod Number"] + cols_after
    result = result[new_cols]

    return result


def main():
    data_dir = Path("data")
    out_dir = Path("filtered")
    out_dir.mkdir(parents=True, exist_ok=True)

    years = [2026, 2025, 2024, 2023]
    project_patterns, candidate_pattern = compile_project_patterns(PROJECTS)
    with TemporaryDirectory(prefix="nasa-contract-projects-") as spool_dir_name:
        spool_dir = Path(spool_dir_name)
        project_numbers = {
            project_name: number for number, project_name in enumerate(PROJECTS)
        }
        spool_paths = {project_name: [] for project_name in PROJECTS}

        for yr in years:
            csv_file = data_dir / f"nasa_awards_{yr}.csv"
            for project_name, matched in iter_project_matches_for_year(
                yr,
                csv_file,
                project_patterns,
                candidate_pattern,
            ):
                project_spools = spool_paths[project_name]
                spool_path = spool_dir / (
                    f"{project_numbers[project_name]}-{len(project_spools)}.pkl"
                )
                matched.to_pickle(spool_path)
                project_spools.append(spool_path)

        for project_name, project_spools in spool_paths.items():
            if not project_spools:
                print(
                    f"No matches found for project '{project_name}'.",
                    file=sys.stderr,
                )
                continue

            combined = pd.concat(
                (pd.read_pickle(path) for path in project_spools),
                ignore_index=True,
            )

            # Filter to only include latest modifications
            latest_only = filter_latest_modifications(combined)

            # Split the Contract/Mod Number column into separate columns
            latest_only = split_contract_mod_column(latest_only)

            # Sort by Reverse Year and Award Type
            latest_only.sort_values(by=["Year", "Award Type"], inplace=True)

            # Split into two dataframes, one that matches "Grant" in Award Type and one that does not
            # Define a regex pattern for grants or cooperative agreements

            pattern = r"\b(?:Grant|Cooperative Agreement)s?\b"

            mask = latest_only["Award Type"].str.contains(
                pattern, flags=re.I, na=False, regex=True
            )

            grants_only = latest_only[mask]
            contracts = latest_only[~mask]

            years_str = "_".join(str(y) for y in years)
            out_path = out_dir / f"{project_name}_{years_str}"

            grants_only.to_csv(f"{out_path}_grants.csv", index=False)
            contracts.to_csv(f"{out_path}_contracts.csv", index=False)

            print(
                f"Wrote {len(latest_only)} rows (latest modifications only) for project '{project_name}' to: {out_path}"
            )


if __name__ == "__main__":
    main()
