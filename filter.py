#!/usr/bin/env python3
import csv
import sys
import argparse
import re
from datetime import datetime, timedelta

def format_table(rows):
    """
    Format a list of rows (each row is a list of strings) into a nicely formatted ASCII table.
    """
    if not rows:
        return ""
    
    ncols = len(rows[0])
    col_widths = [0] * ncols

    # Determine the maximum width for each column
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Create a horizontal separator line
    separator = '+' + '+'.join(['-' * (w + 2) for w in col_widths]) + '+'
    lines = [separator]

    # Header row
    header = rows[0]
    header_line = '|' + '|'.join(' ' + header[i].ljust(col_widths[i]) + ' ' for i in range(ncols)) + '|'
    lines.append(header_line)
    lines.append(separator)

    # Data rows
    for row in rows[1:]:
        line = '|' + '|'.join(' ' + str(row[i]).ljust(col_widths[i]) + ' ' for i in range(ncols)) + '|'
        lines.append(line)
    lines.append(separator)
    
    return "\n".join(lines)

def parse_mod_number(contract_mod_str):
    """
    Parse the 'Contract/Mod Number' field.
    
    Expected format:
      - "AwardID Modification P00006"  OR "AwardID Modification 460"
    Returns a tuple (award_id, mod_number) where mod_number is an integer.
    If the modification portion starts with "P", it is removed before conversion.
    """
    parts = contract_mod_str.split("Modification")
    if len(parts) < 2:
        # Fallback: treat entire string as award id and mod 0
        return contract_mod_str.strip(), 0
    award_id = parts[0].strip()
    mod_str = parts[1].strip()
    if mod_str.startswith("P"):
        mod_str = mod_str[1:]
    try:
        mod_num = int(mod_str)
    except ValueError:
        mod_num = 0
    return award_id, mod_num

def main():
    parser = argparse.ArgumentParser(
        description='Filter CSV rows by description or completion date range, display selected columns as an ASCII table, and extract unique rows to a new CSV file.'
    )
    parser.add_argument('csvfile', help='Path to the input CSV file')
    parser.add_argument('output_csv', help='Path to the output CSV file for filtered rows')
    parser.add_argument('--start_date', help="Start date (MM/DD/YYYY) for Completion Date filter. Defaults to 7 days ago.", default=None)
    parser.add_argument('--end_date', help="End date (MM/DD/YYYY) for Completion Date filter. Defaults to today.", default=None)
    parser.add_argument('--diff', help="CSV file containing 'Contract/Mod Number' column. Rows with Award IDs in this file will be excluded.", default=None)
    args = parser.parse_args()
    
    # Define filter criteria for description
    search_phrases = ["termination", "stop work", "terminated", "terminates","effectuates"]

    # Compute default date range (7 days ago to today) if not provided
    today = datetime.today()
    if args.start_date is None:
        start_date = today - timedelta(days=7)
    else:
        try:
            start_date = datetime.strptime(args.start_date, "%m/%d/%Y")
        except Exception:
            print("Invalid start_date format. Expected MM/DD/YYYY", file=sys.stderr)
            sys.exit(1)
            
    if args.end_date is None:
        end_date = today
    else:
        try:
            end_date = datetime.strptime(args.end_date, "%m/%d/%Y")
        except Exception:
            print("Invalid end_date format. Expected MM/DD/YYYY", file=sys.stderr)
            sys.exit(1)
    
    # Columns to extract and display
    columns_to_display = [
        "District", 
        "Contractor", 
        "Contract/Mod Number", 
        "Award Date", 
        "Completion Date", 
        "Award Type", 
        "Description"
    ]
    
    # Lists for display (with truncated Description) and CSV extraction (full data)
    display_rows = []
    csv_rows = []
    
    # Append header for both
    display_rows.append(columns_to_display)
    csv_rows.append(columns_to_display)
    
    # Process diff file if provided: extract Award IDs from its "Contract/Mod Number" column.
    excluded_award_ids = set()
    if args.diff:
        try:
            with open(args.diff, newline='', encoding='utf-8') as diff_file:
                diff_reader = csv.DictReader(diff_file)
                if "Contract/Mod Number" not in diff_reader.fieldnames:
                    print("Column 'Contract/Mod Number' not found in diff CSV file.", file=sys.stderr)
                    sys.exit(1)
                for diff_row in diff_reader:
                    diff_contract_mod = diff_row.get("Contract/Mod Number", "")
                    diff_award_id, _ = parse_mod_number(diff_contract_mod)
                    excluded_award_ids.add(diff_award_id)
        except FileNotFoundError:
            print(f"Diff file '{args.diff}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred while processing the diff file: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Dictionary to hold the most recent row per Award ID.
    # Key: Award ID, Value: tuple(modification number, row dict)
    latest_rows = {}
    print(len(excluded_award_ids), "Award IDs will be excluded based on the diff file.")
    try:
        with open(args.csvfile, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            # Ensure required columns exist
            for col in columns_to_display:
                if col not in reader.fieldnames:
                    print(f"Column '{col}' not found in CSV file.", file=sys.stderr)
                    sys.exit(1)
                    
            for row in reader:
                contract_mod = row.get("Contract/Mod Number", "")
                award_id, mod_num = parse_mod_number(contract_mod)
                
                # If the award ID is in the diff file, skip this row.
                if award_id in excluded_award_ids:
                    continue
                
                # Keep only the row with the highest modification number per Award ID.
                if award_id in latest_rows:
                    if mod_num > latest_rows[award_id][0]:
                        latest_rows[award_id] = (mod_num, row)
                else:
                    latest_rows[award_id] = (mod_num, row)
                    
    except FileNotFoundError:
        print(f"File '{args.csvfile}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while processing the file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Now apply the filter criteria on only the most recent modifications
    for award_id, (mod_num, row) in latest_rows.items():
        description_val = row.get("Description", "")
        comp_date_str = row.get("Completion Date", "")
        
        # Parse the completion date from the row
        try:
            row_comp_date = datetime.strptime(comp_date_str, "%m/%d/%Y")
        except Exception:
            # If parsing fails, skip the date-range check
            row_comp_date = None
        
        # Check if the row's completion date is within the specified range
        in_date_range = False
        if row_comp_date is not None:
            in_date_range = (start_date <= row_comp_date <= end_date)
        
        # Check if the most recent row meets either filtering condition:
        # - The description contains one of the search phrases, OR
        # - The completion date is within the date range.
        if any(re.search(r'\b' + re.escape(phrase) + r'\b', description_val, re.IGNORECASE) for phrase in search_phrases):
            # Extract only the selected columns
            row_values = [row.get(col, "") for col in columns_to_display]
            
            # For CSV extraction, add the full row (untruncated)
            csv_rows.append([str(value) for value in row_values])
            
            # For display, truncate the "Description" if it exceeds 200 characters
            row_display = row_values.copy()
            desc_index = columns_to_display.index("Description")
            if len(row_display[desc_index]) > 200:
                row_display[desc_index] = row_display[desc_index][:200] + "..."
            display_rows.append(row_display)
    
    print(f"Found {len(display_rows) - 1} rows matching the filter criteria.")
    
    # Write the full filtered rows to the output CSV file
    try:
        with open(args.output_csv, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerows(csv_rows)
        print(f"Filtered rows have been written to '{args.output_csv}'.")
    except Exception as e:
        print(f"An error occurred while writing to the output CSV file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()