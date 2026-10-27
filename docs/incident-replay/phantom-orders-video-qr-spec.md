# Phantom Orders video timestamps and QR payloads

Companion content specification for the approved Phantom Orders feature. The
feature specification remains canonical; this document adds only the six video
ranges and the exact description/QR payloads. It does not redefine the cases,
evidence, challenges or answers.

## Status and scope

- **Specification only.** This lane produces no video bytes, QR artwork, provider
  session or published site entry. No provider is needed to author or review
  this text.
- **Synthetic scenario.** INC-0042 and every person and record are fictional.
  All story timestamps are UTC on 2026-01-12. Amounts are integer cents, never
  dollars or floating-point currency.
- **Revision-pinned aliases.** Each destination uses the `/v/1/` alias form and
  contains no branch name. The parent release's immutable registry resolves the
  alias to the actual published commit. Nothing here asserts that a revision is
  already published.
- **No passive credit.** Watching, pausing, seeking or scanning a QR awards no
  success. Only an accepted challenge submission awards credit. The Watch
  recommendation remains disabled and unscheduled; scanning a link never
  activates it.
- **Honest uncertainty.** A second-success timestamp is the first *observed*
  duplicate. It narrows the investigation; it does not prove when the defect
  was introduced.
- **Config-dependent cause.** Only the complete package's reviewed configuration
  diff supports the causal claim. The absent-configuration variant must answer
  with insufficient evidence and an unknown deployment rather than a cause.

## Playback and checkpoint rules

1. One continuous 7:30 editorial timeline is divided into the six ranges below;
   the ranges are contiguous and cover 00:00–07:30 with no gaps.
2. At each chapter checkpoint the video **explicitly asks viewers to pause it
   themselves**. The player must not auto-advance on elapsed time, and seeking
   or finishing the video must not complete or credit a learner step.
3. While paused, the learner opens the pinned challenge in the real challenge
   editor. The dialogue's prompt action opens the challenge while the guide
   stays on the dialogue and waits at its validation checkpoint.
4. After a validated whole-challenge pass, playback resumes the discussion and
   debrief, then offers an explicit **Next** action that changes chapter.
5. The QR opens the same case description as the link, with no test or run
   parameters. Reviewing the description is not a substitute for solving.

## Six approved ranges and payloads

| # | Chapter | Video range | Description link | QR payload |
|---:|---|---|---|---|
| 1 | duplicate-payments | 00:00–01:00 | https://datatug.app/stories/phantom-orders/v/1/cases/duplicate-payments | https://datatug.app/stories/phantom-orders/v/1/cases/duplicate-payments |
| 2 | payment-impact | 01:00–02:10 | https://datatug.app/stories/phantom-orders/v/1/cases/payment-impact | https://datatug.app/stories/phantom-orders/v/1/cases/payment-impact |
| 3 | failure-window | 02:10–03:20 | https://datatug.app/stories/phantom-orders/v/1/cases/failure-window | https://datatug.app/stories/phantom-orders/v/1/cases/failure-window |
| 4 | retry-evidence | 03:20–04:40 | https://datatug.app/stories/phantom-orders/v/1/cases/retry-evidence | https://datatug.app/stories/phantom-orders/v/1/cases/retry-evidence |
| 5 | root-cause | 04:40–06:00 | https://datatug.app/stories/phantom-orders/v/1/cases/root-cause | https://datatug.app/stories/phantom-orders/v/1/cases/root-cause |
| 6 | prevention | 06:00–07:30 | https://datatug.app/stories/phantom-orders/v/1/cases/prevention | https://datatug.app/stories/phantom-orders/v/1/cases/prevention |

The description link and the QR payload must stay byte-identical for each
chapter. These URLs describe the case; they do not include answer values.

## Chapter script notes

These notes describe editorial beats, not reference answers. They deliberately
omit result rows, request IDs, amounts, deployment versions and configuration
contents so that reading the companion cannot replace solving the challenge.

### 1. duplicate-payments — 00:00–01:00

