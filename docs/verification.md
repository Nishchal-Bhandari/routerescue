# Verification record

Updated on 22 October 2026 using Windows, Python 3.13.2 and Node.js 22.19.0. Travel inventory is synthetic; real OpenRouter execution and LangSmith delivery were verified separately.

| Check | Result |
|---|---|
| Python domain/API/MCP/persistence/auth/admin suite | 42 tests passed |
| TypeScript check and Vite production build | Passed |
| Desktop browser journey | Passed: cancellation → ₹3,200 plan → second disruption → frontier → ₹5,800 constraint change → receipt approval → JSON download → refresh persistence → audit |
| Mobile browser journey | Passed at 390px: create hotel scenario → recover → receipt → keyboard dismissal → navigation; no horizontal overflow |
| Login/admin browser journeys | Passed: sign-in errors, admin users and inventory editing, logout, mobile login and separate traveller trips |
| Browser total | 4 Chromium journeys passed; offline fixture mode in a separate temporary database |
| Real MCP process | Eight tools discovered over stdio; inventory queried; unauthorized owner receives no trip data |
| Actual Deep Agent harness | Scripted test model called real MCP tools and persisted SQLite checkpoints |
| Agent failure behavior | No-key and paid-model guards, malformed-output correction and explicit failure without canned results passed |
| Live OpenRouter/MCP/LangSmith | Successful free-router recovery: 4 model calls, 5 tool calls, 20,427 total tokens; option A validated; trace retrieved remotely |
| Deterministic evaluation | 30 distinct labelled cases, 3 repetitions each, 90/90 executions passed |

`evaluation-results.json` contains raw results and measured evaluator-only latency (p50 approximately 0.033 ms, p95 approximately 0.074 ms on this host). These figures exclude API, MCP, model and network latency; they must not be presented as end-to-end agent speed.

The acceptance tests include the exact hero truth table, second-disruption frontier, unknown/invalid fares, accessibility, cash boundaries, timezone equivalence, pending refunds, impossible/disconnected transfers, expired offers, graph cycles, train/hotel impacts, session ownership, CSRF rejection, duplicate events/runs, optimistic version conflicts, stale/expired/tampered previews, repeated confirmation, persisted SSE/audit records, interrupted-run recovery and superseded-worker protection.

## Not verified

- Every available model/provider: one actual `openrouter/free` run was verified; router selection, rate limits and latency can vary. Sanitized metrics are in `live-integration-results.json`.
- Docker image execution: recipe supplied, not tested on this host.
- Real provider inventory, transactions or travel policies: not implemented; fixture labels remain visible.
- Five-person usability study, real-world impact precision/recall, model latency/cost measurements or business demand: not measured and not claimed.
- Exact-template team presentation and final demo video: source template/team details are not present; content/script are supplied.

Passing tests establishes the tested behavior, not a guarantee of zero defects under all inputs or deployment environments.

## Reproduce

Follow README setup. Run `python scripts/manage.py test` and `python scripts/evaluate.py`. Build the frontend, start `scripts/browser_server.py`, set `APP_URL=http://127.0.0.1:8011`, then run `npm run test:e2e` in `apps/web`. Restart the isolated server before repeating inventory-mutating tests. Screenshots cover login, admin, recovery, frontier, receipt and mobile layouts. Run `python scripts/manage.py smoke-agent` separately to call real providers and verify remote trace delivery.
