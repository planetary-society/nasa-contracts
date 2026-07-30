# NASA Contracts Data Fetcher

This repository contains fiscal-year data collected from [NASA's Procurement Data View (NPDV)](https://prod.nais.nasa.gov/cgibin/npdv/npdv.cgi) and the Python script used to fetch it. Each annual CSV combines NPDV's 50-state, Washington, D.C., and Outside U.S. exports. Outside U.S. records use `International` in the derived `State` column.

## Data Access

Year-by-year award-action data for FY2005 through the current fiscal year is available in the `data/` subdirectory.

Each file is named `nasa_awards_{YYYY}.csv`, where `YYYY` is the four-digit fiscal year. An award appears in a fiscal year only when it was created or modified during that year. An award may remain active without appearing in a later file if it was not modified.

| Fiscal year | Source file |
| --- | --- |
| 2005 | [`nasa_awards_2005.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2005.csv) |
| 2006 | [`nasa_awards_2006.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2006.csv) |
| 2007 | [`nasa_awards_2007.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2007.csv) |
| 2008 | [`nasa_awards_2008.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2008.csv) |
| 2009 | [`nasa_awards_2009.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2009.csv) |
| 2010 | [`nasa_awards_2010.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2010.csv) |
| 2011 | [`nasa_awards_2011.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2011.csv) |
| 2012 | [`nasa_awards_2012.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2012.csv) |
| 2013 | [`nasa_awards_2013.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2013.csv) |
| 2014 | [`nasa_awards_2014.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2014.csv) |
| 2015 | [`nasa_awards_2015.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2015.csv) |
| 2016 | [`nasa_awards_2016.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2016.csv) |
| 2017 | [`nasa_awards_2017.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2017.csv) |
| 2018 | [`nasa_awards_2018.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2018.csv) |
| 2019 | [`nasa_awards_2019.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2019.csv) |
| 2020 | [`nasa_awards_2020.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2020.csv) |
| 2021 | [`nasa_awards_2021.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2021.csv) |
| 2022 | [`nasa_awards_2022.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2022.csv) |
| 2023 | [`nasa_awards_2023.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2023.csv) |
| 2024 | [`nasa_awards_2024.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2024.csv) |
| 2025 | [`nasa_awards_2025.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2025.csv) |
| 2026 | [`nasa_awards_2026.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_awards_2026.csv) |

### New award statistics

Annual summary files for FY2009 through the current fiscal year count new contract and grant awards by fiscal month and total their initial obligations. A new award is identified by the `Modification 0 (Base Record)` suffix in `Contract/Mod Number`; later modifications are not included in these statistics. Each file also includes a fiscal-year total row.

The value columns contain whole-dollar integers. They measure the obligations recorded on each award's base action, not all obligations recorded during the fiscal year. Use the full award listings above to analyze subsequent modifications, deobligations, or total award-action activity.

| Fiscal year | New award statistics |
| --- | --- |
| 2009 | [`nasa_new_award_stats_2009.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2009.csv) |
| 2010 | [`nasa_new_award_stats_2010.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2010.csv) |
| 2011 | [`nasa_new_award_stats_2011.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2011.csv) |
| 2012 | [`nasa_new_award_stats_2012.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2012.csv) |
| 2013 | [`nasa_new_award_stats_2013.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2013.csv) |
| 2014 | [`nasa_new_award_stats_2014.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2014.csv) |
| 2015 | [`nasa_new_award_stats_2015.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2015.csv) |
| 2016 | [`nasa_new_award_stats_2016.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2016.csv) |
| 2017 | [`nasa_new_award_stats_2017.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2017.csv) |
| 2018 | [`nasa_new_award_stats_2018.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2018.csv) |
| 2019 | [`nasa_new_award_stats_2019.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2019.csv) |
| 2020 | [`nasa_new_award_stats_2020.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2020.csv) |
| 2021 | [`nasa_new_award_stats_2021.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2021.csv) |
| 2022 | [`nasa_new_award_stats_2022.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2022.csv) |
| 2023 | [`nasa_new_award_stats_2023.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2023.csv) |
| 2024 | [`nasa_new_award_stats_2024.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2024.csv) |
| 2025 | [`nasa_new_award_stats_2025.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2025.csv) |
| 2026 | [`nasa_new_award_stats_2026.csv`](https://github.com/planetary-society/nasa-contracts/raw/refs/heads/master/data/nasa_new_award_stats_2026.csv) |

## Data Freshness

The current and two preceding fiscal-year award listings are refreshed daily to capture any updates made to awards in the NPDV. The current fiscal year's new award statistics are regenerated after each daily refresh.

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
- **TAS Code**: Treasury Account Symbol identifying the funding source — a two-character agency identifier, a four-character main account code, and an optional three-character subaccount code (FY2009 onward only). The fiscal year of the funds is not encoded in the TAS.
- **Solicitation ID**: Reference number for the original solicitation
- **Solicitation POC**: Point of contact for the solicitation
- **Description**: Brief description of the contracted work or modification

## Usage

You can run this extraction script yourself on any given FY:

```bash
.venv/bin/python fetch-contracts.py -fy 2025
```

or fetch data for multiple fiscal years:

```bash
.venv/bin/python fetch-contracts.py -fy 2024 2025
```

Specify a custom output directory (default is `./data`):

```bash
.venv/bin/python fetch-contracts.py -fy 2025 -dir /path/to/output
```

### Award statistics

[`award_stats.py`](award_stats.py) summarizes one or more annual files from the `data/` directory. For each fiscal year, it prints:

- total obligations by fiscal month, including a running annual total
- counts of new awards by category and fiscal month
- initial obligation values for those new awards

The script identifies a new award by the `Modification 0 (Base Record)` suffix in `Contract/Mod Number`. Printed dollar values are abbreviated in millions; source data and exported values remain whole-dollar integers.

Analyze one fiscal year:

```bash
.venv/bin/python award_stats.py --fys 2026
```

Analyze multiple fiscal years:

```bash
.venv/bin/python award_stats.py --fys 2026 2025 2024
```

Use `--export` without a path to retain the generated `new_awards_{minimum_year}_to_{maximum_year}.csv` filename, or pass a custom output path. Missing parent directories are created automatically. The export contains monthly contract and grant counts and initial obligation values for fiscal years that were successfully processed:

```bash
.venv/bin/python award_stats.py --fys 2026 2025 2024 --export
```

```bash
.venv/bin/python award_stats.py --fys 2026 2025 2024 --export local_dir/output_name.csv
```

FY2005–FY2008 combine contractor indicators and a trailing award descriptor in the `Award Type` field. The script recognizes unambiguous legacy contract and grant descriptors. Ambiguous types such as `Other`, `Intragovernmental`, and `Space Act Agreement` remain `Other` and are excluded from the exported contract/grant columns. The overall monthly obligation table is unaffected.

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
- **Indefinite-Delivery Vehicles**: Parent indefinite-delivery vehicle (IDV) contracts are not included in this dataset. Task orders, delivery orders, and other orders placed under those vehicles are included
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
