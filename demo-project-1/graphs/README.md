# CodeGrapher snapshots

The manifest names content-addressed project and stored-schema graphs. Project snapshots contain asset names and declared references, without query bodies, row data, credentials, or source endpoints. Stored schema comes from the displayed project revision; it is not a live database observation. `chinook-meanings.json` projects authored bindings from its independently pinned CC0 MeaningGraph source. The unchanged Chinook schema retains its upstream MIT license described in the repository README.

The exporter requires Python 3 and PyYAML 6.0.3, declared in `scripts/requirements-codegrapher.txt`. To reproduce the initial snapshots from the original source revision:

```sh
python3 scripts/export-codegrapher-graphs.py --revision e36e15513be6d4a3439119e477cbdc81cba31c73 --generated-at 2026-10-29T22:08:00Z
python3 scripts/test-codegrapher-graphs.py
```

The repository README links use the eventual published snapshot commit and its digest. Regeneration produces new files; keep previously published content-addressed files so existing links retain their original meaning. Opening a graph does not execute a query or write project data.
