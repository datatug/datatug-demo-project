# Direct Google Cloud Logging pilot — execution receipt

Status on 2026-10-19: **source and DALGO read verified; hosted consent and UI
journey not yet activated**. This optional live pilot uses the existing
`sneat-eur3-1` project as a log source. The default, reproducible DataTug demo
continues to read the committed local files described in [the guide](guide.md).
There is no log database, snapshot, ingestion service or aggregation system.

## What exists

| Item | Observed state |
| --- | --- |
| Logging bucket | `projects/sneat-eur3-1/locations/global/buckets/_Default`, active, 30-day retention |
| Log view | `projects/sneat-eur3-1/locations/global/buckets/_Default/views/datatug-log-evidence-pilot` |
| View filter | `log_id("datatug-log-evidence-pilot") AND resource.type="global"` |
| View IAM | No view-level binding was added; the inspected policy had no bindings |
| Pilot entries | Eight structured entries written on 2026-10-19 to the dedicated log ID: six for order `11039`, one each for `11038` and `11040` |
| Classification | Every payload has `synthetic: true`, `pilot_id: datatug-log-evidence-pilot-2026-10-19`, and an `event_index` |
| Source access tested | The active Google account could read the view, but had project `roles/editor`; this does **not** prove view-only IAM |
| Hosted production service | Read-only inspection of ready revision `datatug-cloud-00006-bwb` found no `DATATUG_PERSONAL_CLOUD_LOGS_ENABLED` variable, minimum instance, or instance-based CPU setting |

The eight Cloud Logging entry timestamps span
`2026-10-19T13:52:15.978008256Z` through
`2026-10-19T13:52:34.256091102Z`. The six order `11039` entries use provider
insert IDs `zskt5tf9o699d`, `1cw4bybf71nrip`, `uuahwwfb5mvfp`,
`ziosebfsb2lu8`, `1amb2z8f2nv2vg`, and `dx4bgbftyrg7w` in event order.

The payloads reproduce the committed Northwind fixture's six-event causal
sequence, with `scenario_time` holding the illustrative 2018 time. Cloud
Logging's entry timestamp is the **2026 pilot write time**. The synthetic
carrier HTTP 503 and `retry_budget=0` explain only this demonstration, not the
historical reason Northwind order 11039 lacks `ShippedDate`. No real Sneat
operational log was copied into the pilot log ID.

The view was created with `gcloud logging views create` and the eight entries
were written with `gcloud logging write --payload-type=json`. A direct view
read returned eight entries. The following check was executed successfully
with absolute UTC bounds. It remains repeatable while the bucket retains the
entries (30 days from the write), subject to the reader's view access:

```sh
gcloud logging read \
  'timestamp>="2026-10-19T13:52:00Z" AND timestamp<="2026-10-19T13:53:00Z" AND jsonPayload.pilot_id="datatug-log-evidence-pilot-2026-10-19"' \
  --project=sneat-eur3-1 --bucket=_Default --location=global \
  --view=datatug-log-evidence-pilot --freshness=30d --limit=20 \
  --format=json
```

The existing `cloudlogging.NewPersonalDB` adapter was also exercised with a
user token from the active `gcloud` session and this **fixed view resource**.
One bounded DALGO query used the inclusive UTC range
`2026-10-19T13:52:00Z` to `2026-10-19T13:53:00Z`, `order_id == "11039"`,
descending timestamp order and limit 10. It returned exactly six rows, in
this order: deferred shipment, zero retry budget, carrier HTTP 503, label
request, inventory reservation, order acceptance. The token was captured in
memory by a temporary local probe and was never printed or committed. This
establishes a real direct-read path through DALGO; it does not establish the
hosted OAuth consent, narrow IAM or browser path.

## Remaining live-pilot checks

- Configure a dedicated DataTug OAuth consent/client boundary with
  `https://www.googleapis.com/auth/logging.read` and the registered hosted
  callback. The existing `sneat-eur3-1` OAuth project also contains production
  Sneat clients, so changing its audience or using a shared user grant needs
  an explicit project choice.
- Give a separate low-privilege Google test identity
  `roles/logging.viewAccessor` **on this view only**; verify it can read this
  view and cannot query broader project logs. The current Editor account is
  unsuitable for that permission proof.
- Configure KMS, encrypted credential storage, the host's cleanup liveness,
  and exact Origin/callback settings; then enable the hosted flag and test
  consent, AG Grid query, `Remove view`, and account disconnect with a test
  identity. The hosted feature remains disabled until these checks pass.
- Confirm DataTug's hosted route can navigate from a structured record into
  the view and back. The committed local order-to-log route already does so;
  it must not be described as hosted functionality.

The view is temporary pilot state. Its resource description records
`sneat-eur3-1` project administrators as operational owner and a review date
of **2026-11-18**. The pilot ends when the hosted consent and narrow-IAM
checks finish or at that review, unless the owner explicitly extends it.
Proposed teardown, **not executed**, is `gcloud logging views delete
datatug-log-evidence-pilot --bucket=_Default --location=global
--project=sneat-eur3-1`. Deleting the view does not delete its entries;
the `_Default` bucket's observed retention is 30 days. No IAM grant, OAuth
client, KMS key, Cloud Run flag or minimum instance was created by this pilot
step. No incremental always-on Cloud Run spend has been introduced.
