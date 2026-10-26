# AI Agent Workflow Automation

A practical reference implementation for **guarded AI-agent workflows** with FastAPI, Pydantic, a deterministic workflow engine, and an explicit human-approval gate.

This project demonstrates a core principle: agents should not receive unrestricted tool access. Work through a small allowlist, validate every payload, pause before consequential actions, and preserve an execution trace.

> **Current scope:** runnable demo with deterministic planning and mock tools. No external LLM, database, ticketing system, or production integration is configured.

## Features

- REST API to create, inspect, and list workflow runs.
- Allowlisted tool registry with strict Pydantic input schemas.
- Plan → execute safe step → request approval → resume workflow.
- Explicit approval state before consequential tools run.
- Per-step status, results, timestamps, and execution trace.
- Tests for state transitions, validation, API responses, and rejection paths.
- Docker and GitHub Actions CI configuration.

## Architecture

```text
Client
  |
  v
FastAPI routes ---- Pydantic request validation
  |
  v
Workflow engine ---- Run state + execution trace
  |
  +---- Deterministic demo planner
  |
  +---- Allowlisted tool registry
  |        +---- summarize_text (safe demo)
  |        +---- create_ticket (simulated; approval required)
  |
  +---- Approval gate ---- approve / reject ---- resume workflow
```

## Quick start

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive API documentation.

## Try a workflow

Create a run:

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"goal":"Summarize the incident and create a follow-up ticket","context":{"incident":"Checkout requests timed out for 8 minutes after a deployment."}}'
```

The workflow executes the safe summary step and pauses before simulated ticket creation. Copy `run_id` from the response and inspect the run:

```bash
curl http://127.0.0.1:8000/runs/<run_id>
```

Approve the pending ticket step:

```bash
curl -X POST http://127.0.0.1:8000/runs/<run_id>/decision \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","comment":"Reviewed for demo"}'
```

To reject it, send `"decision":"reject"`. The ticket tool is a **simulation**; it does not contact an external system.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/runs` | Create and start a workflow |
| `GET` | `/runs` | List recent runs |
| `GET` | `/runs/{run_id}` | Get run state and trace |
| `POST` | `/runs/{run_id}/decision` | Approve or reject a pending step |

## Run tests

```bash
python -m pytest
# Optional coverage report
python -m pytest --cov=app --cov-report=term-missing
```

## Docker

```bash
docker build -t ai-agent-workflow-automation .
docker run --rm -p 8000:8000 ai-agent-workflow-automation
```

Or use Docker Compose:

```bash
docker compose up --build
```

## Safety boundaries and limitations

- The planner is deterministic and intentionally small; it is not an LLM planner.
- The included tools are demos. No external side effects are performed.
- Run state is in memory; restarting the process clears runs and this is not multi-worker safe.
- The approval endpoint is an educational example, not an authenticated approval system. Add user identity, authorization, audit retention, and policy controls before production use.
- Add durable storage, queueing, rate limits, timeouts, metrics, secret management, and integration-specific retry handling before production deployment.
- Tools must stay allowlisted and schema-validated. Do not expose arbitrary Python evaluation, unrestricted shell access, or arbitrary URL fetches to an agent.

## Project structure

```text
app/
  api/routes.py
  core/config.py
  models/schemas.py
  services/planner.py
  services/tool_registry.py
  services/workflow_engine.py
  main.py
tests/
  test_api.py
  test_workflow_engine.py
.github/workflows/ci.yml
```

## Roadmap

- [ ] Persist runs in PostgreSQL.
- [ ] Add authenticated, role-based approval decisions.
- [ ] Add provider-neutral LLM planning with strict structured outputs.
- [ ] Add retries, deadlines, and tool-level timeouts.
- [ ] Add OpenTelemetry traces and metrics.
- [ ] Add a UI for run inspection and pending approvals.
- [ ] Add a real integration behind a disabled-by-default adapter and contract tests.

## License

MIT. See [LICENSE](LICENSE).
