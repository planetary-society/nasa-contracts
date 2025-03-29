#!/usr/bin/env python3
import requests
import csv
import argparse
from titlecase import titlecase

def get_award_details(award_ids, award_type_codes):
    """
    Given a list of Award IDs and a list of award type codes, this function builds the payload
    and calls the USASpending API endpoint.
    """
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "filters": {
            "keywords": award_ids,
            "time_period": [{
                "start_date": "2007-10-01",
                "end_date": "2025-09-30"
            }],
            "award_type_codes": award_type_codes
        },
        "fields": [
            "Award ID", 
            "Recipient Name", 
            "Award Amount", 
            "Total Outlays", 
            "Description", 
            "Award Type", 
            "def_codes", 
            "COVID-19 Obligations", 
            "COVID-19 Outlays", 
            "Infrastructure Obligations", 
            "Infrastructure Outlays", 
            "Awarding Agency", 
            "Awarding Sub Agency", 
            "Start Date", 
            "End Date", 
            "recipient_id", 
            "prime_award_recipient_id"
        ],
        "page": 1,
        "limit": 100,
        "sort": "Award Amount",
        "order": "desc",
        "subawards": False
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("results", [])
    else:
        print("Error querying API for award type codes", award_type_codes, ":", response.status_code, response.text)
        return []

def extract_award_ids_from_csv(csv_filename):
    """
    Reads the CSV file and extracts unique Award IDs from the 'Contract/Mod Number' column.
    The Award ID is assumed to be the first token before a space.
    """
    award_ids = []
    with open(csv_filename, mode='r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            contract_mod = row.get("Contract/Mod Number", "") or row.get("Award ID", "")
            if contract_mod:
                award_id = contract_mod.split()[0]
                award_ids.append(award_id)
    # Return unique award IDs
    return list(set(award_ids))

def update_csv_with_award_details(input_csv, output_csv, award_details_map):
    """
    Reads the input CSV file, appends additional columns (Award ID, Start Date, End Date, Award Amount, Total Outlays)
    based on the Award ID extracted from the 'Contract/Mod Number' column, and writes all rows
    to a new output CSV file. If no award details are found for a given row, the extra columns
    remain empty.
    """
    with open(input_csv, mode='r', newline='', encoding='utf-8') as infile, \
         open(output_csv, mode='w', newline='', encoding='utf-8') as outfile:
        
        reader = csv.DictReader(infile)
        # Append new headers to the existing ones.
        fieldnames = reader.fieldnames + ["Award ID", "Start Date", "End Date", "Award Amount", "Total Outlays", "USA Spending Description"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            contract_mod = row.get("Contract/Mod Number", "") or row.get("Award ID", "")
            if contract_mod:
                extracted_award_id = contract_mod.split()[0]
            else:
                extracted_award_id = ""
            
            # Lookup the award details using the extracted Award ID
            details = award_details_map.get(extracted_award_id, {})
            row["Award ID"] = extracted_award_id
            row["Start Date"] = details.get("Start Date", "")
            row["End Date"] = details.get("End Date", "")
            row["Award Amount"] = details.get("Award Amount", "")
            row["Total Outlays"] = details.get("Total Outlays", "")
            row["USA Spending Description"] = details.get("Description", "").capitalize()
            writer.writerow(row)

def main():
    # Parse CLI arguments for input and output CSV file paths.
    parser = argparse.ArgumentParser(description='Update CSV file with award details from the USASpending API.')
    parser.add_argument('input_csv', help='Path to the input CSV file')
    parser.add_argument('output_csv', help='Path to the output CSV file with award details')
    args = parser.parse_args()

    input_csv = args.input_csv
    output_csv = args.output_csv

    # Extract unique Award IDs from the input CSV file.
    award_ids = extract_award_ids_from_csv(input_csv)
    if not award_ids:
        print("No Award IDs found in input CSV.")
        return
    
    # Define groups of award type codes.
    grants_codes = ["02", "03", "04", "05"]
    contracts_codes = ["A", "B", "C", "D"]
    idvs_codes = ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]
    
    # Query the API for each award type group.
    print("Querying grants...")
    grants_results = get_award_details(award_ids, grants_codes)
    
    print("Querying contracts...")
    contracts_results = get_award_details(award_ids, contracts_codes)
    
    print("Querying IDVs...")
    idvs_results = get_award_details(award_ids, idvs_codes)
    
    # Merge all API results together.
    all_results = grants_results + contracts_results + idvs_results
    
    # Build a mapping from Award ID to its details.
    award_details_map = {}
    for result in all_results:
        award_id_key = result.get("Award ID", "")
        if award_id_key:
            award_details_map[award_id_key] = result
            
    # Update the input CSV with additional columns based on the award details.
    update_csv_with_award_details(input_csv, output_csv, award_details_map)
    print(f"Modified CSV file saved successfully as '{output_csv}'.")

if __name__ == "__main__":
    main()