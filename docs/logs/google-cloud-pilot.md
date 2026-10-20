# Direct Google Cloud Logging pilot — execution receipt

Status on 2026-10-20: **source and DALGO read verified; the production
connection page is reachable after fresh Google basic sign-in; separate Cloud
Logging consent, grant, view reads and hosted log query remain unverified**. This
optional live pilot uses the existing `sneat-eur3-1` project as a log source.
The default, reproducible DataTug demo
continues to read the committed local files described in [the guide](guide.md).
There is no log database, snapshot, ingestion service or aggregation system.
The DataTug OAuth web client exists in the shared project; the verified
Firebase identity at `auth.sneat.co` remains shared with Sneat. A fresh Google
basic sign-in reached the authenticated Cloud Logs connections page, which
showed no accounts or views. Authenticated GET connections requests returned
HTTP 200 at `13:09:41.557Z` and `13:09:41.993Z`; POST OAuth start returned
HTTP 200 at `13:10:08.380Z` on production `00010-bjt`. The flow reached the
account chooser, where Google did not recognize the selected provider account.
No `logging.read` consent or grant was completed. An earlier
same-origin `createAuthUri` probe returned HTTP 400
`INVALID_CONTINUE_URI`; the callback-domain ownership issue remains unresolved.

## Current operator targets — checked 2026-10-20

