# NASA Contracts Data Fetcher

This is both a data collection and python script that collates NASA contract data from [NASA's Procurement Data View (NPDV) database](https://prod.nais.nasa.gov/cgibin/npdv/npdv.cgi). The script downloads NASA contract data for all U.S. states and territories, by year, and outputs a single comprehensive CSV file.

## Data Access

Year-by-year contract data for FYs 2005 - current are availabe in the ```data/``` subdirectory.

Each year is in the format of ```nasa_contracts_{YYYY}``` where YYYY is the 4-digit fiscal year. Note that contracts are included in a fiscal year if **only if they are created or modified during that fiscal year**. Some contracts may still be open (based on their completion date) but unmodified. You must parse the data accordingly if you want to find all open contracts.

## Data Freshness

The three most recent fiscal years are refreshed on a weekly basis and pushed to this repo. (You can confirm using the last modified commit dates on the csv files).

### Output Data Column Descriptions

- **State**: Two-letter state/territory code (e.g., "CA", "NY")
- **District**: Congressional district code (e.g., "CA-12", "NY-03", or "00" for at-large (single) district states)
- **Contractor**: Name of the contracting organization
- **Contract/Mod Number**: Unique identifier for the contract or modification
- **NASA Center**: NASA center or facility managing the contract
- **Place of Performance**: Location where the contracted work is performed
- **Award Date**: Date when the contract or modification was awarded
- **Completion Date**: Expected completion date for the contract
- **Award Type**: Type of contract award (e.g., Delivery Order, Purchase Order)
- **Contractor Type - Indicators**: Business size and socioeconomic indicators
- **Obligations**: Current fiscal year funding obligated
- **Change in Award Value**: Change in total contract value from this modification
- **NAICS Code**: North American Industry Classification System code
- **TAS Code**: Treasury Account Symbol identifying the funding source
- **Solicitation ID**: Reference number for the original solicitation
- **Solicitation POC**: Point of contact for the solicitation
- **Description**: Brief description of the contracted work or modification


## Installation
You are welcome to run this script yourself. No API or other data access keys are required.

1. Clone this repository (or just copy the main script, acronym reference file is optional)
2. Install required dependencies:
```bash
pip install requests
```
Requires Python 3.6 or newer.

## Usage

Basic usage with a single fiscal year:
```bash
python nasa_contracts.py -fy 2025
```

Fetch data for multiple fiscal years:
```bash
python nasa_contracts.py -fy 2024 2025
```

Specify a custom output directory (default is ```./data```):
```bash
python nasa_contracts.py -fy 2025 -dir /path/to/output
```

You can also provide a custom or modified list of acronmys to capitalize in the output by providing a csv file with columns ```Acronym,Description``` in a ```references/nasa_acronmys.csv``` directory. This is optional.

## Known Limitations

- **Missing State Data**: Contracts without an associated Place of Performance (such as certain Commercial Lunar Payload Services contracts) will not appear in the dataset
- **Subcontract Exclusion**: The dataset does not include subcontract data. This is particularly relevant for JPL-related contracts, as JPL is operated by Caltech under contract, meaning their contracts are not directly reported in this system
- **District Assignment**: Congressional districts are derived from the place of performance field and may not always be accurate
- **Data Source Stability**: The script relies on NASA's NPDV database interface, which may change without notice

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Author

Casey Dreier, The Planetary Society

[planetary.org](https://planetary.org)