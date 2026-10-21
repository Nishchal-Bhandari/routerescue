# Four-minute demo

1. **0:00–0:30:** Show connected bookings, 19:00 venue deadline and ₹5,000 spending limit. State the data are synthetic.
2. **0:30–1:15:** Simulate flight cancellation. Show ₹3,200 recovery and ledger. Explain B's ₹800 excess, C's 45-minute delay and D's impossible transfer.
3. **1:15–2:00:** Simulate bus unavailable. Show that A is no longer selectable and the frontier requires an explicit choice.
4. **2:00–2:35:** Increase budget to ₹5,800. Show fresh validation and 17:00 arrival. A constraint change is not booking approval.
5. **2:35–3:15:** Review and confirm the simulated receipt. Show booking pending with provider, evidence and JSON/print export.
6. **3:15–3:40:** Show Activity and verification results. If configured, inspect the shown run ID in LangSmith; otherwise say model-free mode is active.
7. **3:40–4:00:** Explain the travel-desk pilot hypothesis and supported scope. Do not claim live booking, real fares or measured model latency.

## Exactly eight slides

| Slide | Required heading | Content |
|---|---|---|
| 1 | Team details | RouteRescue — Save the purpose of the trip; PS 4.1. Insert actual team/member/college/contact details. |
| 2 | Problem Statement | One cancelled flight can break multiple bookings and the purpose of the trip. |
| 3 | Solution Overview | Impact graph, recovery frontier and receipt; ₹3,200 / 18:15 synthetic example. |
| 4 | Technical Approach | React, FastAPI, Deep Agents, scoped MCP, deterministic checks, SQLite, OpenRouter, LangSmith. |
| 5 | Diagrams/Flow Charts/Visuals | Architecture from implementation.md and second-disruption decision flow. |
| 6 | Impacts and Benefits | Only measured figures from verification.md/evaluation-results.json, with test scope identified. |
| 7 | Business Impact & Scalability | Travel-desk subscription hypothesis; validate demand and one authorized provider pilot. |
| 8 | Additional links | Actual repository and ≤4-minute video links; label prototype simulation scope. |

Use the original template when supplied; preserve its headings and slide count. Name the final deck after the actual team. Team identities, repository URLs, public deployment and video links are not invented here.

## Source package

The ZIP contains source, lock files, environment example, tests, evaluation cases/results, launch scripts and documentation. It excludes credentials, databases, dependencies and caches. The README explains installation and local startup.