[Host PR #18](https://github.com/datatug/datatug-cloud/pull/18) moved new
deployments to Belgium (`europe-west1`), at merge
`ffd7b6fc2216cce9c7691678481fea35fd984ad1`. Use the Belgium service URL
`https://datatug-cloud-354fvnqbaa-ew.a.run.app` for the future cleanup POST and
its OIDC audience. The intended Scheduler location is also `europe-west1`.
The approved KMS key and Secret Manager replication remain in `europe-west3`;
the host move did not move these resources.

Provider readback at 07:39:57 UTC found Belgium production revision
`datatug-cloud-00002-lcj` and preview `datatug-cloud-preview-00002-4gc`, each
at 100% traffic on the PR #18 image tag. Both GET health checks returned 200
with `X-Sneat-Service: datatug-cloud` at 07:41:09 UTC. The Frankfurt services
remain present, configured on the earlier PR #17 revisions recorded below. Neither
region had personal Cloud Logs environment variables or OAuth secret bindings,
and neither had the named pilot Scheduler job. Before activation, inventory
both regions and any tagged revisions, direct targets and in-flight work;
checking only the new Belgium deployment does not establish the activation
barrier. These were read-only checks; no service was enabled or deleted.

The execution receipts below retain their original dates and regions.

### Current setup — 2026-10-20

Host PR #25 merged as `9d055b12fae5ae74793e8f452bd7fc8714e22d33`. Exact-main
CI passed 10/10 at `13:00:44Z`; deployment `39426215088` succeeded. Provider
readback at `13:07:48Z` found Belgium production `datatug-cloud-00010-bjt` and
preview `datatug-cloud-preview-00009-2fx`, both at 100% on the merged image.
Production master and user routes are `1`, secret references are `2`/`1`, and
the allowlisted UID matches. Preview and Frankfurt remain without pilot
configuration; all four health checks returned HTTP 200. The standard Firebase
`auth_time` fix is now deployed.

The approved activation CAS resumed epoch `1` to epoch `2` at
`13:09:15.798Z` on production `00010-bjt`; readback confirmed
`paused=false` and durable epoch `2`. The disposable Scheduler probe was
deleted and returned `NOT_FOUND` at `13:10:25Z`. The recurring cleanup remains
enabled and minutely; three scheduled target requests returned HTTP 200 at
`13:06:08Z`, `13:07:07Z` and `13:08:04Z` on `00010-bjt`, using OIDC without
`X-Cron-Secret`. These responses do not identify affected records.

Fresh Google basic sign-in reached the authenticated Cloud Logs connections
page, which showed no accounts or views. Authenticated GET connections returned
HTTP 200 at `13:09:41.557Z` and `13:09:41.993Z`; POST OAuth start returned
HTTP 200 at `13:10:08.380Z` on `00010-bjt`. The flow reached the account
chooser, where Google did not recognize the selected provider account. No
Logging consent, grant or query was completed. Positive
view-only and negative broader-project reads remain
pending, as does the hosted AG Grid journey.

Live production readback at `12:26:19Z` found Belgium production revision
`datatug-cloud-00008-2rw` and preview revision `datatug-cloud-preview-00007-hmj`,
both at 100% traffic on image `852c5cacd7925d8e7d30749e3e9babfb88d201ba`.
Production runtime configuration references OAuth client Secret Manager
version `2` and state-key version `1`; the master feature flag and user routes
are both `1`. At this earlier readback, the allowlisted lifecycle was paused
at epoch `1`; it was later resumed as recorded above.
The private operator control returned HTTP 200 for OIDC status at
`11:51:44.410251Z` and HTTP 401 without authentication. A pause with expected
epoch `0` returned HTTP 200 at `12:01:27.524850Z`; Firestore readback confirmed
`paused=true` at epoch `1`. These receipts do not prove Google Logging consent,
a user log query or deletion of expired records. One owner-approved cleanup
check is recorded below.

The existing task invoker already has `run.invoker`; no new invoker IAM grant
was added. The restricted test identity has no direct project role; its
view-only binding is on the synthetic pilot view, but positive and negative
read checks remain pending. The managed cleanup job
`datatug-personal-cloud-log-cleanup` is enabled in `europe-west1` on
`* * * * *` UTC, using the existing task service account, Belgium service URL
as audience and the existing `/_tasks` URI. The approved scheduled target
request returned HTTP 200 at `12:22:00.796489Z` on revision
`datatug-cloud-00007-lt8`; OIDC target matched and `X-Cron-Secret` was absent.
The earlier single approved check returned HTTP 200 at `12:15:20.352921Z` on
revision `datatug-cloud-00006-fc2`. Neither receipt establishes which records
were deleted. At this checkpoint, the temporary Scheduler probe had been re-paused in the
operation's `finally` cleanup; it was later deleted and returned `NOT_FOUND` as
recorded above. Run `39421223763` attempt 2 passed WB 10/10 at
`12:26:53.834799Z`. The four Belgium and Frankfurt production/preview health
checks returned HTTP 200 with the expected service header. Preview and both
Frankfurt services had no personal Cloud Logs settings; the Frankfurt services
remain on their existing revisions. Post-deployment runtime readback confirms
master `1`, routes `1`, secret references `2`/`1` and the allowlisted UID match.

At the `12:26Z` checkpoint, lifecycle activation was still paused at epoch `1`
and the deployed image predated the auth-time fix. The later merge, deployment
and epoch-2 resume receipts are recorded above. No Google Cloud Logging user
grant exists; positive/negative view reads and hosted consent remain
unverified.

Before activation, preflight found all 35 retained DataTug revisions across
Belgium and Frankfurt and all 7 current project Cloud Run services without
personal Cloud Logs settings. All 9 credential roots were empty at
`11:36:36Z`. The deployed Firestore ruleset was byte-equal to reviewed origin
main SHA `a78abcd7e55258b93ba996b7bfe1e48149cfe029`, with SHA-256
`9038e32d45753b5ebe62ac078743da5b0cd7eadb40b9dfedae723c8bf245d8d2`. This
supports the pre-activation old-writer check; it is not a blanket shutdown
proof.

At the earlier 12:15 cleanup check, exactly one
`DataTugPersonalCloudLogCleanup` target request returned HTTP 200 at
`2026-10-20T12:15:20.352921Z` on production revision
`datatug-cloud-00006-fc2`. The temporary probe was re-paused in `finally` and
the managed recurring job was paused at that checkpoint. This receipt proves
the target request returned success, not which records (if any) were deleted.

The CICD scheduler-header fix merged as [PR #45](https://github.com/sneat-co/cicd/pull/45)
at `3d89e25a11d042b4c855765e58ec876838780679`; its fake-provider regression
passed on the exact candidate and post-merge main CI passed 6/6. OIDC updates
now clear workflow-owned custom headers before attaching OIDC. No protocol
change was made.

The approved managed cleanup schedule is enabled and its target returned HTTP
200 as recorded above; no receipt identifies affected records. Automatic
review had rejected an earlier potentially destructive operation; the owner
later approved the bounded cleanup check and recurring job. No Cloud Logging
user grant exists.
Earlier dated provider snapshots below remain historical and do not describe
the current runtime configuration or Scheduler state.

## What exists

| Item | Observed state |
| --- | --- |
| Logging bucket | `projects/sneat-eur3-1/locations/global/buckets/_Default`, active, 30-day retention |
| Log view | `projects/sneat-eur3-1/locations/global/buckets/_Default/views/datatug-log-evidence-pilot` |
| View filter | `log_id("datatug-log-evidence-pilot") AND resource.type="global"` |
| View IAM | A view-level `roles/logging.viewAccessor` binding was added for the restricted test identity on this synthetic view. Policy readback confirms the binding; positive view read and negative broader-project read are not yet verified. The earlier source read used an Editor identity and does not prove least-privilege access. |
| Pilot entries | Eight structured entries written on 2026-10-19 to the dedicated log ID: six for order `11039`, one each for `11038` and `11040` |
| Classification | Every payload has `synthetic: true`, `pilot_id: datatug-log-evidence-pilot-2026-10-19`, and an `event_index` |
| Source access tested | The active Google account could read the view, but had project `roles/editor`; this does **not** prove view-only IAM |
| Hosted service and cleanup | Host PR #15's historical provider snapshot at 18:05:25 UTC found production datatug-cloud-00013-hjk and preview datatug-cloud-preview-00014-np9, both at 100% traffic on image e5925566ab0c81f95a7bbe46b73fd9836f1c024f; neither had Cloud Logs environment variables or OAuth secret bindings, and no pilot Scheduler job existed. README-only host PR #16 merged at b5c6c8444fd3c98c177d441b47f691cbdfae1d5b. Candidate build/lint [39299058079](https://github.com/datatug/datatug-cloud/actions/runs/39299058079), post-merge Go CI [39299663820](https://github.com/datatug/datatug-cloud/actions/runs/39299663820), and deployment [39299949750](https://github.com/datatug/datatug-cloud/actions/runs/39299949750) passed. Provider readback at 18:11:59 UTC found production datatug-cloud-00014-lhg and preview datatug-cloud-preview-00015-6w6 at 100% traffic on the PR #16 image; both had no Cloud Logs environment variables or OAuth secret bindings, and no pilot Scheduler job existed. GET /health-check returned 200 with X-Sneat-Service: datatug-cloud at 18:12:01 UTC. The user-routes switch omits all eight handlers while retaining cleanup registration and credentials when enabled; it was not exercised with the master feature enabled. No grant, live cleanup or shutdown proof exists. |
| Production DataTug UI | [Apps PR #407](https://github.com/datatug/datatug-apps/pull/407) merged at `a63cfe2883d1078f9a3c1058483197126ea372de`; post-merge [CI run 39292521711](https://github.com/datatug/datatug-apps/actions/runs/39292521711) passed preflight, build, test, Cloud Logs E2E and deploy-gate checks. Cloudflare workflow [39293867514](https://github.com/datatug/datatug-apps/actions/runs/39293867514) succeeded; public build-info reports the same SHA and version `0.1.0+1201`. The production UI flag is on behind the fail-closed server-confirmed UID gate; Business Preview is off. At this earlier PR #407 checkpoint, no post-deploy CI smoke was run and the backend configuration was absent, so access remained denied. |
| Activation backend | [Backend PR #67](https://github.com/datatug/backend/pull/67) merged at `d3112f646accffedcc7279995ea7362c390f8e8c`. Reviewed candidate `7a52784dbdf7e923941fc66f202ad8092e15be65` passed [Backend CI 39308503102](https://github.com/datatug/backend/actions/runs/39308503102) and [Security 39308502042](https://github.com/datatug/backend/actions/runs/39308502042). The local full Firestore adapter suite passed with `-race`, 100% statement coverage and zero uncovered statements in 14.416s. Published `v0.38.0` points to that merge commit. Post-merge [Backend CI 39309725492](https://github.com/datatug/backend/actions/runs/39309725492) and [Security 39309724286](https://github.com/datatug/backend/actions/runs/39309724286) passed; WB verified the exact target at 19:25:05 UTC. No live lifecycle invocation is claimed. |
| Activation host | [Host PR #17](https://github.com/datatug/datatug-cloud/pull/17) merged at `669728342d2b9c36d7b37e254c821ba19b4162bf`, pinning backend `v0.38.0`. Reviewed candidate `a67028d5f689d0ff0f73719d535cd638836780de` passed [Go CI 39313747372](https://github.com/datatug/datatug-cloud/actions/runs/39313747372), including build/test, lint and the actual Firestore-emulator HTTP journey with `-race` (8.446s). The local full host race suite had 100% statement coverage and zero uncovered statements. The private fixed-UID OIDC control supports status, pause, resume and bounded durable reconciliation; its synthetic tests use fake OAuth/KMS/OIDC and do not prove live authenticated task delivery or Google consent/read/revoke. Post-merge [Go CI 39314930149](https://github.com/datatug/datatug-cloud/actions/runs/39314930149) and [deployment 39316404362](https://github.com/datatug/datatug-cloud/actions/runs/39316404362) passed; WB verified all ten exact-target checks at 20:09:41 UTC. Provider readback at 20:09:47 UTC found production `datatug-cloud-00015-vdq` and preview `datatug-cloud-preview-00016-p9d` at 100% traffic, both configured with the merge SHA image tag. Their immutable image digests are respectively `dfc28e7b327c4950d8ec1d1955851975b08a0aa3a4c2a32659d905b18d773115` and `6af0f4fc286dce15a5fad73c42213750d73d50daf60ebd36f7e67bdab7adaaa9`. Both had no personal Cloud Logs environment variables or OAuth secret bindings, and no pilot Scheduler job existed. GET health checks at 20:10:10 UTC returned 200 with `X-Sneat-Service: datatug-cloud` for both services. The code is deployed with the master feature off; no live lifecycle invocation or hosted Google journey is claimed. |

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
client secret into private tool output. Independent security review then
required replacing it before activation, storing a new pinned Secret Manager
version and retiring the original Google credential after verification. The
owner created that replacement on 2026-10-20, as recorded below. At this checkpoint,
no Google user grant or runtime secret binding existed, and no Google
user-token revocation was performed. Current runtime configuration is recorded
above.

After automatic approval review required exact permission, the owner separately
approved and the following prerequisites were applied:

- `roles/cloudkms.cryptoKeyEncrypterDecrypter` for the existing runtime account
  `588648831063-compute@developer.gserviceaccount.com` on the named KMS key only.
- Version `1` of `datatug-cloud-logs-oauth-state-key`: a standard-base64 encoding
  of 32 random bytes, generated and transferred in memory, with read-back
  equality verified. Its sole replication location is `europe-west3`. The
  application uses this as an AES-GCM key for short-lived pending PKCE
  verifiers and nonces, bound to the state hash and UID. KMS separately
  encrypts Google refresh tokens; neither storage path stores log entries.

Existing project-level Secret Manager access remains unchanged. The runtime
identity is shared, so other workloads using it also have access to this new
key; that is an explicitly approved pilot limitation. At this 2026-10-19
checkpoint, the Scheduler job and hosted activation were unprovisioned. Generic release
wiring is merged in [CICD PR #44](https://github.com/sneat-co/cicd/pull/44)
at `9571a3c78a448598ccce184a2aa7625ab07d6a53`; its 133 fake-provider step
checks passed locally and independently. That is not provider activation.

### Credential replacement — 2026-10-20

The owner clicked **Add secret** on the dedicated client. Its downloaded JSON
was checked against the client ID and project, made private, and processed in
memory. The replacement differs from the original secret, is stored as enabled
Secret Manager version `2`, and matched a private read-back. The temporary JSON
was deleted. Secret Manager version `1` is now disabled; the state-key secret
remains version `1`. The non-secret GitHub repository selector
`DATATUG_PERSONAL_CLOUD_LOGS_CLIENT_SECRET_VERSION` is pinned to `2`. At the
time of this secret readback, the master feature variable was absent and no
runtime binding had been added; current runtime references are recorded above.

The owner has confirmed that the original credential was retired in Google's
OAuth client. Disabling its stored Secret Manager version was separate from
that Google-side retirement. No Google user-token revocation occurred because
no Cloud Logging user grant exists. Production routes are enabled, and the
allowlisted lifecycle was resumed from epoch `1` to epoch `2`; current runtime
and resume receipts are recorded above. Fresh basic sign-in reached the
connections page, while the separate Logging account chooser did not recognize
the selected provider account. No consent or view read has been completed.

## Remaining live-pilot checks

- Complete and verify separate Cloud Logging consent using the dedicated OAuth
  web client and a recognized account. Basic Google sign-in works, but the
  selected provider account was not recognized by Google during the Logging
  chooser flow. No consent or Google user grant has been completed.
- The restricted test identity has `roles/logging.viewAccessor` on this view
  only; verify a positive read of the view and a negative broader-project read.
  The earlier Editor account is not evidence for least-privilege access.
- The original Google OAuth client credential is retired, replacement Secret
  Manager version `2` is selected, and live runtime configuration references
  versions `2` and state-key version `1`. The existing task invoker already has
  Cloud Run `run.invoker`; no new invoker binding was added. The managed cleanup
  job is enabled, and scheduled OIDC target requests returned HTTP 200 without
  `X-Cron-Secret`; the responses do not identify affected records. Production
  routes are enabled and the allowlisted lifecycle is resumed at epoch `2`.
  The standard Firebase `auth_time` fix is deployed. Complete and verify the
  separate Logging consent, then verify a positive view read and negative
  broader-project read, the hosted AG Grid journey, account disconnect, and
  exclusion of older unguarded writers. No broader access is approved.
- Host PR #15 added the private route-stop switch under the master feature
  flag: setting DATATUG_PERSONAL_CLOUD_LOGS_USER_ROUTES_ENABLED=0 omits all
  eight user handlers while retaining cleanup registration, credentials and
  task OIDC. The PR #17 execution receipt and current PR #18 deployment targets
  are listed above.
  The latest production configuration is master feature `1` with user routes
  enabled; the private control returned authenticated status and unauthenticated
  denial, and a pause at expected epoch `0` persisted as paused at epoch `1`,
  subsequently resumed to epoch `2` as recorded above.
  This does not prove full shutdown. The switch does not revoke grants. The new activation epoch guards
  fence admission, callback persistence and completion activation in guarded
  writers. Older revisions using the unguarded backend ignore that epoch and
  can still activate a grant after an initial disconnect inventory; cleanup
  alone only handles expiring completions and queued revocations. Before
  turning the master feature flag off after activation, prove a
  no-further-activation barrier across all serving and old revisions and
  in-flight start/callback/finish requests, then take a final active-grant
  inventory. Any late active grant needs a separately verified revocation path,
  followed by a generation-fenced drain of queued revocations and purge of all
  completion records while cleanup and keys remain available. This shutdown
  sequence has no live proof. Turning the master flag to 0 removes cleanup
  registration and its credential bindings.
- Fresh Google basic sign-in reached the authenticated Cloud Logs connections
  page, which showed no accounts or views. The separate Logging connection
  reached the account chooser, but Google did not recognize the selected
  provider account. No consent, grant or log read is verified. An earlier
  same-origin `createAuthUri` probe returned HTTP 400
  `INVALID_CONTINUE_URI`; its callback-domain ownership issue remains unresolved.
  Public checks showed
  the shared helper returns HTTP 200, its `init.json` identifies
  `sneat-eur3-1` / `auth.sneat.co`, and both handler scripts match the canonical
  Firebase helper by SHA-256. These checks do not establish the browser-flow
  failure cause. The basic login success does not establish a Logging OAuth
  grant. No identity, Firebase project or auth-domain change has been made.
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
the `_Default` bucket's observed retention is 30 days. Current stage: the
view-only binding exists but positive and negative test-identity reads are
pending; the managed cleanup Scheduler job is enabled and scheduled target
requests returned HTTP 200, without a receipt of affected records. The
disposable probe was deleted and returned `NOT_FOUND`. The Cloud Run master
feature and user routes are `1`; the allowlisted lifecycle is active at epoch
`2`. No Google Cloud Logging user grant exists. Host PR #25 is merged and
deployed as source `9d055b12fae5ae74793e8f452bd7fc8714e22d33`.
The approved KMS key, key-level runtime permission, state-key version `1` and
OAuth client-secret version `2` exist as recorded above; the old stored client
secret version `1` is disabled. No minimum-instance configuration was introduced
by this pilot step.
