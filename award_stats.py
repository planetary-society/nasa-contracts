#!/usr/bin/env python3
"""
Script to calculate basic statistics for NASA contracts by fiscal year.

For each given fiscal year, this script will:
  1. Calculate sum total of all obligations grouped by month of Award Date
  2. Count new awards (Modification 0) by category by month

Usage:
  python award_stats.py --fys 2025 2024 2023
  python award_stats.py --fys 2025 2024 2023 --export
  python award_stats.py --fys 2025 2024 2023 --export reports/awards.csv
"""

import argparse
from pathlib import Path
import pandas as pd
from tabulate import tabulate
from typing import Dict, List, Optional

# Award type category mapping
AWARD_CATEGORIES = {
    "contracts": {
        "A": "BPA Call",
        "B": "Purchase Order",
        "C": "Delivery Order",
        "D": "Definitive Contract",
    },
    "loans": {"07": "Direct Loan", "08": "Guaranteed/Insured Loan"},
    "idvs": {
        "IDV_A": "GWAC Government Wide Acquisition Contract",
        "IDV_B": "IDC Multi-Agency Contract, Other Indefinite Delivery Contract",
        "IDV_B_A": "IDC Indefinite Delivery Contract / Requirements",
        "IDV_B_B": "IDC Indefinite Delivery Contract / Indefinite Quantity",
        "IDV_B_C": "IDC Indefinite Delivery Contract / Definite Quantity",
        "IDV_C": "FSS Federal Supply Schedule",
        "IDV_D": "BOA Basic Ordering Agreement",
        "IDV_E": "BPA Blanket Purchase Agreement",
    },
    "grants": {
        "02": "Block Grant",
        "03": "Formula Grant",
        "04": "Project Grant",
        "05": "Cooperative Agreement",
        "XX": "Grant",
    },
}

# FY2005-FY2008 put contractor indicators before the award descriptor in the
# same field. These are the source's unambiguous contract and assistance types;
# values such as Other, Intragovernmental, and Space Act Agreement stay Other.
LEGACY_AWARD_CATEGORIES = {
    "contracts": {
        "BPA Call",
        "Combination",
        "Cost No Fee",
        "Cost Plus Award Fee",
        "Cost Plus Fixed Fee",
        "Cost Plus Incentive Fee",
        "Cost Sharing",
        "Firm Fixed Price",
        "Fixed Price Award Fee",
        "Fixed Price Incentive",
        "Fixed Price Level of Effort",
        "Fixed Price Redetermination",
        "Fixed Price with Economic Price Adjustment",
        "Labor Hours",
        "Purchase Order",
        "Time and Materials",
    },
    "grants": {
        "Cooperative Agreement",
        "Grant For Research",
        "Training Grant",
    },
}

# Month names for fiscal year (Oct = 1, Sep = 12)
FISCAL_MONTHS = [
    "October",
    "November",
    "December",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
]

# NPDV marks an award's first action with this suffix. Matching it as a
# substring would also catch later modifications such as "Modification 00001A".
BASE_RECORD_SUFFIX = "Modification 0 (Base Record)"

# Columns the statistics need; Description dominates file size and is unused.
STATS_COLUMNS = ["Award Date", "Obligations", "Contract/Mod Number", "Award Type"]
AUTO_EXPORT = object()


def dollars(value) -> str:
    """
    Render a dollar amount the way every printed table displays it.

    Amounts are shown in millions: to the nearest million above $10M, and to
    one decimal place below that, so $65,646,257 reads as $66M and $8,712,004
    as $8.7M. Exported CSVs keep the underlying whole-dollar integers.
    """
    millions = (0 if pd.isna(value) else value) / 1_000_000
    return f"${millions:,.0f}M" if abs(millions) >= 10 else f"${millions:,.1f}M"


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate basic statistics for NASA contracts by fiscal year"
    )
    parser.add_argument(
        "--fys",
        nargs="+",
        type=int,
        required=True,
        help="Fiscal years to process (e.g., --fys 2025 2024 2023)",
    )
    parser.add_argument(
        "--export",
        nargs="?",
        const=AUTO_EXPORT,
        type=Path,
        metavar="OUTPUT_CSV",
        help="Export results, optionally to a custom CSV path",
    )
    return parser.parse_args()


