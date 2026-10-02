# Entity: Country

## Fields

- **Exported**:
  [JSON](https://raw.githubusercontent.com/datatug/datatug-meta-iso/main/geo/country/country.json),
  [docs](https://github.com/datatug/datatug-meta-iso/tree/main/geo/country)
  - **ID**: string
  - **Name**: string
- **Local** (declared in [Country.entity.json](Country.entity.json), used by this demo project):
  - **Name**: string — `namePatterns: ["Country"]`, declared against the `Country` column
    on Chinook Customer rows and inGitDB support notes.
  - **Currency**: string — the ISO currency code for the country (e.g. `CAD`), used as the
    `Country.Currency` parameter tag on the `currency-rate` HTTP query
    (see [queries/reference](../../queries/reference)).
  - **alpha2**, **alpha3**: string — ISO 3166-1 codes (`IE`, `IRL`), mapped to the `geo` inGitDB
    reference data (`countries.iso2`/`iso3`, `population_wb.iso3`; see [data/geo](../../data/geo)).
  - **Name** is also mapped to `Invoice.BillingCountry` in Chinook and to `country_aliases.alias`,
    the table that turns Chinook's spellings (`USA`, `Czech Republic`) into `countries` records.
    That mapping is what lets `sales/chinook-sales-per-capita` join sales to World Bank population.
