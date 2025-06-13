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

import pandas as pd

# Define the projects and their keyword batches.
PROJECTS = {
    "MSR": ["MSR", "Mars Sample Return"],
    "Juno": ["Juno"],
    "New Horizons": ["New Horizons","~New Horizons Aeronautics, Llc"],
    "OSIRIS-APEX": ["OSIRIS-APEX", "Apophis Explorer"],
    "Mars Odyssey": ["ODY","Mars Odyssey","Odyssey", "~Odyssey Space Research"],
    "VERITAS": ["VERITAS","Venus Emissivity, Radio Science, InSAR, Topography, and Spectroscopy"],
    "DAVINCI": ["DAVINCI","Deep Atmosphere Venus Investigation of Noble gases, Chemistry, and Imaging"],
    "EnVision": ["EnVision","vensar","~nustar","~plankton"],
    "MAVEN": ["MAVEN"],
    "Euclid": ["Euclid", "~SBIR","~STTR","~Euclid Beamlabs"],
    "MEx": ["Mars Express"],
    "Fermi": ["Fermi","~SOLAR wind"],
    "Chandra": ["Chandra"],
    "SAGE-III": ["SAGE-III", "Stratospheric Aerosol and Gas Experiment III", "SAGE III"],
    "DSCOVR": ["DSCOVR", "Deep Space Climate Observatory", "DSCOVR EPIC", "DSCOVR NISTAR"],
    "Terra": ["Terra", "Terra EOS"],
    "Aqua": ["Aqua"],
    "Aura": ["Aura"],
    "OCO-3": ["OCO-3", "Orbiting Carbon Observatory-3", "OCO3"],
    "OCO-2": ["OCO-2", "Orbiting Carbon Observatory-2", "OCO2"],
    "GOLD": ["GOLD", "Global-scale Observations of the Limb and Disk"],
    "Hinode": ["Hinode", "Solar-B", "Hinode NASA"],
    "IBEX": ["IBEX", "Interstellar Boundary Explorer", "IBEX NASA"],
    "MMS": ["MMS", "Magnetospheric Multiscale"],
    "THEMIS_ARTEMIS": ["THEMIS", "THEMIS-ARTEMIS"],
    "TIMED": ["TIMED", "Thermosphere Ionosphere Mesosphere Energetics Dynamics"],
    "VIPER": ["VIPER", "Volatiles Investigating Polar Exploration Rover"],
    "Rosalind_Franklin_Rover": [
        "Rosalind Franklin",
        "ExoMars",
    ],
    "COSI": ["COSI", "Compton Spectrometer and Imager"],
    "LISA": ["LISA", "Laser Interferometer Space Antenna"],
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
    "GDC": ["GDC", "Geospace Dynamics Constellation"]
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

    # Create row-wise concatenated string
    row_strings = df_chunk.astype(str).agg(" ".join, axis=1)

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
        years_str = "_".join(str(y) for y in years)
        out_path = out_dir / f"{project_name}_{years_str}.csv"
        combined.to_csv(out_path, index=False)
        print(f"Wrote {len(combined)} rows for project '{project_name}' to: {out_path}")


if __name__ == "__main__":
    main()