# NASA Contracts Data Fetcher

This repository contains fiscal-year data collected from [NASA's Procurement Data View (NPDV)](https://prod.nais.nasa.gov/cgibin/npdv/npdv.cgi) and the Python script used to fetch it. Each annual CSV combines NPDV's 50-state, Washington, D.C., and Outside U.S. exports. Outside U.S. records use `International` in the derived `State` column.

## Data Access

Year-by-year award-action data for FY2005 through the current fiscal year is available in the `data/` subdirectory.

Each file is named `nasa_awards_{YYYY}.csv`, where `YYYY` is the four-digit fiscal year. An award appears in a fiscal year only when it was created or modified during that year. An award may remain active without appearing in a later file if it was not modified.

## Data Freshness

The current and two preceding fiscal years are refreshed daily by GitHub Actions. NPDV publishes the current fiscal year only through the previous month end, so the newest file lags by up to one month no matter how often it is refreshed.

## Output Schemas

NPDV exposes two historical export schemas, which are retained rather than artificially normalized:

- FY2005–FY2008: 16 output columns, including the derived `State` and `District` columns; no `TAS Code`.
- FY2009 onward: 17 output columns, including `TAS Code`.

### Output Data Column Descriptions

- **State**: Two-letter domestic jurisdiction code (for example, `CA` or `DC`), or `International` for NPDV's Outside U.S. export
- **District**: Source-reported congressional district prefixed with the state code, always as a two-digit number from `00` to `98` — `CA-12` for a numbered district, `MT-00` for an at-large jurisdiction, `DC-98` for the District of Columbia's delegate seat; blank when NPDV reports no district and for International records
- **Contractor**: Name of the contracting organization
- **Contract/Mod Number**: Unique identifier for the contract or modification
- **NASA Center**: NASA center or facility managing the contract
- **Place of Performance**: Location where the contracted work is performed
- **Award Date**: Date when the contract or modification was awarded
- **Completion Date**: End of the contract period of performance, covering the contract and all modifications to it; unexercised options are not reflected
- **Award Type**: Type of award (e.g., Delivery Order, Purchase Order)
- **Contractor Type - Indicators**: Contractor category and socioeconomic indicators — business size (large or small, and small-business subcategories such as 8(a), woman-owned, and SBIR), educational institution, nonprofit institution, or intragovernmental
- **Obligations**: Funding obligated during the file's fiscal year, as a whole-dollar integer with no currency symbol or thousands separators (for example, `0`, `35000`, or `-16915` for a deobligation). This is not the cumulative total obligated since award
- **Change in Award Value**: Change this action makes to the total amount agreed upon, including all deliverables and exercised options, in the same whole-dollar integer format. Options that have not been exercised in writing are excluded, so this column is not a measure of contract ceiling
- **NAICS Code**: North American Industry Classification System code
- **TAS Code**: Treasury Account Symbol identifying the funding source — a two-character agency identifier, a four-character main account code, and an optional three-character subaccount code (FY2009 onward only). The fiscal year of the funds is not encoded in the TAS
- **Solicitation ID**: Reference number for the original solicitation
- **Solicitation POC**: Point of contact for the solicitation
- **Description**: Brief description of the contracted work or modification

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

## Tests

Run the default suite, which parses fixtures transcribed from real NPDV exports and checks the committed CSVs against the parser's guarantees:

```bash
python -m unittest discover -s tests -v
```

The committed-data checks scan one file per source schema by default. To scan every fiscal year in `data/` instead (roughly 13 seconds for all 795,000 rows):

```bash
NPDV_FULL_DATA_TESTS=1 .python -m unittest discover -s tests -v
```

Integration tests that query NPDV are skipped unless explicitly enabled. They issue four requests for Vermont and Outside U.S., NPDV's two smallest exports, plus one deliberately malformed query:

```bash
NPDV_LIVE_TESTS=1 python -m unittest discover -s tests -v
```

## Known Limitations

- **Purchase Order Threshold**: NPDV includes all contracts, assistance awards, cooperative agreements, and space act agreements, but only those purchase orders with a value greater than $25,000. Smaller purchase orders are absent from the dataset entirely
- **Missing State Data**: NPDV's geographical query excludes records without a Place of Performance state
- **Upstream Coverage**: NPDV notes that intragovernmental awards are not comprehensively captured beginning in FY2007
- **Subcontract Exclusion**: The dataset does not include subcontract data. This is particularly relevant for JPL-related contracts, as JPL is operated by Caltech under contract, meaning their contracts are not directly reported in this system
- **District Assignment**: District values are extracted from NPDV's Place of Performance text and inherit any upstream omissions or coding errors
- **Legacy Award Types**: Some FY2005–FY2008 Award Type values contain compound, comma-separated source text; these strings are preserved verbatim rather than normalized for downstream category matching
- **Data Source Stability**: The script relies on NASA's NPDV database interface, which may change without notice

## License

This project is open source and available under the MIT License.

## Author

Casey Dreier, The Planetary Society

[planetary.org](https://planetary.org)
