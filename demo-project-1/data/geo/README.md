# Geo reference data (vendored from geo-ingitdb)

Three collections copied from [ingitdb/geo-ingitdb](https://github.com/ingitdb/geo-ingitdb)
so the demo project is self-contained and its saved queries have a pinned,
reviewable dataset:

- **countries** (252) - ISO 3166-1 codes and names.
- **population_wb** (216) - latest World Bank `SP.POP.TOTL` observation per country. Each record
  carries `indicator`, `year`, `source_url`, `fetched_at` and `source_updated`. 36 countries have
  no row (for example Taiwan, Jersey, Guernsey and Vatican), so an inner join on `population_wb`
  drops them; the list is in the
  [geo-ingitdb README](https://github.com/ingitdb/geo-ingitdb#world-bank-population).
- **country_aliases** (24) - the `Invoice.BillingCountry` spellings used by Chinook mapped to a
  `countries` record, with `source` provenance.

Open it with
`datatug query run --db ingitdb://<this directory> --from population_wb --no-policies`.

## Provenance and refresh

[`.vendored-from`](.vendored-from) records the geo-ingitdb commit this copy was taken from.
Refresh with `scripts/sync-geo-data.sh [path-to-geo-ingitdb]`; it replaces only the managed
files (the three collections, `.ingitdb/` and `DATA-LICENSE.md`) and leaves this README alone.
`scripts/sync-geo-data.sh --check [path-to-geo-ingitdb]` fails when the vendored files differ
from that checkout; CI runs it against the recorded commit, so the copy cannot drift or be
edited unnoticed.

## Attribution and licence

This directory is a **derived and modified** copy of third-party data; the full statement,
including what was changed, is in [DATA-LICENSE.md](DATA-LICENSE.md) (vendored from geo-ingitdb).

- **Population (`population_wb`)**: World Bank, World Development Indicators, indicator
  [SP.POP.TOTL](https://data.worldbank.org/indicator/SP.POP.TOTL) ("Population, total"),
  retrieved from the World Bank Indicators API v2
  (`https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json&mrnev=1`).
  © The World Bank, licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Modified: only the latest
  non-empty observation per country is kept, aggregates (regions, income groups, "World") and
  entities without a `countries` record are dropped, and rows are re-keyed by ISO 3166-1
  alpha-2 code.
- **Countries and ISO codes (`countries`)**: © [GeoNames](https://www.geonames.org/)
  (<https://download.geonames.org/export/dump/>, `countryInfo.txt`), licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Modified: re-keyed by lowercase
  ISO 3166-1 alpha-2 code with renamed columns and stored as one JSON file per country.
- **`country_aliases`** is hand-checked mapping data with no third-party content.

Neither the World Bank nor GeoNames endorses this project or the changes made to their data.
