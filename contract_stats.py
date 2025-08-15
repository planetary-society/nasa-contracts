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


def get_awards_data_for_year(df: pd.DataFrame, fiscal_year: int) -> Dict:
    """
    Get raw awards data for a fiscal year.
    
    Args:
        df: DataFrame with contract data
        fiscal_year: Fiscal year to process
        
    Returns:
        Dictionary with monthly counts and values for contracts and grants
    """
    # Filter for this fiscal year and Modification 0
    df_fy = df[
        (df["Fiscal_Year"] == fiscal_year) & 
        (df["Contract/Mod Number"].str.contains("Modification 0", case=False, na=False))
    ].copy()
    
    if df_fy.empty:
        return {}
    
    # Extract award categories
    df_fy["Category"] = df_fy["Award Type"].apply(get_award_category)
    
    # Initialize result dictionary
    result = {}
    
    # Process each month
    for month_idx, month_name in enumerate(FISCAL_MONTHS, 1):
        month_data = df_fy[df_fy["Fiscal_Month"] == month_idx]
        
        # Count and sum by category
        contracts_data = month_data[month_data["Category"] == "Contracts"]
        grants_data = month_data[month_data["Category"] == "Grants"]
        
        result[month_name] = {
            "contract_count": len(contracts_data),
            "contract_value": round(contracts_data["Obligations_Float"].sum(), 2),
            "grant_count": len(grants_data),
            "grant_value": round(grants_data["Obligations_Float"].sum(), 2)
        }
    
    return result


def create_combined_awards_csv(all_data: Dict, fiscal_years: List[int]) -> str:
    """
    Create combined CSV file with awards data for all fiscal years.
    
    Args:
        all_data: Dictionary with data for each fiscal year
        fiscal_years: List of fiscal years to include
        
    Returns:
        Filename of exported CSV
    """
    # Sort fiscal years for consistent ordering
    fiscal_years = sorted(fiscal_years, reverse=True)
    
    # Build rows
    rows = []
    for month in FISCAL_MONTHS:
        row = {"Month": month}
        for fy in fiscal_years:
            if fy in all_data and month in all_data[fy]:
                data = all_data[fy][month]
                row[f"FY {fy} New Grant Awards"] = data["grant_count"]
                row[f"FY {fy} Grant Awards Value"] = data["grant_value"]
                row[f"FY {fy} New Contract Awards"] = data["contract_count"]
                row[f"FY {fy} Contract Awards Value"] = data["contract_value"]
            else:
                row[f"FY {fy} New Grant Awards"] = 0
                row[f"FY {fy} Grant Awards Value"] = 0.00
                row[f"FY {fy} New Contract Awards"] = 0
                row[f"FY {fy} Contract Awards Value"] = 0.00
        rows.append(row)
    
    # Add totals row
    total_row = {"Month": "Total"}
    for fy in fiscal_years:
        grant_count_total = 0
        grant_value_total = 0.0
        contract_count_total = 0
        contract_value_total = 0.0
        
        if fy in all_data:
            for month_data in all_data[fy].values():
                grant_count_total += month_data["grant_count"]
                grant_value_total += month_data["grant_value"]
                contract_count_total += month_data["contract_count"]
                contract_value_total += month_data["contract_value"]
        
        total_row[f"FY {fy} New Grant Awards"] = grant_count_total
        total_row[f"FY {fy} Grant Awards Value"] = round(grant_value_total, 2)
        total_row[f"FY {fy} New Contract Awards"] = contract_count_total
        total_row[f"FY {fy} Contract Awards Value"] = round(contract_value_total, 2)
    
    rows.append(total_row)
    
    # Create DataFrame and export
    df_export = pd.DataFrame(rows)
    
    # Generate filename
    min_year = min(fiscal_years)
    max_year = max(fiscal_years)
    filename = f"new_awards_{min_year}_to_{max_year}.csv"
    
    # Export with proper float formatting (2 decimal places)
    df_export.to_csv(filename, index=False, float_format='%.2f')
    return filename


