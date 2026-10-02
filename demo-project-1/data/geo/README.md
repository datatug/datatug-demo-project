# Geo reference data (vendored from geo-ingitdb)

Three collections copied from [ingitdb/geo-ingitdb](https://github.com/ingitdb/geo-ingitdb)
so the demo project is self-contained and its saved queries have a pinned,
reviewable dataset:

- **countries** (252) - ISO 3166-1 codes and names.
- **population_wb** (216) - latest World Bank `SP.POP.TOTL` observation per country. Each record
  carries `indicator`, `year`, `source_url` and `fetched_at`.
- **country_aliases** (24) - the `Invoice.BillingCountry` spellings used by Chinook mapped to a
  `countries` record, with `source` provenance.

Refresh with `scripts/sync-geo-data.sh [path-to-geo-ingitdb]`. Open it with
`datatug query run --db ingitdb://<this directory> --from population_wb --no-policies`.
Population data: World Bank Open Data, CC BY 4.0; names and ISO codes: GeoNames, CC BY 4.0.
