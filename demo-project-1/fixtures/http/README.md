# HTTP source fixtures

Recorded snapshots for the two HTTP `QueryDef`s in
[`queries/reference`](../../queries/reference), fetched once and committed so the demo
still works with the network disabled. Both source APIs are public, read-only GET
endpoints with no API key.

- `country-facts.json` — response for `queries/reference/country-facts` with `name=Canada`.
- `currency-rate.json` — response for `queries/reference/currency-rate` with `to=CAD`.

Fetched 2026-09-09.

## Note: REST Countries substitution

The plan's original choice for the "country facts" source was REST Countries
(`https://restcountries.com/v3.1/name/{name}`) — the lead's concrete pick under the
founder's HTTP-source ruling, not the ruling itself (see
`spec/features/core-investigation-loop/README.md` assumption A1 in the `datatug` hub).
As of this fetch, every route under `restcountries.com` (v3.1 and v5 alike) 301-redirects
to a static "This API version has been deprecated" notice — the service is no longer
usable without registering for a different product. `queries/reference/country-facts.query.http`
therefore points at `countriesnow.space`'s keyless `GET /api/v0.1/countries/currency/q?country={name}`
endpoint instead, which is common/understandable in the same way and, conveniently, already
returns the ISO currency code the `currency-rate` query needs next.

`currency-rate.query.http` keeps the plan's Frankfurter choice but follows its 2026
domain move from `api.frankfurter.app` (still 301s, may not forever) to
`api.frankfurter.dev`.

`shipping/carrier-status` calls the synthetic carrier sandbox, is live-only and intentionally has no fixture: the CLI serves one fixture per query for every parameter value, so a recorded answer would report the wrong booking for other requests.
