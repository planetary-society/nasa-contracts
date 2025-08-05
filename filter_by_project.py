#!/usr/bin/env python3
"""
Script to filter large NASA contract CSVs by project-specific keyword batches using chunked processing,
without triggering the “has match groups” warning.

For each project in the PROJECTS dict, this script will:
  1. Read the CSV files in data/nasa_contracts_{year}.csv for the years 2025, 2024, and 2023 in chunks.
  2. For each chunk, filter rows where any of the project's keywords appear (case-insensitive) in any column.
  3. Accumulate filtered rows across all chunks and all three years.
  4. Write the combined rows to filtered/{project_name}_2025_2024_2023.csv.

Dependencies:
  - pandas
"""

import re
import sys
from pathlib import Path
from typing import Set, Optional, Tuple
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the projects and their keyword batches.
PROJECTS = {
    "MSR": ["MSR", "Mars Sample Return"],
    "Juno": ["Juno"],
    "New Horizons": ["New Horizons","~New Horizons Aeronautics, Llc"],
    "OSIRIS-APEX": ["OSIRIS-APEX", "Apophis Explorer"],
    "Mars Odyssey": ["ODY","Mars Odyssey","Odyssey", "~Odyssey Space Research"],
    "VERITAS": ["VERITAS","Venus Emissivity, Radio Science, InSAR, Topography, and Spectroscopy","~netbackup","~netback up","~Metgreen Solutions Inc","~software","~maintenance","~consulting services","~renewal"],
    "SAGE-III": ["SAGE-III", "Stratospheric Aerosol and Gas Experiment III", "SAGE III"],
    "DSCOVR": ["DSCOVR", "Deep Space Climate Observatory", "DSCOVR EPIC", "DSCOVR NISTAR"],
    "Terra": ["Terra", "Terra EOS","~Terra Ferma Llc","~A-Terra Llc","~Terra Universal, Inc.","~Terra Research Inc."],
    "Aqua": ["Aqua"],
    "Aura": ["Aura"],
    "OCO-3": ["OCO-3", "Orbiting Carbon Observatory-3", "OCO3"],
    "OCO-2": ["OCO-2", "Orbiting Carbon Observatory-2", "OCO2"],
    "GOLD": ["GOLD", "Global-scale Observations of the Limb and Disk"],
    "Hinode": ["Hinode", "Solar-B", "Hinode NASA"],
    "IBEX": ["IBEX", "Interstellar Boundary Explorer", "IBEX NASA","~ibex business"],
    "MMS": ["MMS", "Magnetospheric Multiscale"],
    "THEMIS_ARTEMIS": ["THEMIS", "THEMIS-ARTEMIS"],
    "TIMED": ["TIMED", "Thermosphere Ionosphere Mesosphere Energetics Dynamics"],
    "VIPER": ["VIPER", "Volatiles Investigating Polar Exploration Rover", "~versatile imager platform","~VIPER machine","~3d systems","~vxworks VIPER","~VIPER fabrication services","~Eo14042"],
    "Rosalind_Franklin_Rover": [
        "Rosalind Franklin",
        "ExoMars",
        "~trace gas orbiter"
    ],
    "COSI": ["COSI", "Compton Spectrometer and Imager"],
    "LISA": ["LISA", "Laser Interferometer Space Antenna","LISA-T"],
    "ULTRASAT": [
        "ULTRASAT",
        "Ultraviolet Transient Astronomy Satellite",
    ],
    "ARIEL": ["Atmospheric Remote-sensing Infrared Exoplanet Large-survey", "ARIEL"],
    "Pioneers_Missions": [
        "PUEO",
        "Pandora",
        "Aspera",
        "StarBurst",
        "TIGERISS"
    ],
    "SBG-VSWIR": [
        "SBG-VSWIR",
        "Surface Biology and Geology VSWIR",
        "VSWIR Spectrometer"
    ],
    "PMM": ["PMM", "Global Precipitation Measurement Mission"],
    "Landsat_Next": ["Landsat Next", "Landsat-Next"],
    "SBG-TIR": [
        "SBG-TIR",
        "Surface Biology and Geology TIR",
        "TIR Radiometer"
    ],
    "EUVST": ["EUVST", "EUV Solar Telescope"],
    "HelioSwarm": ["HelioSwarm", "Helio Swarm"],
    "HERMES": ["HERMES", "Heliospheric Relay and Monitoring Experiment"],
    "GDC": ["GDC", "Geospace Dynamics Constellation"],
    
}

