# Local browser workspace

Step 5 implements UI-1 through UI-5 over the existing workspace semantics.
The UI is a local research tool, with no third-party runtime dependencies, hosted
service, chat interface, or separate belief policy.

## Start

From the repository root:

```bash
PYTHONPATH=src python3 -m holon.cli --db runtime/ui-check.sqlite3 serve
```

Open **http://127.0.0.1:8765**. This example selects a separate database for a
walkthrough. To use an existing workspace, supply its path with the global `--db`
option before `serve`. The resolved path is shown in the browser header and the
terminal. Server startup initializes or upgrades that selected database using the
existing storage migration rules; back up an older workspace before upgrading.
There is no browser API accepting arbitrary filesystem paths or switching stores.
Stop the server and restart with a different `--db` to select another workspace.

For an installed package, the equivalent command is:

```bash
holon --db runtime/ui-check.sqlite3 serve --port 8765 --model qwen3:14b
```

`--host` selects the Ollama URL (default `http://127.0.0.1:11434`), not the browser
server's binding. `--timeout` controls model request time in seconds. The browser
server always binds to `127.0.0.1`. Manual workflows work without Ollama; previews
require a running server and an installed model. The form can select a model
name, but cannot change the configured Ollama destination.

## Workflow

1. **New claim:** enter a claim and explicit scope. Browse or search claims by
   claim/scope text, and filter by current evidence status.
2. **New observation:** switch to Observations and record a source, report, and
   optional known observation time. Search by report/source and optionally filter
   by exact source. An observation alone is not evidence of a claim.
3. **Link to a claim:** open an observation, search/select a claim, and either
   save a manually assigned relationship or choose **Preview with model**.
   Alternatively, **Add report** on a claim records a report and link together.
4. **Review:** inspect the original report, scoped claim, source, model rationale,
   and proposed relationship. **Accept evidence** commits it; **Discard preview**
   returns to the form. Uncertain/unrelated proposals cannot be accepted.
5. **Inspect:** the claim view shows active support/contradiction, withdrawn links,
   observation provenance, original model rationale, replacement IDs, revision
   history, and the experimental Beta projection with its full metadata.
6. **Correct:** use **Correct report** to create a replacement report, **Reinterpret**
   to replace a relationship while retaining the observation, or **Withdraw** to
   remove a link from active evidence without deleting its history. Each requires
   attribution and a reason. Other links to the original observation are unaffected.

No UUID copying is necessary. Optional impact mass is a stipulated experimental
quantity. The projection is labeled as experimental, not truth confidence.
Incomplete legacy metadata remains visible as unavailable quantitative readout;
explicit legacy annotation is still available through the existing CLI.

## Implementation and consistency

- `workspace/operations.py` is shared by CLI and browser model workflows.
  Preview captures a consistent context (including projection metadata), releases
  the read transaction, and then calls the model. Acceptance checks that same
  context and applies the change under one write transaction. A changed context
  requires a fresh preview, including changes made through another interface.
- `Workspace.transaction()` lets application operations own an outer transaction;
  nested service operations do not independently commit it. Nested failures must
  propagate to the owner. Existing standalone service and CLI operations retain
  their own atomic commits/rollbacks.
- The application opens and closes a SQLite connection per operation, in the
  executing thread. No SQLite connection is shared between HTTP threads.
- Browser commands persist a request digest and result in an additive
  `browser_receipts` table, atomically with their effects. This adapter metadata
  does not independently change the core schema version, evidence semantics, or revision
  policies. Exact retries return the original result; changed content under the
  same request ID fails. Results are receipts of the original operation, not a
  new current-state read; the UI refreshes current state afterward.
- Acceptance receipts are keyed by preview token: repeating acceptance with a new
  request ID still cannot create another report/link. Completed acceptance can be
  retried after server restart. Pending previews live in server memory, expire
  after 30 minutes, and must be regenerated after a restart. At most 256 pending
  previews are retained; discarded/expired previews create no evidence.
- Before a browser command is sent, its payload/ID is retained in that tab's
  session storage, scoped to the selected database path. A lost response or 503
  retains the command for **Retry saved submission**, including after reload.
  A definitive rejection or successful response clears it. A different command
  is blocked while an outcome is unknown. Closing the tab may lose this pending
  browser state; durable server receipts remain. Successful identical submissions
  made deliberately with new request IDs are distinct events.
- Host/Origin checks, a per-server request token, JSON-only bounded POST bodies,
  no CORS permissions, a restrictive content security policy, and text-only DOM
  rendering protect the local browser boundary. This is not remote authentication
  or a deployment server. Local software/users with access to the machine remain
  trusted. Failed/declined interpretation attempts are not a persistent audit log.

## API surface

All routes use the workspace selected at server startup.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/workspace` | Selected path, model settings, local request token |
| GET | `/api/propositions` | `q`, `status`, `limit` (1–100), `offset` |
| GET | `/api/observations` | `q`, exact `source`, `limit`, `offset` |
| GET | `/api/propositions/{id}` | Evidence, history, current projection |
| GET | `/api/observations/{id}` | Observation and evidence links |
| POST | `/api/preview` | `{kind, arguments, model}`; kinds: report, observation, reinterpret |
| POST | `/api/discard` | `{token}` |
| POST | `/api/commands` | `{request_id, operation, arguments}` |

Commands: `propose`, `observe`, `report`, `link`, `correct`, `reinterpret`,
`withdraw`, `accept`. Strict schemas reject extra fields. All POST requests require
`Content-Type: application/json` and the `X-Holon-Token` from workspace metadata.
A stale preview/reused request ID returns 409; invalid input returns 400;
unavailable storage/model returns 503. The frontend uses refreshes for current
state rather than streaming updates.

## Verification checkpoint

Automated verification uses temporary stores and a deterministic mocked model:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q
node --check src/holon/web/static/app.js
node --check src/holon/web/static/structure.js
```

