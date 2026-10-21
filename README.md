# RouteRescue

**Save the purpose of the trip.** React + FastAPI + LangChain Deep Agents + MCP + OpenRouter + LangSmith + SQLite.

A cancelled flight threatens a traveller's pickup, hotel and workshop. RouteRescue checks connected bookings, evaluates alternatives, offers exact budget/time trade-offs, and produces an evidence-backed recovery receipt.

**Travel inventory is demo data; agent execution is real.** The supported corridor is Mangaluru → Bengaluru on 15 November 2026. OpenRouter is the default execution mode. Missing or failed model access is reported explicitly, without silently substituting canned results. Confirming a recovery never purchases or cancels a real booking.

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

Sign in at `/login`. The admin dashboard is `/admin`; travellers use `/app`. Five local accounts and eight assigned trips are seeded once. See [all demo credentials](docs/accounts.md).

- **Admin:** `admin@routerescue.local` / `Admin@12345`
- **Traveller:** `aarav@routerescue.local` / `Aarav@12345`

Travellers see only their own trips. Select a trip, choose **Report a disruption**, describe what happened and enter when you can leave. The agent reads the trip/report, searches current inventory and evaluates updated plans through MCP tools. Admin edits to fares, availability or capacity invalidate old recovery results.

For frontend development, run the API plus `npm.cmd --prefix apps/web run dev` on port 5173. Normal use serves the built frontend and API together on port 8000.

On macOS/Linux, use `.venv/bin/python` and `npm`. The Python lock file restricts pywin32 to Windows. Optional Docker instructions: create `.env` and run `docker compose up --build`. The Docker recipe is supplied but was not validated on this host.

## Enable OpenRouter and LangSmith

Set these server-side values in `.env`, then restart the API:

```dotenv
AGENT_MODE=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=openrouter/free
ALLOW_PAID_MODELS=false
AGENT_TIMEOUT_SECONDS=90
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-key
LANGSMITH_PROJECT=routerescue
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Use your LangSmith account's regional endpoint and workspace ID when required. Secrets never belong in the frontend or source control.

The free router selects available free models with required capabilities; availability and rate limits vary. A specific tool-capable `:free` model also works. Paid models require `ALLOW_PAID_MODELS=true`; no automatic paid fallback occurs. Use an account-side credit limit if enabling paid models. Research is bounded to **6 model calls, 12 tool calls, 1,200 output tokens per response and a 90-second default deadline**.

Verify your actual credentials with:

```powershell
.\.venv\Scripts\python.exe scripts/manage.py smoke-agent
```

Recover a trip and expand **Recovery activity**. Choose **Verify LangSmith trace** to check remote delivery and open the exact trace. Traces cover the recovery, model/tool calls, inventory search and validation. Admins can inspect runs, tool stages and token usage across accounts. Configuration status alone is not proof of trace delivery.

Live OpenRouter/MCP execution and LangSmith delivery have been verified: **4 model calls, 5 tool calls, a validated recovery and a remotely retrieved trace**. The smoke command uses a temporary database. Keys remain in ignored `.env`.

`AGENT_MODE=fixture` is retained only for explicit offline testing. The normal app uses `openrouter` and requires working credentials. SQLite inventory stays labelled as demo data even when the model and tracing connections are live.

## Verification

```powershell
.\.venv\Scripts\python.exe scripts/manage.py test
.\.venv\Scripts\python.exe scripts/evaluate.py
# In another terminal, start the isolated offline test server:
.\.venv\Scripts\python.exe scripts/browser_server.py
# In the test terminal:
Set-Location apps/web
$env:APP_URL='http://127.0.0.1:8011'
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

See [verification results](docs/verification.md). Backend and browser tests use temporary databases. Offline browser tests do not spend model credits; actual provider calls are verified separately. Restart the browser test server before each full suite because admin tests edit seeded inventory. Screenshots are generated in `artifacts/`.

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

Accounts use salted scrypt passwords and hashed, revocable server-side session tokens with role and ownership checks. Demo credentials are public; do not deploy them unchanged on a public server. Live airline inventory, ticket purchases, notifications and automatic monitoring remain out of scope. Interrupted runs are marked failed on restart and can be retried. Persisted results survive refresh/restart.

Read [implementation/scope](docs/implementation.md), [demo/submission script](docs/demo-and-submission.md) and the [original blueprint](docs/source/RouteRescue_AI_Implementation_Blueprint.md).