def count_new_awards_by_category(df: pd.DataFrame, fiscal_year: int) -> pd.DataFrame:
    """
    Count new awards (Modification 0) by category and month, including value totals.
    
    Args:
        df: DataFrame with contract data
        fiscal_year: Fiscal year to process
        
    Returns:
        DataFrame with categories as rows and months as columns, including counts and values
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
    
    # Create count pivot table
    count_pivot = pd.crosstab(
        df_fy["Category"],
        df_fy["Fiscal_Month"],
        margins=True,
        margins_name="Total"
    )
    
    # Create value pivot table (sum of obligations)
    value_pivot = pd.crosstab(
        df_fy["Category"],
        df_fy["Fiscal_Month"],
        values=df_fy["Obligations_Float"],
        aggfunc='sum',
        margins=True,
        margins_name="Total Value"
    )
    
    # Rename columns to month names
    column_mapping = {i: FISCAL_MONTHS[i-1] for i in range(1, 13)}
    count_pivot = count_pivot.rename(columns=column_mapping)
    value_pivot = value_pivot.rename(columns=column_mapping)
    
    # Ensure all months are present (fill missing with 0)
    for month in FISCAL_MONTHS:
        if month not in count_pivot.columns:
            count_pivot[month] = 0
        if month not in value_pivot.columns:
            value_pivot[month] = 0
    
    # Reorder columns for count pivot
    ordered_cols = [col for col in FISCAL_MONTHS if col in count_pivot.columns] + ["Total"]
    count_pivot = count_pivot[ordered_cols]
    
    # Reorder columns for value pivot (handle different margin column name)
    value_ordered_cols = [col for col in FISCAL_MONTHS if col in value_pivot.columns]
    if "All" in value_pivot.columns:
        value_ordered_cols.append("All")
        value_pivot = value_pivot[value_ordered_cols]
        value_pivot = value_pivot.rename(columns={"All": "Total"})
    else:
        value_pivot = value_pivot[value_ordered_cols]
    
    # Rename value rows
    value_pivot.index = [f"{idx} Value" if idx != "Total Value" else idx for idx in value_pivot.index]
    
    # Filter to get contract and grant values specifically
    contract_value_row = value_pivot[value_pivot.index.str.contains("Contracts Value", na=False)].copy()
    grant_value_row = value_pivot[value_pivot.index.str.contains("Grants Value", na=False)].copy()
    total_value_row = value_pivot[value_pivot.index == "Total Value"].copy()
    
    # Rename for clarity
    if not contract_value_row.empty:
        contract_value_row.index = ["Contract Value"]
    if not grant_value_row.empty:
        grant_value_row.index = ["Grant Value"]
    
    # Calculate Total column if missing (sum all month columns)
    month_cols = [col for col in value_pivot.columns if col != "Total"]
    if not contract_value_row.empty:
        contract_value_row["Total"] = contract_value_row[month_cols].sum(axis=1)
    if not grant_value_row.empty:
        grant_value_row["Total"] = grant_value_row[month_cols].sum(axis=1)
    if not total_value_row.empty:
        total_value_row["Total"] = total_value_row[month_cols].sum(axis=1)
    
    # Create formatted copies to avoid dtype conversion warnings
    all_cols = month_cols + ["Total"]
    
    # Format contract values
    if not contract_value_row.empty:
        formatted_contract = contract_value_row.copy()
        for col in all_cols:
            if col in formatted_contract.columns:
                formatted_contract[col] = formatted_contract[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        contract_value_row = formatted_contract
    
    # Format grant values
    if not grant_value_row.empty:
        formatted_grant = grant_value_row.copy()
        for col in all_cols:
            if col in formatted_grant.columns:
                formatted_grant[col] = formatted_grant[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        grant_value_row = formatted_grant
    
    # Format total values
    if not total_value_row.empty:
        formatted_total = total_value_row.copy()
        for col in all_cols:
            if col in formatted_total.columns:
                formatted_total[col] = formatted_total[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        total_value_row = formatted_total
    
    # Combine count and value tables
    result = pd.concat([count_pivot, contract_value_row, grant_value_row, total_value_row])
    
    return result




def process_fiscal_year(year: int, data_dir: Path, export: bool = False) -> Dict:
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
        
        # Note: Individual export removed - data will be combined later
    else:
        print("No data available")
    
    # Table 2: New awards by category (counts and values)
    print("\n2. New Awards (Modification 0) by Category and Month")
    print("-" * 60)
    
    awards_table = count_new_awards_by_category(df, year)
    if not awards_table.empty:
        print(tabulate(awards_table, headers="keys", tablefmt="grid"))
        
        # Note: Individual export removed - data will be combined later
    else:
        print("No new awards found")
    
    # Return raw data for export if requested
    if export:
        return get_awards_data_for_year(df, year)
    return {}


def main():
    """Main function."""
    args = parse_arguments()
    data_dir = Path("data")
    
    # Sort fiscal years in descending order
    fiscal_years = sorted(args.fys, reverse=True)
    
    print(f"Processing fiscal years: {', '.join(map(str, fiscal_years))}")
    if args.export:
        print("CSV export enabled - files will be saved to current directory")
    
    # Collect data from all fiscal years
    all_awards_data = {}
    for fy in fiscal_years:
        fy_data = process_fiscal_year(fy, data_dir, args.export)
        if fy_data:
            all_awards_data[fy] = fy_data
    
    # Export combined CSV if requested
    if args.export and all_awards_data:
        filename = create_combined_awards_csv(all_awards_data, fiscal_years)
        print(f"\nExported combined awards data to: {filename}")
    
    print(f"\n{'='*60}")
    print("Analysis complete")


if __name__ == "__main__":
    main()