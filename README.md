# NASA Contracts Data Fetcher

This repository contains fiscal-year data collected from [NASA's Procurement Data View (NPDV)](https://prod.nais.nasa.gov/cgibin/npdv/npdv.cgi) and the Python script used to fetch it. Each annual CSV combines NPDV's 50-state, Washington, D.C., and Outside U.S. exports. Outside U.S. records use `International` in the derived `State` column.

## Data Access

Year-by-year award-action data for FY2005 through the current fiscal year is available in the `data/` subdirectory.

Each file is named `nasa_contracts_{YYYY}.csv`, where `YYYY` is the four-digit fiscal year. An award appears in a fiscal year only when it was created or modified during that year. An award may remain active without appearing in a later file if it was not modified.

## Data Freshness

The current and two preceding fiscal years are refreshed daily by GitHub Actions.

## Output Schemas

NPDV exposes two historical export schemas, which are retained rather than artificially normalized:

- FY2005–FY2008: 16 output columns, including the derived `State` and `District` columns; no `TAS Code`.
- FY2009 onward: 17 output columns, including `TAS Code`.

All source field values preserve NPDV's capitalization, punctuation, embedded quotes, and leading or trailing whitespace after decoding the export's transport-level quoting. The scraper does not sentence-case descriptions, title-case contractor names, or apply the acronym reference file.

### Output Data Column Descriptions

- **State**: Two-letter domestic jurisdiction code (for example, `CA` or `DC`), or `International` for NPDV's Outside U.S. export
- **District**: Source-reported congressional district prefixed with the state code (for example, `CA-12`, `MT-02`, `DC-98`, or `TX-NA`); blank when NPDV provides no district or for International records
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
- **TAS Code**: Treasury Account Symbol identifying the funding source (FY2009 onward only)
- **Solicitation ID**: Reference number for the original solicitation
- **Solicitation POC**: Point of contact for the solicitation
- **Description**: Brief description of the contracted work or modification


## Installation

No API key is required.

1. Clone this repository.
2. Create or activate a virtual environment.
3. Install the dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

## Usage

Basic usage with a single fiscal year:

```bash
.venv/bin/python fetch-contracts.py -fy 2025
```

Fetch data for multiple fiscal years:

```bash
.venv/bin/python fetch-contracts.py -fy 2024 2025
```

Specify a custom output directory (default is `./data`):

```bash
.venv/bin/python fetch-contracts.py -fy 2025 -dir /path/to/output
```

Run the test suite:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Known Limitations

- **Missing State Data**: NPDV's geographical query excludes records without a Place of Performance state
- **Upstream Coverage**: NPDV notes that intragovernmental awards are not comprehensively captured beginning in FY2007
- **Subcontract Exclusion**: The dataset does not include subcontract data. This is particularly relevant for JPL-related contracts, as JPL is operated by Caltech under contract, meaning their contracts are not directly reported in this system
- **District Assignment**: District values are extracted from NPDV's Place of Performance text and inherit any upstream omissions or coding errors
- **Legacy Award Types**: Some FY2005–FY2008 Award Type values contain compound, comma-separated source text; these strings are preserved verbatim rather than normalized for downstream category matching
- **Data Source Stability**: The script relies on NASA's NPDV database interface, which may change without notice

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Author

Casey Dreier, The Planetary Society

[planetary.org](https://planetary.org)