The 13 new tests in `tests/integration/test_browser_workspace.py` cover the full
application workflow, search/filter/pagination/reuse, CLI/browser semantic parity,
restart-safe receipts, concurrent duplicate submissions, rollback on receipt
failure, changes during model calls, stale review, discard/expiry/abstention,
invalid requests, and HTTP routes/assets/headers/error mapping. HTTP handlers are
exercised in memory without opening sockets. At the step 5 checkpoint the full Python suite had 93 tests; step 6 slice 1
added 11 domain tests, and slice 2 adds 14 persistence tests, bringing the current
total to 118 at slice 2; slice 3 adds 11 service/interface tests for 129 total. Slice 4 adds five
Node-backed adapter tests for 134 total (skipped if Node is unavailable).

**Live browser acceptance is partially verified by the user** (see the
2026-11-07 checkpoint below). The implementation session's sandbox
rejected socket creation with `PermissionError: [Errno 1] Operation not permitted`.
Consequently that implementation session did not establish actual browser or
live Ollama acceptance; subsequent user-reported results are recorded below.
JavaScript syntax and packaged static assets can be checked independently; they do
not establish browser layout or interaction correctness.

### Remaining manual acceptance

Run the startup command above outside the restricted execution sandbox, then:

1. Create a claim and an observation through the browser. Find each via search.
2. Link the observation to the claim with a reviewed model preview. Verify discard
   leaves evidence unchanged and acceptance adds one link. Verify an unavailable
   model reports an error without writing evidence.
3. Inspect the claim, observation, history, and projection. Reuse the observation
   for another claim using the searchable picker.
4. Reinterpret one link, correct its replacement report, then withdraw its active
   replacement. Confirm original records and reasons remain visible and the other
   claim's link is unchanged.
5. Leave a preview open; modify the same claim through the CLI or another tab;
   verify the stale acceptance is rejected and a fresh preview can be reviewed.
6. Check narrow/wide layouts, keyboard focus, dialog dismissal, and error messages.
   Verify a retained pending submission can be retried without another revision.
7. Restart the server and inspect the saved records. Compare with CLI inspection.

After this walkthrough passes, mark step 5/UI-3 through UI-5 complete in the plan
and roadmap. Step 6 derivation/lineage controls are now implemented; their acceptance
checklist is below. The next research implementation is step 7 repair. UI-6 and general chat remain later work.

### User walkthrough checkpoint — 2026-11-07

The user confirmed live claim creation, observation creation, Ollama preview and
acceptance, and a contradictory report changing status to contested. The dark
interface and model preview were also visible in the supplied screenshot. The
correction exercise was provided but its outcome has not been explicitly
confirmed; the remaining acceptance checklist stays open. At the user’s request,
step 6 domain work proceeds alongside these outstanding checks.

### API additions from step 6 slice 3

`GET /api/derivations` and `GET /api/lineage` return decoded whole-workspace
snapshots. The command endpoint additionally accepts `derive`, `assign-origin`,
`merge-origins`, and `reverse-lineage` with the same atomic receipt behavior.
Lineage conflicts return 409. These operations have CLI equivalents and GUI
controls as of slice 4. See the [derivation interface contract](derivation-lineage-contract.md).


### Slice 4 walkthrough — implementation checkpoint 2026-11-08

Restart `holon serve` and refresh the page to load the new static asset route.
Use a disposable workspace for these checks. Live acceptance is pending: the local
test server responds to HTTP, but the browser tool cannot connect to its loopback URL.

1. Create three scoped claims. Open the third and choose **Add justification**.
   Search for the first two, select their required stances, and enter rule, name and
   reason. Record it; verify both premises, signs and attribution in the detail view.
2. Add an alternative justification and follow the premise/conclusion navigation.
   Check duplicate premises and a circular dependency are rejected without a new
   record. Qualitative status and Beta projection must remain unchanged.
3. Create two observations. Assign each to a different origin group via its detail
   panel. Verify an empty group records **Unknown**, not independence; then reassign.
4. Open **Origin groups & history**. Merge the two groups, choosing one name to keep.
   Inspect every before/after membership, record the merge, then review and record
   its reversal. Verify both events remain visible and memberships are restored.
5. Open an assignment/merge review, make another origin change in a second tab, then
   submit the old review. Expect a conflict, disabled Save, and **Reload and review**.
   Verify reloading presents current memberships before allowing a new submission.
6. Check dependent reversal blocking, keyboard navigation, narrow layouts, and dialog
   dismissal. Restart the server and confirm derivations/groups/history persist.
   A transport-failed command must retry without duplicating its event.

These controls record supplied structure. Eligibility propagation and selective
repair are step 7; origin groups do not change existing evidence impact clusters.
