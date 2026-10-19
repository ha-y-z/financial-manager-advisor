# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Local, single-user web app that turns Trade Republic exports (Transaction CSV, Portfolio Statement PDF) into categorized cash-flow and Portfolio charts. `docs/spec-v1.md` is the source of truth for behavior; `docs/adr/` records the decisions behind it; `GLOSSARY.md` defines the domain vocabulary (Transaction, Counterparty, Alias, Flow Type, Override, Excluded, Income Source, Holding, Snapshot, Tag …). Use those terms exactly in code, UI copy and docs.

## Commands

```sh
# backend (FastAPI, Python ≥3.12, managed by uv)
cd backend && uv run uvicorn app.main:app --port 8000 --reload
cd backend && uv run pytest                                  # all tests
cd backend && uv run pytest tests/test_api.py::test_type_mapping_table   # one test

# frontend (Vue 3 + TS + Vite; dev server proxies /api -> :8000)
cd frontend && npm run dev          # http://localhost:5173
cd frontend && npm run build        # vue-tsc type check + build (the only frontend check; no unit tests)
```

`FM_DB` overrides the SQLite path (default `backend/data/financial.db`). Schema is created with `create_all` on startup; there is no Alembic yet, so schema changes require deleting the dev DB.

## Privacy constraints

- `example.csv` and `example_portfolio.pdf` contain real personal financial data. Never commit them, use them as test fixtures, or print their contents; `.gitignore` excludes `*.csv`, `*.pdf`, `backend/data/`. Tests build synthetic CSV rows and a synthetic PDF (`statement_pdf()` with fpdf2) in `tests/test_api.py`.
- ADR 0003: the Portfolio Statement PDF is parsed from an in-memory `BytesIO` (`app/portfolio.py`) and never written to disk or logged. Only the statement date and Holdings are stored.
- The app must stay fully local: no external network calls (the font is self-hosted via `@fontsource-variable`, not Google Fonts).

## Backend architecture (`backend/app/`)

- **Flow Type is not a column** (ADR 0001). The Category tree has four undeletable, unrenamable roots (Income, Expense, Investment Flow, Internal Transfer); a Transaction's Flow Type is the root of its Category. `classify.Tree` loads the whole tree once and answers `flow()`, `root_of()`, `subtree()`, `path()`, `uncategorized()`. "Uncategorized" means category is `NULL` (unknown Trade Republic type) or sits directly on the Income/Expense/Investment Flow root.
- **Categorization pipeline** (`classify.py`): `base_category()` resolves the Trade Republic `type` + IBAN context (TRANSFER_* rules are hard-coded against `OwnAccount`, ADR 0002; all other types come from the editable `TypeMapping` table). Then `Categorizer`: a type-specific non-root mapping (Fees, Buy, Dividends…) wins; otherwise Counterparty Default Category → MCC table (`seed.MCC`, name paths that fall back to the parent) → root. Candidates must lie under the resolved root.
- **`recategorize(db)` recomputes `category_id` for every imported Transaction** and is called after anything that changes rules: import, Default Category, type mapping, Own Account, merge/split, Category delete. Keep that invariant when adding new rule-changing endpoints.
- **Bank values vs. Overrides**: `Transaction` keeps the bank's values (`date`, `amount`, `counterparty_id`, `category_id`) and separate `o_*` Override columns; `eff_*` properties merge them. Import upserts by `tx_id` and only ever touches bank fields, never `o_*` or `excluded`. Manual Transactions have `tx_id = NULL`, are edited in place and are not touched by `recategorize`.
- **Counterparties**: `counterparty_for(db, raw)` maps a raw Alias (`name`, else `description` when `name` has no real text; never the unreliable `counterparty_name`, see `importer.alias_text`) to a Counterparty, creating one via `normalize()` on first sight. Merge/split move Aliases and Transactions.
- **Recurring Entries** (`recurring.py`): `materialize()` generates missing occurrences up to today as Manual Transactions with `recurring_id`; editing changes only the rule, so already-generated rows keep their values. Deleting a generated occurrence excludes it (otherwise it would be regenerated).
- **Analytics** (`analytics.py`) works on effective, non-Excluded rows in the period; Internal Transfers are left out, Refunds net into their Expense Category. Sankey nodes and links carry `info` (sum, count, top 3 Counterparties) for hover and a `filter` object the frontend passes back to `GET /api/transactions` for click-to-filter. The Sankey must balance (inflow to Budget = outflow), adding From Investments / Saved / From Reserves nodes as needed.
- Routes live in `app/routes/` (transactions + analytics, setup = categories/counterparties/accounts/mappings/recurring, portfolio). Tests go through the HTTP API only (FastAPI `TestClient` with a temp DB via `dependency_overrides`); assert on what the user would see, not on internal tables.

## Frontend architecture (`frontend/src/`)

- No router: `App.vue` switches tabs (Cash flow, Review, Portfolio, Setup), mirrored in `location.hash`.
- `state.ts` holds shared state: the global period (`period`, `setPeriod`, `shiftPeriod`), the Category list, formatting helpers, and `version`/`bump()`. Every mutation calls `bump()`, and views `watch(version)` to refetch. That is the whole cache-invalidation story.
- `api.ts` holds the fetch wrapper and all response types. Call `api.*` from script functions, not inline in templates (vue-tsc mis-types imported objects in templates).
- `theme.ts`: chart colors are read from CSS custom properties in `style.css` (light + dark sets, banknote-inspired Flow Type hues plus an 8-slot categorical palette validated for colour-vision deficiency). `categoryColor()` fixes a Category's hue by its first-level ancestor's position, so colors follow the entity, not its rank. `infoTooltip()` renders the shared hover summary.
- `TransactionTable.vue` is reused for the cash-flow list, the Review list (`mode="review"`) and the Excluded list (`mode="excluded"`). Parents pass a reactive `filters` object that chart clicks mutate.
