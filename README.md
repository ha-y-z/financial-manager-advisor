# Financial Manager

Local web app for Trade Republic exports: categorized cash flow (CSV) and Portfolio composition (Portfolio Statement PDF).
Runs on your machine only; all data lives in `backend/data/financial.db` (back up that one file). Spec: `docs/spec-v1.md`.

## Run

```sh
cd backend && uv run uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```

First steps: in **Setup**, add the IBAN of the account your salary arrives on and tick *Income Source*. Then drop a CSV or PDF anywhere in the window.

## Test

```sh
cd backend && uv run pytest
cd frontend && npm run build   # type check
```

Real exports (`*.csv`, `*.pdf`) are git-ignored; tests use synthetic fixtures.