def resolve_export_path(export, fiscal_years: List[int]) -> Optional[Path]:
    """Resolve the optional export argument to a concrete output path."""
    if export is None:
        return None
    if export is AUTO_EXPORT:
        return Path(
            f"new_awards_{min(fiscal_years)}_to_{max(fiscal_years)}.csv"
        )
    return Path(export)


def add_derived_columns(
    df: pd.DataFrame,
    source_fiscal_year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Add fiscal year, fiscal month, dollar, and award category columns.

    Args:
        df: DataFrame of raw award actions

    Returns:
        The same DataFrame, with derived columns added and unreadable values
        reported. Fiscal months run Oct = 1 through Sep = 12.
    """
    award_dates = pd.to_datetime(df["Award Date"], format="%m/%d/%Y", errors="coerce")
    df["Fiscal_Year"] = award_dates.dt.year + (award_dates.dt.month >= 10)
    df["Fiscal_Month"] = (award_dates.dt.month - 10) % 12 + 1

    # NPDV writes whole-dollar integers, so anything unparseable is a surprise.
    amounts = pd.to_numeric(df["Obligations"], errors="coerce")
    df["Obligations_Dollars"] = amounts.fillna(0)

    # A fiscal year holds tens of thousands of rows but only a few dozen
    # distinct award types, so categorize each distinct value once.
    categories = {
        value: get_award_category(value, source_fiscal_year)
        for value in df["Award Type"].unique()
    }
    df["Category"] = df["Award Type"].map(categories)

    if award_dates.isna().any():
        print(
            f"Warning: {award_dates.isna().sum():,} rows have an unreadable "
            "Award Date and are excluded from every table"
        )
    if amounts.isna().any():
        print(
            f"Warning: {amounts.isna().sum():,} rows have an unreadable "
            "Obligations value and are counted as 0"
        )

    return df


def get_award_category(
    award_type: str,
    fiscal_year: Optional[int] = None,
) -> str:
    """
    Extract and categorize award type.

    Args:
        award_type: Full award type string from CSV
        fiscal_year: Source file's fiscal year, used to interpret the legacy
            compound field

    Returns:
        Top-level category name
    """
    if not award_type or pd.isna(award_type):
        return "Unknown"

    if fiscal_year is not None and fiscal_year <= 2008:
        descriptor = str(award_type).rsplit(",", 1)[-1].strip()
        for category_name, descriptions in LEGACY_AWARD_CATEGORIES.items():
            if descriptor in descriptions:
                return category_name.capitalize()
        return "Other"

    # Modern exports put the award vehicle before the first comma.
    first_part = str(award_type).split(",", 1)[0].strip()
    for category_name, mappings in AWARD_CATEGORIES.items():
        for code, description in mappings.items():
            if first_part == code or first_part == description:
                return category_name.capitalize()

    return "Other"


def calculate_obligations_by_month(df_fy: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate sum of obligations by month for one fiscal year's award actions.

    Args:
        df_fy: DataFrame holding a single fiscal year

    Returns:
        DataFrame with month, total obligations, and running total
    """
    monthly = df_fy.groupby("Fiscal_Month")["Obligations_Dollars"].sum().sort_index()

    return pd.DataFrame(
        {
            "Month": [FISCAL_MONTHS[month - 1] for month in monthly.index],
            "Total Obligations": monthly.map(dollars),
            "Running Total": monthly.cumsum().map(dollars),
        }
    )


def summarize_new_awards(new_awards: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Count and total new awards by category and fiscal month.

    Args:
        new_awards: DataFrame holding one fiscal year's base records

    Returns:
        {"counts": DataFrame, "values": DataFrame}, both indexed by category
        with the twelve fiscal months plus a "Total" column, and a total row.
        Empty frames when there are no new awards.
    """
    if new_awards.empty:
        return {"counts": pd.DataFrame(), "values": pd.DataFrame()}

    grouped = new_awards.groupby(["Category", "Fiscal_Month"])[
        "Obligations_Dollars"
    ].agg(["size", "sum"])

    summary = {}
    for name, column, total_label in (
        ("counts", "size", "Total"),
        ("values", "sum", "Total Value"),
    ):
        table = (
            grouped[column]
            .unstack(fill_value=0)
            .rename(columns=lambda month: FISCAL_MONTHS[month - 1])
            .reindex(columns=FISCAL_MONTHS, fill_value=0)
            .rename_axis(None)
            .rename_axis(None, axis="columns")
        )
        table.loc[total_label] = table.sum()
        table["Total"] = table.sum(axis=1)
        summary[name] = table

    return summary


def get_awards_data_for_year(summary: Dict[str, pd.DataFrame]) -> Dict:
    """
    Reshape one fiscal year's summary into the export dictionary.

    Args:
        summary: Output of summarize_new_awards

    Returns:
        Dictionary with monthly counts and values for contracts and grants
    """
    counts, values = summary["counts"], summary["values"]
    if counts.empty:
        return {}

    def cell(table: pd.DataFrame, category: str, month: str) -> int:
        return int(table.at[category, month]) if category in table.index else 0

    return {
        month: {
            "contract_count": cell(counts, "Contracts", month),
            "contract_value": cell(values, "Contracts", month),
            "grant_count": cell(counts, "Grants", month),
            "grant_value": cell(values, "Grants", month),
        }
        for month in FISCAL_MONTHS
    }


def create_combined_awards_csv(
    all_data: Dict,
    fiscal_years: List[int],
    output_path: Path,
) -> Path:
    """
    Create combined CSV file with awards data for all fiscal years.

    Args:
        all_data: Dictionary with data for each fiscal year
        fiscal_years: List of fiscal years to include
        output_path: Destination CSV path

    Returns:
        Path of the exported CSV
    """
    # Sort fiscal years for consistent ordering
    fiscal_years = sorted(
        (year for year in fiscal_years if year in all_data),
        reverse=True,
    )
    if not fiscal_years:
        raise ValueError("no fiscal-year data to export")

    # Build rows
    rows = []
    for month in FISCAL_MONTHS:
        row = {"Month": month}
        for fy in fiscal_years:
            data = all_data.get(fy, {}).get(month, {})
            row[f"FY {fy} New Grant Awards"] = data.get("grant_count", 0)
            row[f"FY {fy} Grant Awards Value"] = data.get("grant_value", 0)
            row[f"FY {fy} New Contract Awards"] = data.get("contract_count", 0)
            row[f"FY {fy} Contract Awards Value"] = data.get("contract_value", 0)
        rows.append(row)

    # Create DataFrame, then let pandas total every column but the month name
    df_export = pd.DataFrame(rows)
    totals = df_export.drop(columns="Month").sum()
    df_export = pd.concat(
        [df_export, pd.DataFrame([{"Month": "Total", **totals}])], ignore_index=True
    )

    # Values are whole dollars, so no float formatting is needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_export.to_csv(output_path, index=False)
    return output_path


def format_awards_table(summary: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Lay one fiscal year's summary out as counts above formatted dollar rows.

    Args:
        summary: Output of summarize_new_awards

    Returns:
        DataFrame with categories as rows and months as columns
    """
    counts, values = summary["counts"], summary["values"]
    if counts.empty:
        return pd.DataFrame()

    value_rows = [
        values.loc[[category]].rename(index={category: label}).map(dollars)
        for category, label in (
            ("Contracts", "Contract Value"),
            ("Grants", "Grant Value"),
            ("Total Value", "Total Value"),
        )
        if category in values.index
    ]

    return pd.concat([counts] + value_rows)


def process_fiscal_year(year: int, data_dir: Path, export: bool = False) -> Dict:
    """
    Process a single fiscal year and print statistics.

    Args:
        year: Fiscal year to process
        data_dir: Directory containing CSV files
        export: Whether to export results as CSV files
    """
    csv_file = data_dir / f"nasa_awards_{year}.csv"

    if not csv_file.exists():
        print(f"\nWarning: {csv_file} not found. Skipping fiscal year {year}.")
        return {}

    print(f"\n{'=' * 60}")
    print(f"Fiscal Year {year} Statistics")
    print(f"{'=' * 60}")

    df = add_derived_columns(
        pd.read_csv(csv_file, dtype=str, usecols=STATS_COLUMNS),
        source_fiscal_year=year,
    )

    # Filter for this fiscal year
    df_fy = df[df["Fiscal_Year"] == year]

    if df_fy.empty:
        print(f"No contracts found for fiscal year {year}")
        return {}

    new_awards = df_fy[
        df_fy["Contract/Mod Number"].str.endswith(BASE_RECORD_SUFFIX, na=False)
    ]
    summary = summarize_new_awards(new_awards)

    uncategorized = (new_awards["Category"] == "Other").mean() if len(new_awards) else 0
    if uncategorized and year <= 2008:
        print(
            f"\nWarning: {uncategorized:.0%} of FY{year} new awards use a legacy "
            "type that cannot be classified as a contract or grant. They remain "
            "Other and are excluded from exported contract/grant columns."
        )
    elif uncategorized > 0.5:
        print(
            f"\nWarning: {uncategorized:.0%} of FY{year} new awards cannot be "
            "classified as a contract or grant. They remain Other and are "
            "excluded from exported contract/grant columns."
        )

    # Table 1: Obligations by month
    print("\n1. Sum of Obligations by Month")
    print("-" * 40)

    print(
        tabulate(
            calculate_obligations_by_month(df_fy),
            headers="keys",
            tablefmt="grid",
            showindex=False,
        )
    )
    print(f"\nTotal for FY{year}: {dollars(df_fy['Obligations_Dollars'].sum())}")

    # Table 2: New awards by category (counts and values)
    print("\n2. New Awards (Modification 0) by Category and Month")
    print("-" * 60)

    awards_table = format_awards_table(summary)
    if awards_table.empty:
        print("No new awards found")
    else:
        print(tabulate(awards_table, headers="keys", tablefmt="grid"))

    # Return raw data for export if requested
    if export:
        return get_awards_data_for_year(summary)
    return {}


def main():
    """Main function."""
    args = parse_arguments()
    data_dir = Path("data")

    # Sort fiscal years in descending order
    fiscal_years = sorted(args.fys, reverse=True)
    output_path = resolve_export_path(args.export, fiscal_years)

    print(f"Processing fiscal years: {', '.join(map(str, fiscal_years))}")
    if output_path is not None:
        print(f"CSV export enabled - output will be saved to {output_path}")

    # Collect data from all fiscal years
    all_awards_data = {}
    for fy in fiscal_years:
        fy_data = process_fiscal_year(fy, data_dir, output_path is not None)
        if fy_data:
            all_awards_data[fy] = fy_data

    # Export combined CSV if requested
    if output_path is not None:
        if not all_awards_data:
            raise SystemExit(
                "No fiscal-year data available; export was not created."
            )
        filename = create_combined_awards_csv(
            all_awards_data,
            fiscal_years,
            output_path,
        )
        print(f"\nExported combined awards data to: {filename}")

    print(f"\n{'=' * 60}")
    print("Analysis complete")


if __name__ == "__main__":
    main()