# Number of rows per chunk. Adjust based on your available memory.
CHUNK_SIZE = 100_000


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
    # Split into positive and negative keyword lists
    positives = [kw for kw in keywords if not kw.startswith("~")]
    negatives = [kw[1:] for kw in keywords if kw.startswith("~")]

    # Create row-wise concatenated string. Don't include contractor names since those frequently return false positives.
    row_strings = df_chunk.drop(columns=['Contractor'], errors='ignore').astype(str).agg(" ".join, axis=1)

    # Build positive regex (if any)
    if positives:
        escaped_pos = [re.escape(kw) for kw in positives]
        pos_pattern = re.compile(r"(?i)\b(?:" + "|".join(escaped_pos) + r")\b")
        pos_mask = row_strings.str.contains(pos_pattern, na=False)
    else:
        # If no positives provided, match everything by default
        pos_mask = pd.Series(True, index=df_chunk.index)

    # Build negative regex (if any)
    if negatives:
        escaped_neg = [re.escape(kw) for kw in negatives]
        neg_pattern = re.compile(r"(?i)\b(?:" + "|".join(escaped_neg) + r")\b")
        neg_mask = row_strings.str.contains(neg_pattern, na=False)
    else:
        # If no negatives provided, nothing to exclude
        neg_mask = pd.Series(False, index=df_chunk.index)

    # Final mask: match positives AND NOT match negatives
    return pos_mask & ~neg_mask


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

    filtered_chunks = []
    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=CHUNK_SIZE):
        mask = build_filter_mask(chunk, keywords)
        if mask.any():
            df_matched = chunk[mask].copy()
            df_matched.insert(0, "Year", year)
            filtered_chunks.append(df_matched)

    if not filtered_chunks:
        return pd.DataFrame()

    return pd.concat(filtered_chunks, ignore_index=True)

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
    if not contract_mod_str: # Check again after potential stripping of whitespace-only string
        return "", 0

    # 2. Split by " Modification" followed by (space or end of string)
    # This correctly handles "AWARD_ID Modification", "AWARD_ID Modification ", and "AWARD_ID Modification P001"
    parts = re.split(r'\s+Modification(?:\s+|$)', contract_mod_str, maxsplit=1, flags=re.IGNORECASE)

    # 3. If no " Modification" part that matches criteria, parts[0] is original string.
    if len(parts) < 2:
        # This case implies "Modification" was not found in a way that allows splitting off an award ID.
        # e.g. input is just "AWARD_ID" or "SomeText"
        return contract_mod_str, 0
    
    award_id = parts[0].strip()
    mod_part_full = parts[1].strip() # This will be "" if "Modification" was at the end

    # Handle case where the part after "Modification" is empty (already handled by mod_part_full = "" from split)
    if not mod_part_full:
        logging.info(f"Input '{contract_mod_str}' resulted in empty mod_part_full. Award ID: '{award_id}'. Mod num: 0.")
        return award_id, 0

    # 5. Attempt to extract modification number (int) from non-empty mod_part_full
    mod_num = 0
    mod_num_found = False

    # First, try to match leading digits directly (handles "215", "0 (Base Record)")
    match_leading_digits = re.match(r'^(\d+)', mod_part_full)
    if match_leading_digits:
        mod_str = match_leading_digits.group(1)
        try:
            mod_num = int(mod_str)
            mod_num_found = True
        except (ValueError, TypeError):
                # Should be unlikely if regex matched \d+, but handle anyway
                logging.warning(f"Failed converting leading digits '{mod_str}' from '{mod_part_full}' in '{contract_mod_str}'.")
                # Continue to next check

    # If leading digits weren't found or failed conversion,
    # try stripping leading non-digits (handles "P001", "S022", "A00002")
    if not mod_num_found:
        mod_part_numeric = re.sub(r'^\D+', '', mod_part_full) # Remove leading non-digits
        if mod_part_numeric: # Check if anything numeric remains
            try:
                mod_num = int(mod_part_numeric)
                mod_num_found = True
            except (ValueError, TypeError):
                logging.warning(f"Failed converting digits '{mod_part_numeric}' (after stripping non-digits) from '{mod_part_full}' in '{contract_mod_str}'.")
                # Mod num remains 0

    # If no number was found by either method, log a warning
    if not mod_num_found:
            logging.warning(f"Could not extract numeric modification from '{mod_part_full}' in '{contract_mod_str}'. Defaulting mod to 0.")
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

def main():
    data_dir = Path("data")
    out_dir = Path("filtered")
    out_dir.mkdir(parents=True, exist_ok=True)

    years = [2025, 2024, 2023]

    for project_name, keywords in PROJECTS.items():
        all_frames = []
        for yr in years:
            csv_file = data_dir / f"nasa_contracts_{yr}.csv"
            df_filtered = filter_for_project_and_year(yr, csv_file, keywords)
            if not df_filtered.empty:
                all_frames.append(df_filtered)

        if not all_frames:
            print(f"No matches found for project '{project_name}'.", file=sys.stderr)
            continue

        combined = pd.concat(all_frames, ignore_index=True)
        
        # Filter to only include latest modifications
        latest_only = filter_latest_modifications(combined)
        
        # Sort by Reverse Year and Award Type
        latest_only.sort_values(by=["Year", "Award Type"], inplace=True)
        
        # Split into two dataframes, one that matches "Grant" in Award Type and one that does not
        grants_only = latest_only[latest_only["Award Type"].str.contains("Grant", case=False, na=False)]
        contracts = latest_only[~latest_only["Award Type"].str.contains("Grant", case=False, na=False)]
        
        years_str = "_".join(str(y) for y in years)
        out_path = out_dir / f"{project_name}_{years_str}"
        
        grants_only.to_csv(f"{out_path}_grants.csv", index=False)
        contracts.to_csv(f"{out_path}_contracts.csv", index=False)

        print(f"Wrote {len(latest_only)} rows (latest modifications only) for project '{project_name}' to: {out_path}")


if __name__ == "__main__":
    main()