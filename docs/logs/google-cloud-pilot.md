# Direct Google Cloud Logging pilot — execution receipt

Status on 2026-10-19: **source and DALGO read verified; the gated production
UI is deployed, but hosted sign-in and consent are not verified**. This
optional live pilot uses the existing `sneat-eur3-1` project as a log source.
The default, reproducible DataTug demo
continues to read the committed local files described in [the guide](guide.md).
There is no log database, snapshot, ingestion service or aggregation system.
The DataTug OAuth web client now exists in the shared project; the verified
Firebase identity at `auth.sneat.co` remains shared with Sneat. Popup and
redirect attempts reached the shared helper but did not produce a usable
DataTug session. This records configuration progress only, not a completed
Google user grant or hosted log journey.

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
| Hosted service and cleanup | Host PR #15's historical provider snapshot at 18:05:25 UTC found production datatug-cloud-00013-hjk and preview datatug-cloud-preview-00014-np9, both at 100% traffic on image e5925566ab0c81f95a7bbe46b73fd9836f1c024f; neither had Cloud Logs environment variables or OAuth secret bindings, and no pilot Scheduler job existed. README-only host PR #16 merged at b5c6c8444fd3c98c177d441b47f691cbdfae1d5b. Candidate build/lint [39299058079](https://github.com/datatug/datatug-cloud/actions/runs/39299058079), post-merge Go CI [39299663820](https://github.com/datatug/datatug-cloud/actions/runs/39299663820), and deployment [39299949750](https://github.com/datatug/datatug-cloud/actions/runs/39299949750) passed. Provider readback at 18:11:59 UTC found production datatug-cloud-00014-lhg and preview datatug-cloud-preview-00015-6w6 at 100% traffic on the PR #16 image; both had no Cloud Logs environment variables or OAuth secret bindings, and no pilot Scheduler job existed. GET /health-check returned 200 with X-Sneat-Service: datatug-cloud at 18:12:01 UTC. The user-routes switch omits all eight handlers while retaining cleanup registration and credentials when enabled; it was not exercised with the master feature enabled. No grant, live cleanup or shutdown proof exists. |
| Production DataTug UI | [Apps PR #407](https://github.com/datatug/datatug-apps/pull/407) merged at `a63cfe2883d1078f9a3c1058483197126ea372de`; post-merge [CI run 39292521711](https://github.com/datatug/datatug-apps/actions/runs/39292521711) passed preflight, build, test, Cloud Logs E2E and deploy-gate checks. Cloudflare workflow [39293867514](https://github.com/datatug/datatug-apps/actions/runs/39293867514) succeeded; public build-info reports the same SHA and version `0.1.0+1201`. The production UI flag is on behind the fail-closed server-confirmed UID gate; Business Preview is off. No post-deploy CI smoke was run, and the absent backend configuration leaves access denied. |

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

## Approved credential provisioning — 2026-10-19

The owner approved storing this client's JSON credentials in Secret Manager and
creating the named KMS resources. The following operations were executed:

- Stored the client secret as version `1` of
  `projects/sneat-eur3-1/secrets/datatug-cloud-logs-oauth-client-secret`, with
  user-managed replication in `europe-west3`. The downloaded JSON's client ID,
  project and callback were checked before upload. Secret read-back matched in
  memory, and the temporary JSON was deleted. No credential file is in Git.
- Created key ring `datatug-cloud-logs` and key `google-oauth-grants` in
  `sneat-eur3-1/europe-west3`. Its primary version `1` is enabled, uses software
  protection, and has purpose `ENCRYPT_DECRYPT`. This verifies provisioning,
  not application encrypt/decrypt permission or a completed user grant.

During browser recovery, a tool ignored output suppression and emitted the
client secret into private tool output. Independent security review requires
replacing it before activation, storing the replacement as a new pinned Secret
Manager version, and retiring the exposed version after verification. The owner
handoff is at this client's **Add secret** control. No Google user-token
revocation is needed: no user grant or runtime secret binding exists.

After automatic approval review required exact permission, the owner separately
approved and the following prerequisites were applied:

- `roles/cloudkms.cryptoKeyEncrypterDecrypter` for the existing runtime account
  `588648831063-compute@developer.gserviceaccount.com` on the named KMS key only.
- Version `1` of `datatug-cloud-logs-oauth-state-key`: a standard-base64 encoding
  of 32 random bytes, generated and transferred in memory, with read-back
  equality verified. Its sole replication location is `europe-west3`.

Existing project-level Secret Manager access remains unchanged. The runtime
identity is shared, so other workloads using it also have access to this new
key; that is an explicitly approved pilot limitation. The Scheduler job and
hosted activation are still unprovisioned. Generic release
wiring is merged in [CICD PR #44](https://github.com/sneat-co/cicd/pull/44)
at `9571a3c78a448598ccce184a2aa7625ab07d6a53`; its 133 fake-provider step
checks passed locally and independently. That is not provider activation.

## Remaining live-pilot checks

- Complete and verify consent using the dedicated OAuth web client already
  created in the shared `sneat-eur3-1` project. Its client ID is
  `588648831063-rr6titvvsu52j9n7gqc07uagqoru3lfd.apps.googleusercontent.com`
  and its registered callback is
  `https://api.sneat.cloud/v0/datatug/me/google-log-grants/oauth/callback`.
  The `auth.sneat.co` verified Firebase identity remains shared; no Google user
  grant has been completed.
- Give a separate low-privilege Google test identity
  `roles/logging.viewAccessor` **on this view only**; verify it can read this
  view and cannot query broader project logs. The current Editor account is
  unsuitable for that permission proof.
- Complete credential replacement and bind the new version only after verifying
  it. The named runtime's key-level permission and separate state key now exist.
  Provision the managed Cloud Scheduler OIDC POST to
  the existing `/_tasks` route only after the host route is deployed. The
  intended job is `datatug-personal-cloud-log-cleanup` in `europe-west3`, using
  `cloud-tasks-invoker@sneat-eur3-1.iam.gserviceaccount.com` and audience
  `https://datatug-cloud-354fvnqbaa-ey.a.run.app`; it should remain paused until
  the route and feature configuration are ready. No Scheduler job is provisioned;
  the existing task invoker already has Cloud Run invoke permission, verified
  by policy readback. Then enable the hosted flag and test consent,
  AG Grid query, `Remove view`, and account disconnect with a test identity.
  The hosted feature remains disabled until these checks pass.
- Host PR #15 added the private route-stop switch under the master feature
  flag: setting DATATUG_PERSONAL_CLOUD_LOGS_USER_ROUTES_ENABLED=0 omits all
  eight user handlers while retaining cleanup registration, credentials and
  task OIDC. The latest PR #16 deployment and provider receipt are listed above.
  No Cloud Logs environment configuration or Scheduler job was present, so the
  route stop with the master feature enabled was not exercised. The switch does
  not revoke grants or establish full shutdown. Source review identified a
  shutdown race: an in-flight finish can activate a completion after the initial
  revoke inventory, removing that completion and creating an active grant;
  cleanup only handles expiring completions and queued revocations. Before
  turning the master feature flag off after activation, prove a
  no-further-activation barrier across all serving and old revisions and
  in-flight start/callback/finish requests, then take a final active-grant
  inventory. Any late active grant needs a separately verified revocation path,
  followed by a generation-fenced drain of queued revocations and purge of all
  completion records while cleanup and keys remain available. This shutdown
  sequence has no live proof. Turning the master flag to 0 removes cleanup
  registration and its credential bindings.
- Resolve the shared Google login blocker before claiming the hosted browser
  journey. Popup and redirect attempts with the existing shared Firebase
  identity reached `auth.sneat.co` but did not return a usable DataTug session;
  the popup attempt returned `auth/popup-closed-by-user`. Public checks showed
  the shared helper returns HTTP 200, its `init.json` identifies
  `sneat-eur3-1` / `auth.sneat.co`, and both handler scripts match the canonical
  Firebase helper by SHA-256. These checks do not establish the browser-flow
  failure cause. A separate same-origin `createAuthUri` probe returned HTTP 400
  `INVALID_CONTINUE_URI` because `datatug.app` belongs to a different Firebase
  Hosting project. No identity or auth-domain change is proposed, and no auth
  configuration was mutated.
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
the `_Default` bucket's observed retention is 30 days. No view-only IAM grant,
Scheduler job, Cloud Run enable flag, or Google user grant has been created.
The approved KMS key, key-level runtime permission and both Secret Manager
versions exist as recorded above. No minimum-instance configuration was introduced
by this pilot step.
