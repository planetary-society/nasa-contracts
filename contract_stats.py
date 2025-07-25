#!/usr/bin/env python3
"""
Script to calculate basic statistics for NASA contracts by fiscal year.

For each given fiscal year, this script will:
  1. Calculate sum total of all obligations grouped by month of Award Date
  2. Count new awards (Modification 0) by category by month

Usage:
  python contract_stats.py --fys 2025 2024 2023
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from tabulate import tabulate
import re
from typing import Dict, List, Tuple

# Award type category mapping
AWARD_CATEGORIES = {
    "contracts": {
        "A": "BPA Call",
        "B": "Purchase Order",
        "C": "Delivery Order",
        "D": "Definitive Contract"
    },
    "loans": {
        "07": "Direct Loan",
        "08": "Guaranteed/Insured Loan"
    },
    "idvs": {
        "IDV_A": "GWAC Government Wide Acquisition Contract",
        "IDV_B": "IDC Multi-Agency Contract, Other Indefinite Delivery Contract",
        "IDV_B_A": "IDC Indefinite Delivery Contract / Requirements",
        "IDV_B_B": "IDC Indefinite Delivery Contract / Indefinite Quantity",
        "IDV_B_C": "IDC Indefinite Delivery Contract / Definite Quantity",
        "IDV_C": "FSS Federal Supply Schedule",
        "IDV_D": "BOA Basic Ordering Agreement",
        "IDV_E": "BPA Blanket Purchase Agreement"
    },
    "grants": {
        "02": "Block Grant",
        "03": "Formula Grant",
        "04": "Project Grant",
        "05": "Cooperative Agreement",
        "XX": "Grant"
    }
}

# Month names for fiscal year (Oct = 1, Sep = 12)
FISCAL_MONTHS = [
    "October", "November", "December", "January", "February", "March",
    "April", "May", "June", "July", "August", "September"
]


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
        help="Fiscal years to process (e.g., --fys 2025 2024 2023)"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export results as CSV files"
    )
    return parser.parse_args()


def get_fiscal_year_month(date_str: str) -> Tuple[int, int]:
    """
    Convert a date string to fiscal year and month.
    
    Args:
        date_str: Date string in MM/DD/YYYY format
        
    Returns:
        Tuple of (fiscal_year, fiscal_month) where fiscal_month is 1-12
        (Oct = 1, Sep = 12)
    """
    try:
        date = datetime.strptime(date_str, "%m/%d/%Y")
        # Fiscal year starts in October
        if date.month >= 10:  # Oct, Nov, Dec
            fiscal_year = date.year + 1
            fiscal_month = date.month - 9  # Oct=1, Nov=2, Dec=3
        else:  # Jan through Sep
            fiscal_year = date.year
            fiscal_month = date.month + 3  # Jan=4, Feb=5, ..., Sep=12
        return fiscal_year, fiscal_month
    except (ValueError, TypeError):
        return None, None


def parse_obligations(obligation_str: str) -> float:
    """
    Parse obligation string to float value.
    
    Args:
        obligation_str: String like "$1,234.56" or "-$5,678.90"
        
    Returns:
        Float value
    """
    if not obligation_str or pd.isna(obligation_str):
        return 0.0
    
    # Remove $ and commas, handle negative values
    clean_str = str(obligation_str).replace("$", "").replace(",", "")
    try:
        return float(clean_str)
    except (ValueError, TypeError):
        return 0.0


def get_award_category(award_type: str) -> str:
    """
    Extract and categorize award type.
    
    Args:
        award_type: Full award type string from CSV
        
    Returns:
        Top-level category name
    """
    if not award_type or pd.isna(award_type):
        return "Unknown"
    
    # Split by comma and take first value
    first_part = str(award_type).split(",")[0].strip()
    
    # Check each category mapping
    for category_name, mappings in AWARD_CATEGORIES.items():
        for code, description in mappings.items():
            if first_part == code or first_part == description:
                return category_name.capitalize()
    
    return "Other"


def calculate_obligations_by_month(df: pd.DataFrame, fiscal_year: int) -> pd.DataFrame:
    """
    Calculate sum of obligations by month for a fiscal year.
    
    Args:
        df: DataFrame with contract data
        fiscal_year: Fiscal year to process
        
    Returns:
        DataFrame with month, total obligations, and running total
    """
    # Filter for this fiscal year
    df_fy = df[df["Fiscal_Year"] == fiscal_year].copy()
    
    if df_fy.empty:
        return pd.DataFrame(columns=["Month", "Total Obligations", "Running Total"])
    
    # Group by fiscal month and sum obligations
    monthly_obligations = df_fy.groupby("Fiscal_Month")["Obligations_Float"].sum().reset_index()
    
    # Sort by fiscal month to ensure proper order for cumulative sum
    monthly_obligations = monthly_obligations.sort_values("Fiscal_Month")
    
    # Calculate running total
    monthly_obligations["Running_Sum"] = monthly_obligations["Obligations_Float"].cumsum()
    
    # Map to month names
    monthly_obligations["Month"] = monthly_obligations["Fiscal_Month"].apply(
        lambda x: FISCAL_MONTHS[x - 1] if 1 <= x <= 12 else "Unknown"
    )
    
    # Format for display
    monthly_obligations["Total Obligations"] = monthly_obligations["Obligations_Float"].apply(
        lambda x: f"${x:,.2f}"
    )
    monthly_obligations["Running Total"] = monthly_obligations["Running_Sum"].apply(
        lambda x: f"${x:,.2f}"
    )
    
    return monthly_obligations[["Month", "Total Obligations", "Running Total"]]


def export_obligations_table(obligations_table: pd.DataFrame, fiscal_year: int) -> str:
    """
    Export obligations table to CSV file.
    
    Args:
        obligations_table: DataFrame with obligations data
        fiscal_year: Fiscal year for filename
        
    Returns:
        Filename of exported CSV
    """
    filename = f"obligations_by_month_FY{fiscal_year}.csv"
    obligations_table.to_csv(filename, index=False)
    return filename


def export_awards_table(awards_table: pd.DataFrame, fiscal_year: int) -> str:
    """
    Export awards table to CSV file.
    
    Args:
        awards_table: DataFrame with awards data
        fiscal_year: Fiscal year for filename
        
    Returns:
        Filename of exported CSV
    """
    filename = f"new_awards_by_category_FY{fiscal_year}.csv"
    awards_table.to_csv(filename, index=True)  # Keep index for category names
    return filename


def count_new_awards_by_category(df: pd.DataFrame, fiscal_year: int) -> pd.DataFrame:
    """
    Count new awards (Modification 0) by category and month.
    
    Args:
        df: DataFrame with contract data
        fiscal_year: Fiscal year to process
        
    Returns:
        DataFrame with categories as rows and months as columns
    """
    # Filter for this fiscal year and Modification 0
    df_fy = df[
        (df["Fiscal_Year"] == fiscal_year) & 
        (df["Contract/Mod Number"].str.contains("Modification 0", case=False, na=False))
    ].copy()
    
    if df_fy.empty:
        return pd.DataFrame()
    
    # Extract award categories
    df_fy["Category"] = df_fy["Award Type"].apply(get_award_category)
    
    # Create pivot table
    pivot = pd.crosstab(
        df_fy["Category"],
        df_fy["Fiscal_Month"],
        margins=True,
        margins_name="Total"
    )
    
    # Rename columns to month names
    column_mapping = {i: FISCAL_MONTHS[i-1] for i in range(1, 13)}
    pivot = pivot.rename(columns=column_mapping)
    
    # Ensure all months are present (fill missing with 0)
    for month in FISCAL_MONTHS:
        if month not in pivot.columns:
            pivot[month] = 0
    
    # Reorder columns
    ordered_cols = [col for col in FISCAL_MONTHS if col in pivot.columns] + ["Total"]
    pivot = pivot[ordered_cols]
    
    return pivot


def process_fiscal_year(year: int, data_dir: Path, export: bool = False) -> None:
    """
    Process a single fiscal year and print statistics.
    
    Args:
        year: Fiscal year to process
        data_dir: Directory containing CSV files
        export: Whether to export results as CSV files
    """
    csv_file = data_dir / f"nasa_contracts_{year}.csv"
    
    if not csv_file.exists():
        print(f"\nWarning: {csv_file} not found. Skipping fiscal year {year}.")
        return
    
    print(f"\n{'='*60}")
    print(f"Fiscal Year {year} Statistics")
    print(f"{'='*60}")
    
    # Read CSV
    df = pd.read_csv(csv_file, dtype=str)
    
    # Parse dates and obligations
    df[["Fiscal_Year", "Fiscal_Month"]] = df["Award Date"].apply(
        lambda x: pd.Series(get_fiscal_year_month(x))
    )
    df["Obligations_Float"] = df["Obligations"].apply(parse_obligations)
    
    # Filter for this fiscal year
    df_fy = df[df["Fiscal_Year"] == year]
    
    if df_fy.empty:
        print(f"No contracts found for fiscal year {year}")
        return
    
    # Table 1: Obligations by month
    print("\n1. Sum of Obligations by Month")
    print("-" * 40)
    
    obligations_table = calculate_obligations_by_month(df, year)
    if not obligations_table.empty:
        print(tabulate(obligations_table, headers="keys", tablefmt="grid", showindex=False))
        
        # Add total
        total = df_fy["Obligations_Float"].sum()
        print(f"\nTotal for FY{year}: ${total:,.2f}")
        
        # Export if requested
        if export:
            filename = export_obligations_table(obligations_table, year)
            print(f"Exported obligations table to: {filename}")
    else:
        print("No data available")
    
    # Table 2: New awards by category
    print("\n2. New Awards (Modification 0) by Category and Month")
    print("-" * 60)
    
    awards_table = count_new_awards_by_category(df, year)
    if not awards_table.empty:
        print(tabulate(awards_table, headers="keys", tablefmt="grid"))
        
        # Export if requested
        if export:
            filename = export_awards_table(awards_table, year)
            print(f"Exported awards table to: {filename}")
    else:
        print("No new awards found")


def main():
    """Main function."""
    args = parse_arguments()
    data_dir = Path("data")
    
    # Sort fiscal years in descending order
    fiscal_years = sorted(args.fys, reverse=True)
    
    print(f"Processing fiscal years: {', '.join(map(str, fiscal_years))}")
    if args.export:
        print("CSV export enabled - files will be saved to current directory")
    
    for fy in fiscal_years:
        process_fiscal_year(fy, data_dir, args.export)
    
    print(f"\n{'='*60}")
    print("Analysis complete")


if __name__ == "__main__":
    main()