- **Setup:** Sarah reports that customers contacted support about repeated
  charges and warns the reports may overlap. Maya frames the first step as
  counting successful payments per order. Daniel cautions that a retry is not
  automatically a duplicate. Incidentius announces the opened fictional case.
- **Checkpoint:** the video asks viewers to pause themselves. The learner solves
  the pinned challenge and waits at the validation checkpoint; the guide stays
  on the dialogue while the prompt opens the real challenge.
- **Debrief:** after a validated pass, the team reviews which orders have more
  than one successful charge and restates that failed attempts are not charges.
  The debrief ends with the explicit Next action.

### 2. payment-impact — 01:00–02:10

- **Setup:** Sarah needs affected customers and excess charges rather than
  payment identifiers. Maya asks for one result row per affected order. Daniel
  identifies the refunded event as a distractor for this measurement.
- **Checkpoint:** pause invitation; the learner runs the real join challenge and
  waits for validation.
- **Debrief:** the team reviews the per-order excess in cents and the total, then
  moves on by explicit Next.

### 3. failure-window — 02:10–03:20

- **Setup:** Maya asks when the data first demonstrated a second successful
  charge. Daniel says to use the second success because a first charge can be
  valid. Sarah asks to distinguish the earliest observation from the exact
  moment the defect was introduced.
- **Checkpoint:** pause invitation; the learner submits the timestamp and
  interpretation in the real challenge editor.
- **Debrief:** the team agrees the observed duplicate narrows the search but
  does not by itself prove that a deployment caused the defect. Explicit Next
  follows.

### 4. retry-evidence — 03:20–04:40

- **Setup:** Daniel describes a provider acceptance followed by a handler
  timeout and a retry of the same request. Maya asks for the second affected
  request and a harmless retry to compare. Sarah asks to keep request IDs with
  the evidence so the conclusion is reproducible.
- **Checkpoint:** pause invitation; the learner correlates the SQL and log
  evidence and selects the declared attachments in the real challenge.
- **Debrief:** the team confirms duplicate successes on the retried requests and
  identifies the recovered failure as harmless. Explicit Next follows.

### 5. root-cause — 04:40–06:00

- **Setup, complete package:** Daniel presents the reviewed configuration diff
  and names the omitted retry safeguard. **Setup, absent-config variant:** Daniel
  says no reviewed configuration diff exists yet, so the cause remains
  unconfirmed. In both variants Maya asks whether the explanation accounts for
  every affected request and what would refute it; Sarah asks whether the team
  has enough evidence to explain the incident without guessing.
- **Checkpoint:** pause invitation; the learner submits the cohort and the
  evidence-backed structured answer. A selected cause is accepted only when the
  package actually supplies the configuration evidence.
- **Debrief, complete package:** the diff and both repeated-request traces
  support the missing safeguard, leading into prevention. **Debrief,
  absent-config variant:** the team records insufficient evidence and an unknown
  deployment instead of asserting a cause. Explicit Next follows.

### 6. prevention — 06:00–07:30

- **Setup:** Maya asks the learner to turn the duplicate-charge query into a
  Check and to prove that it fails broken data, passes repaired data and still
  catches a different affected order. Daniel says a Watch could later run that
  Check, but training must not activate a production monitor. Sarah asks the
  postmortem to cite the evidence and state the verification performed.
- **Checkpoint:** pause invitation; the learner submits the Check definition and
  the structured postmortem citations in the real editor.
- **Debrief:** the team confirms the Check distinguishes broken from repaired
  data, labels the matrix as synthetic validation, and leaves the Watch as a
  disabled proposal for a separately authorized owner. The chapter ends with the
  existing finish, replay and skipped-case options. No QR scan or playback
  awards credit.

## Release checks (parent-owned)

- Resolve all six `/v/1/` aliases against one immutable registry revision and
  confirm link and QR payload equality.
- Confirm the six ranges remain contiguous across 00:00–07:30.
- Confirm no URL carries a branch, query string or test/run parameter.
- Confirm no video or QR bytes are added to the native package closure and no
  Watch is activated.
- Treat a changed case ID, evidence set or answer as a new revision rather than
  reusing these aliases.
