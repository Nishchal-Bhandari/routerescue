# Verification record

Verified on 21 October 2026 using Windows, Python 3.13.2 and Node.js 22.19.0. This report describes the synthetic prototype, not production travel reliability.

| Check | Result |
|---|---|
| Python domain/API/MCP/persistence suite | 37 tests passed |
| TypeScript check and Vite production build | Passed |
| Desktop browser journey | Passed: cancellation → ₹3,200 plan → second disruption → frontier → ₹5,800 constraint change → receipt approval → JSON download → refresh persistence → audit |
| Mobile browser journey | Passed at 390px: create hotel scenario → recover → receipt → keyboard dismissal → navigation; no horizontal overflow |
| Real MCP process | Seven tools discovered over stdio; fixture tool invoked; unauthorized owner receives no trip data |
| Actual Deep Agent harness | Scripted test model called real MCP tools and persisted SQLite checkpoints |
| Agent failure behavior | No-key and paid-model guards, malformed-output correction and provider-failure fallback passed |
| Deterministic evaluation | 30 distinct labelled cases, 3 repetitions each, 90/90 executions passed |

`evaluation-results.json` contains raw results and measured evaluator-only latency (p50 approximately 0.033 ms, p95 approximately 0.074 ms on this host). These figures exclude API, MCP, model and network latency; they must not be presented as end-to-end agent speed.

The acceptance tests include the exact hero truth table, second-disruption frontier, unknown/invalid fares, accessibility, cash boundaries, timezone equivalence, pending refunds, impossible/disconnected transfers, expired offers, graph cycles, train/hotel impacts, session ownership, CSRF rejection, duplicate events/runs, optimistic version conflicts, stale/expired/tampered previews, repeated confirmation, persisted SSE/audit records, interrupted-run recovery and superseded-worker protection.

## Not verified

- Live OpenRouter responses: no credentials were available. The integration path is implemented, but model quality, free-tier availability and runtime behavior need the provided smoke test with your key.
- LangSmith remote delivery: tracing is implemented and correlated by run ID, but account/project ingestion was not verified without a key.
- Docker image execution: recipe supplied, not tested on this host.
- Real provider inventory, transactions or travel policies: not implemented; fixture labels remain visible.
- Five-person usability study, real-world impact precision/recall, model latency/cost measurements or business demand: not measured and not claimed.
- Exact-template team presentation and final demo video: source template/team details are not present; content/script are supplied.

Passing tests establishes the tested behavior, not a guarantee of zero defects under all inputs or deployment environments.

## Reproduce

Follow README setup. Run `python scripts/manage.py test`, `python scripts/evaluate.py`, build the frontend, start the API and run `npm run test:e2e` from `apps/web`. Browser test artifacts include desktop recovery/frontier/receipt and mobile recovery screenshots.
