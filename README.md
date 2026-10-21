# RouteRescue

**Save the purpose of the trip.** React + FastAPI + LangChain Deep Agents + MCP + OpenRouter + LangSmith + SQLite.

A cancelled flight threatens a traveller's pickup, hotel and workshop. RouteRescue checks connected bookings, evaluates alternatives, offers exact budget/time trade-offs, and produces an evidence-backed recovery receipt.

**All travel data are simulated.** Confirming a plan never buys or cancels a real booking. The supported fixture corridor is Mangaluru → Bengaluru on 15 November 2026. Model-free mode works without credentials.

## Setup and launch

Tested prerequisites: Python 3.13.2 and Node.js 22.19.0. From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
npm.cmd --prefix apps/web ci
npm.cmd --prefix apps/web run build
.\.venv\Scripts\python.exe scripts/manage.py seed
.\.venv\Scripts\python.exe scripts/manage.py run
```

Open **http://127.0.0.1:8000**. API documentation: **http://127.0.0.1:8000/docs**. Keep the terminal running. Do not overwrite an existing `.env` containing your configuration.

Each browser session gets a private sample trip. Choose **Simulate flight cancellation**, inspect the ₹3,200 option, then **Simulate bus unavailable** to see the ₹800 / 45-minute recovery frontier.

For frontend development, run the API plus `npm.cmd --prefix apps/web run dev` on port 5173. Normal use serves the built frontend and API together on port 8000.

On macOS/Linux, use `.venv/bin/python` and `npm`. The Python lock file restricts pywin32 to Windows. Optional Docker instructions: create `.env` and run `docker compose up --build`. The Docker recipe is supplied but was not validated on this host.

## Enable OpenRouter and LangSmith

Set these server-side values in `.env`, then restart the API:

```dotenv
AGENT_MODE=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=openrouter/free
ALLOW_PAID_MODELS=false
AGENT_TIMEOUT_SECONDS=25
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-key
LANGSMITH_PROJECT=routerescue
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Use your LangSmith account's regional endpoint and workspace ID when required. Secrets never belong in the frontend or source control.

The free router selects available free models with the requested capabilities; availability and rate limits vary. A specific tool-capable `:free` model also works. Paid models require `ALLOW_PAID_MODELS=true`; no automatic paid fallback occurs. Use an account-side credit limit if enabling a paid model. Research is bounded to **5 model calls, 12 tool calls, 900 output tokens per response, and a 25-second default deadline**.

Verify your actual credentials with:

```powershell
.\.venv\Scripts\python.exe scripts/manage.py smoke-agent
```

Recover a trip in the UI and expand **Recovery activity**. Search its run ID in your LangSmith project. Traces cover the recovery, agent/model/tool calls, inventory search and deterministic validation. Workspace settings show configuration, not proof that LangSmith received a trace.

Without credentials, model planning is explicitly unavailable and deterministic fixture recovery remains usable. The test suite uses a scripted model to exercise real Deep Agents and MCP. **Live OpenRouter calls and LangSmith delivery must still be verified with your keys.**

## Verification

```powershell
.\.venv\Scripts\python.exe scripts/manage.py test
.\.venv\Scripts\python.exe scripts/evaluate.py
# Keep the built app running on port 8000 for browser tests:
Set-Location apps/web
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

See [measured verification results](docs/verification.md). Backend tests use temporary SQLite databases; browser tests create private sessions in the local app. Screenshots are generated in `artifacts/`.

## Reset and package

Stop the API and run these commands from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/manage.py reset-demo
.\.venv\Scripts\python.exe scripts/manage.py run
```

Reset preserves prior databases in `data/backup-*`. Reload the browser for a fresh session. Use **New trip** instead to keep your previous trips.

```powershell
.\.venv\Scripts\python.exe scripts/manage.py package
```

Creates `artifacts/RouteRescue-submission.zip` without credentials, databases, dependencies or caches. Install dependencies and build after extraction.

## Structure

```text
apps/api/                 API routes, session ownership, approval
apps/web/                 React + TypeScript UI and browser tests
routerescue/domain/       Graph, constraints, ranking, frontier
routerescue/providers/    Explicit synthetic inventory and evidence
routerescue/agent/        Bounded Deep Agent and OpenRouter integration
routerescue/mcp/          Private read-only stdio MCP tools
routerescue/store.py      SQLite persistence and audit
routerescue/service.py    Recovery orchestration and receipts
fixtures/                Independent labelled evaluation cases
tests/                   Domain, API, isolation and MCP tests
scripts/                 Launch, seed, test, reset, evaluate, package
docs/                    Requirements, verification and submission content
```

Browser-session identity is local, not a production account system. Live inventory, buying tickets, notifications and automatic monitoring are out of scope. Interrupted runs are marked failed on server restart and can be retried. Persisted results survive refresh/restart.

Read [implementation/scope](docs/implementation.md), [demo/submission script](docs/demo-and-submission.md) and the [original blueprint](docs/source/RouteRescue_AI_Implementation_Blueprint.md).
