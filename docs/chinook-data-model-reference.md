# Chinook logical reference and physical provenance

The optional `dataModels` document in `demo-project-1/datatug-project.json`
references `modelspec://github.com/demo-db/chinook/chinook` at source commit
`3e7bb316d8a438eb7e5930067997a4e4543a275c`, using the local alias `chinook-v1`.
The `local/chinook-local` and `prod/chinook-prod` bindings select that same alias.
Catalog selectors are existing folder keys under `environments/*/catalogs`,
not the filenames `chinook-local.sqlite` and `chinook-prod.sqlite` in their
connection configurations. These are metadata fixtures, not evidence that either
configured database exists or a live environment or engine has been tested.

The logical publisher is [demo-db/chinook](https://github.com/demo-db/chinook/tree/3e7bb316d8a438eb7e5930067997a4e4543a275c).
Its original `model/chinook.modelspec.json` has SHA256
`19be3e0f575e14aa999769da79ba3ecb7fe3cb7e6a7dee151399dcbebfc56a7b`.
An exact-byte copy and the publisher's MIT license are retained only under
`tests/fixtures/chinook-logical` as offline evidence. They are not a runtime
model store, registry, or generation input. `provenance.json` records the source
identity, exact hashes, and local resolution evidence from the explicitly pinned
registry commit `b034db05dc74c13e2503d5135d4b4f1f814077bf` (catalog SHA256
`f4103c609d1d8fc2422b854d3a2652b138ad7836fb28247e8576f3459013f631`).
That registry commit is a local resolution evidence pin, not a published
production configuration or signature claim.

The separate physical database pin remains in
`demo-project-1/fixtures/chinook/phase1-acceptance.json`: publisher
[datatug/chinook-database](https://github.com/datatug/chinook-database/tree/6334395117e2478a2712e083be614721341c26c9),
revision `6334395117e2478a2712e083be614721341c26c9`, path
`ChinookDatabase/DataSources/Chinook_Sqlite.sqlite`, SHA256
`f82efedb6c5c40734609e168bc5be5616a2eca6b90ed0048451a8674625e03a3`.
The two repository addresses and source pins describe different artifacts;
matching Chinook names do not make the publishers or identities interchangeable.

## Explicit correspondence

Each logical record below maps to the same-named physical table in dbModel
`chinook`, schema `main`. Every listed logical field maps to a physical column
with exactly the same spelling. The offline check compares all eleven record
field sets and ordered primary keys against the scanned
`demo-project-1/dbmodels/chinook/main/tables/<Table>/main.<Table>.columns.json`
files; their original byte hashes are retained in `provenance.json`.

| Logical record / physical table | Same-name logical field / physical column pairs |
| --- | --- |
| Album | `AlbumId`, `ArtistId`, `Title` |
| Artist | `ArtistId`, `Name` |
| Customer | `Address`, `City`, `Company`, `Country`, `CustomerId`, `Email`, `Fax`, `FirstName`, `LastName`, `Phone`, `PostalCode`, `State`, `SupportRepId` |
| Employee | `Address`, `BirthDate`, `City`, `Country`, `Email`, `EmployeeId`, `Fax`, `FirstName`, `HireDate`, `LastName`, `Phone`, `PostalCode`, `ReportsTo`, `State`, `Title` |
| Genre | `GenreId`, `Name` |
| Invoice | `BillingAddress`, `BillingCity`, `BillingCountry`, `BillingPostalCode`, `BillingState`, `CustomerId`, `InvoiceDate`, `InvoiceId`, `Total` |
| InvoiceLine | `InvoiceId`, `InvoiceLineId`, `Quantity`, `TrackId`, `UnitPrice` |
| MediaType | `MediaTypeId`, `Name` |
| Playlist | `Name`, `PlaylistId` |
| PlaylistTrack | `PlaylistId`, `TrackId` |
| Track | `AlbumId`, `Bytes`, `Composer`, `GenreId`, `MediaTypeId`, `Milliseconds`, `Name`, `TrackId`, `UnitPrice` |

This correspondence concerns names and primary keys. It does not establish type
conversion, constraint equivalence, semantic meaning eligibility, or automatic
engine conversion. No scanned dbModel, meaning, or query metadata is rewritten.
The existing `scripts/prepare_chinook.py` creates a DALgo-readable derived SQLite
copy by adding a text `id` proxy column from each table's primary key. This
adapter column is outside the logical schema above; the pinned upstream file
and its digest remain separate from the derived copy and its digest.

## Verification and compatibility

From the repository root:

```sh
python3 tests/test_chinook_data_models.py -v
cd tests
go test data_models_metadata_test.go -v
```

The Python checks verify metadata bindings, exact source/license hashes, all
record/field/key correspondence, physical metadata hashes, and the distinct
physical pin. The Go check uses the existing dependency pin and exercises actual
Core `ProjectFile` decode/encode preservation of `dataModels`, `dbModels`, and
`connectionCatalog`. With Core v0.75.0 it passes through the existing opaque
metadata path. This is serializer evidence, not a guarantee that every older
binary/provider safely preserves references during project saves. Upgrade known
writers before using references in production; retain original bytes for
rollback. The fixture change does not require an invented Core publication or
change the existing test module's dependency pins.
