# Financial Manager — v1 Spec

Agreed on 2026-10-19. Vocabulary follows `GLOSSARY.md`; decisions in `docs/adr/` apply.

## Problem Statement

My money lives mainly in a Trade Republic account, with income arriving via another bank. Trade Republic gives me a CSV export of Transactions and a PDF Portfolio Statement, but neither tells me where my money actually goes, how much I save each month, or how my Portfolio is composed. Categorizing hundreds of card payments by hand every month is tedious, and generic tools either want my bank credentials, upload my data to the cloud, or count buying an ETF as "spending".

## Solution

A personal web app that runs locally on my machine. I drop in my Trade Republic CSV and Portfolio Statement PDF; the app assigns every Transaction a Flow Type and Category, remembers my corrections per Counterparty so I only categorize each merchant once, and shows intuitive charts of income, spending, savings and Portfolio composition. Nothing leaves my machine, and the PDF itself is never stored.

## User Stories

### Importing Transactions

1. As the user, I want to drag and drop a Trade Republic CSV onto the app, so that importing takes one gesture.
2. As the user, I want a file picker as an alternative to drag and drop, so that I can import without a file manager window open.
3. As the user, I want an import summary (new, already known, Uncategorized, Excluded), so that I can see what the import did.
4. As the user, I want to re-import overlapping date ranges without creating duplicates, so that I don't have to track which exports I already loaded.
5. As the user, I want re-imports never to overwrite my Overrides, so that my corrections are permanent.
6. As the user, I want re-imports never to bring back Excluded Transactions, so that removed items stay removed.
7. As the user, I want foreign-currency card payments to be counted in EUR, so that all totals are in one currency.
8. As the user, I want an import to fail with a clear message if the file is not a Trade Republic CSV, so that I don't load garbage.

### Flow Types

9. As the user, I want card payments counted as Expense, so that my spending is captured automatically.
10. As the user, I want positive amounts on Expense Categories treated as Refunds, so that a returned purchase reduces my spending instead of inflating my income.
11. As the user, I want buys, sells and Saveback counted as Investment Flow, so that investing never looks like spending.
12. As the user, I want dividends and interest counted as Income, so that investment income shows up.
13. As the user, I want to register my Own Accounts by IBAN, so that transfers between my accounts are recognized as Internal Transfers.
14. As the user, I want to flag an Own Account as an Income Source, so that money arriving from my salary account counts as Income.
15. As the user, I want transfers out to an Income Source to remain Internal Transfers, so that moving money back doesn't count as spending.
16. As the user, I want inbound direct debits without an IBAN counted as Internal Transfers, so that top-ups from my other account are not misread as income.
17. As the user, I want Transactions with an unknown Trade Republic type to land in the review list instead of breaking the import, so that new export formats don't block me.
18. As the user, I want to map an unknown type to a Flow Type (and optionally a Category) once, so that all past and future Transactions of that type follow it.

### Categorization

19. As the user, I want every Transaction to receive a Category automatically where possible, so that I only review the exceptions.
20. As the user, I want the app to use the Counterparty's Default Category first, so that my own decisions take precedence.
21. As the user, I want the app to fall back to the merchant category code, so that unknown merchants are still categorized sensibly.
22. As the user, I want Transactions that can't be categorized marked Uncategorized and listed for review, so that nothing is silently misfiled.
23. As the user, I want confirming or changing a Transaction's Category to set the Counterparty's Default Category, so that I categorize each merchant only once.
24. As the user, I want to override the Category on a single Transaction without changing the Default Category, so that an occasional Amazon electronics purchase doesn't reclassify all my Amazon orders.
25. As the user, I want changing a Default Category to update all past Transactions of that Counterparty except those I overrode, so that history stays consistent.

### Counterparties

26. As the user, I want raw merchant names normalized automatically (e.g. branch numbers stripped), so that "DM-FIL. A1EN" and "DM-FIL. B2XY" become one Counterparty.
27. As the user, I want to merge two Counterparties, so that I can fix what normalization missed.
28. As the user, I want to choose which Default Category survives a merge, so that merging never silently loses a decision.
29. As the user, I want to split an Alias off into its own Counterparty, so that I can fix wrong automatic merges.
30. As the user, I want to see all Aliases of a Counterparty, so that I understand what is grouped together.

### Categories

31. As the user, I want a starter set of about 15 Categories, so that the app is useful immediately.
32. As the user, I want to add, rename and delete Categories up to two levels under each Flow Type, so that the structure fits my life.
33. As the user, I want the four Flow Type roots to be undeletable, so that I cannot break the income and spending totals.
34. As the user, I want to assign a Transaction to a parent Category as well as a child, so that I don't have to over-specify.
35. As the user, I want Transactions and Default Categories of a deleted Category moved to its parent (or Uncategorized for first-level Categories), with a confirmation showing how many are affected, so that deletion never loses data.

### Editing Transactions

36. As the user, I want to add Manual Transactions, so that spending outside the main account (e.g. paid from my other bank) is included.
37. As the user, I want to create Recurring Entries (e.g. 36 € insurance monthly on the 1st), so that regular outside payments are captured without manual work.
38. As the user, I want changes to a Recurring Entry to affect only future occurrences, so that history doesn't shift.
39. As the user, I want to end a Recurring Entry, so that cancelled contracts stop appearing.
40. As the user, I want to edit and delete Manual Transactions freely, so that I can fix mistakes.
41. As the user, I want to change amount, date, Counterparty or Category of an imported Transaction as an Override, so that I can correct the bank's data.
42. As the user, I want to reset an Override to the bank's original values, so that I can undo corrections.
43. As the user, I want to Exclude an imported Transaction, so that it disappears from all charts.
44. As the user, I want a list of Excluded Transactions from which I can restore them, so that exclusion is reversible.
45. As the user, I want Manual Transactions and Overrides visibly marked, so that I can tell my data from the bank's.

### Cash-flow views

46. As the user, I want to pick the time period (month, quarter, year, custom) once at the top, so that all views stay in sync.
47. As the user, I want a monthly bar chart of Income vs. Expense with my savings rate, so that I see whether I'm saving.
48. As the user, I want a sunburst of Categories for the period, so that I see where my money goes at both levels.
49. As the user, I want a Sankey diagram from Income Categories through a Budget node to Expense Categories, Investments and Saved, so that I see the whole flow of money at a glance.
50. As the user, I want a "From Reserves" node when I spent more than I earned, so that deficits are visible rather than hidden.
51. As the user, I want Internal Transfers left out of the Sankey and totals, so that shuffling money doesn't distort the picture.
52. As the user, I want hovering over a chart node or link to show its sum, number of Transactions and top 3 Counterparties, so that I get detail without leaving the chart.
53. As the user, I want clicking a chart node or link to filter the Transaction list beneath it, so that I can see the exact Transactions behind a number.
54. As the user, I want to clear that filter with one click, so that I can get back to the full view.
55. As the user, I want a ranking of top Counterparties by spending, so that I see which merchants cost me most.
56. As the user, I want a filterable Transaction list (period, Flow Type, Category, Counterparty, text), so that I can find anything.
57. As the user, I want Refunds netted into their Expense Category in all charts, so that totals reflect what I really spent.

### Portfolio

58. As the user, I want to drag and drop (or pick) a Trade Republic Portfolio Statement PDF, so that importing my Portfolio is one gesture.
59. As the user, I want the import to extract only the Holdings and the statement date, so that personal data in the PDF is never stored.
60. As the user, I want the PDF itself discarded after import, so that nothing sensitive stays on disk.
61. As the user, I want the import rejected with both numbers shown if the parsed Holdings don't match the statement's own count and total, so that a layout change fails loudly instead of silently producing wrong data.
62. As the user, I want each import stored as a dated Portfolio Snapshot, so that I can track my Portfolio over time.
63. As the user, I want re-importing a statement with the same date to replace that Snapshot, so that I don't get duplicates.
64. As the user, I want a pie chart of the Portfolio by Holding, so that I see its composition.
65. As the user, I want to add any number of Tags to a Holding, so that I can group Holdings my own way (e.g. "ETF", "Stock", "Tech").
66. As the user, I want Tags to stick to a Holding's ISIN across Snapshots, so that I tag each security only once.
67. As the user, I want a pie chart of the Portfolio by Tag, so that I see e.g. ETF vs. single-stock allocation.
68. As the user, I want to choose which Snapshot I'm looking at, with the latest shown by default, so that I can review the past.
69. As the user, I want a line chart of total Portfolio value across Snapshots, so that I see how my wealth develops.
70. As the user, I want the pie charts to behave like the cash-flow charts (hover summary, click to filter Holdings), so that the app feels consistent.

### Privacy and operation

71. As the user, I want the app to run entirely locally without login, so that my financial data never leaves my machine.
72. As the user, I want all data in a single local database file, so that backing up means copying one file.

## Implementation Decisions

### Architecture

- Monorepo with a FastAPI backend and a Vue 3 + TypeScript + Vite frontend. Single user, localhost only, no authentication.
- Persistence: SQLite via SQLAlchemy; schema changes via Alembic migrations.
- Charts: ECharts (via vue-echarts), which covers bar, line, pie, sunburst and Sankey with hover and click events.
- LangChain, HuggingFace and PyTorch are not dependencies in v1. Categorization is designed so a model-based suggester can later be added as an extra step before "Uncategorized".

### Modules

- **Transaction import**: parses the Trade Republic CSV (comma-separated, quoted, dot decimals, ISO dates), upserts by the bank's transaction ID, and returns an import summary. Ignores Trade Republic's own `category` column. Uses the `date` column (booking date) for all time periods. The `amount` column is already in EUR.
- **Flow Type resolution**: maps the Trade Republic `type` plus IBAN context to a Flow Type:

  | Trade Republic `type` | Flow Type |
  |---|---|
  | CARD_TRANSACTION, CARD_TRANSACTION_INTERNATIONAL | Expense (positive amount = Refund) |
  | CARD_ORDERING_FEE | Expense → Fees |
  | BUY, SELL, BENEFITS_SAVEBACK | Investment Flow |
  | DIVIDEND, INTEREST_PAYMENT | Income → Investment Income |
  | TRANSFER_INBOUND, TRANSFER_INSTANT_INBOUND | Income Source IBAN → Income; other Own Account → Internal Transfer; otherwise Income |
  | TRANSFER_INSTANT_OUTBOUND | Own Account (incl. Income Source) → Internal Transfer; otherwise Expense |
  | TRANSFER_DIRECT_DEBIT_INBOUND | no IBAN or Own Account → Internal Transfer; Income Source → Income; otherwise Income |
  | anything else | Uncategorized, in review list |

  The mapping is stored as editable data (not hard-coded only), so that the user can map unknown types; mappings apply retroactively.
- **Categorizer**: an ordered pipeline: (1) Counterparty's Default Category, (2) merchant category code → Category default table, (3) Uncategorized. Its result is always restricted to Categories under the resolved Flow Type. Overrides always win over the pipeline.
- **Counterparty registry**: Counterparties are identified from the `name` column (`counterparty_name`/`counterparty_iban` only appear on SEPA transfers and are used for Own Account matching). Raw names are stored as Aliases; a normalizer proposes the Alias → Counterparty grouping; merge and split operations exist. A merge requires choosing the surviving Default Category.
- **Category tree**: four fixed, undeletable roots (one per Flow Type, see ADR 0001), at most two editable levels beneath each. Seeded with: Income → Salary, Investment Income (Dividends, Interest), Cashback, Other Income; Expense → Housing (Rent, Utilities), Food (Groceries, Restaurants & Cafés), Transport (Public Transport, Fuel, Taxi), Shopping (Clothing, Electronics, Household), Health & Drugstore, Leisure (Subscriptions, Travel, Culture), Insurance, Fees, Other; Investment Flow → Buy, Sell, Saveback; Internal Transfer (no children). Deletion reassigns Transactions and Default Categories to the parent (first level → Uncategorized).
- **Own Accounts**: a list of IBANs, each optionally flagged as Income Source (ADR 0002).
- **Transaction editing**: imported Transactions keep the bank's original values; Overrides (amount, date, Counterparty, Category) are stored separately and are resettable. Exclusion is a flag remembered by transaction ID, never a hard delete. Manual Transactions are fully editable and deletable. Recurring Entries (amount, Counterparty, Category, interval, start, optional end) generate Manual Transactions up to today; editing or ending one affects future occurrences only.
- **Cash-flow analytics**: given a period (and optional filter), computes monthly Income/Expense/savings rate, Category totals rolled up to parents, Sankey nodes and links, and top Counterparties. Internal Transfers and Excluded Transactions are left out; Refunds net against their Expense Category. Sankey layout: Income children → Income parents → Budget → Expense parents → Expense children, plus Investments (net Investment Flow) and Saved (remainder); a From Reserves node feeds Budget when outflows exceed Income.
- **Portfolio Statement import**: extracts with pdfplumber-style text extraction only the Holdings table (quantity, name, price per share, market value, ISIN) and the statement date ("zum DD.MM.YYYY"). Handles German number formats (decimal comma, space as thousands separator). Validates the parsed Holdings against the statement's "ANZAHL POSITIONEN" count and total and rejects the whole file on mismatch. The PDF is processed in memory and never persisted or forwarded (ADR 0003).
- **Portfolio store**: one Portfolio Snapshot per statement date (re-import replaces). Tags are stored per ISIN, independent of Snapshots.

### API (shape, not final paths)

- Upload endpoints for Transaction CSV and Portfolio Statement PDF, returning an import summary or a validation error.
- CRUD for Categories, Counterparties (incl. merge/split), Own Accounts, type mappings, Manual Transactions, Recurring Entries, Tags.
- Transaction endpoints: list with filters, set Category, set/reset Override, Exclude/restore.
- Analytics endpoints taking a period and optional filter, returning chart-ready data for bar, sunburst, Sankey, top Counterparties.
- Portfolio endpoints: list Snapshots, get Snapshot with Holdings, Portfolio value over time, allocation by Holding and by Tag.

### UI

- One upload area (drag and drop + file picker) accepting both file types, showing the import summary.
- Global period selector (month, quarter, year, custom) shared by all cash-flow views.
- Charts: hover shows sum, Transaction count and top 3 Counterparties; click filters the Transaction list below; the filter can be cleared in one click.
- Review list for Uncategorized Transactions and unknown types.
- Manual Transactions and Overrides are visibly marked.

## Testing Decisions

- Good tests exercise external behavior only: feed in files and user actions, assert on what the user would see (import summaries, Categories, chart data). They don't assert on internal tables, intermediate classes or private functions, so the internals can be refactored freely.
- **Primary seam: the backend HTTP API**, exercised through FastAPI's test client against a fresh temporary SQLite database per test. Nearly every behavior in this spec (import, Flow Type resolution, categorization, Overrides, Exclusion, merges, Category deletion, Recurring Entries, analytics, Portfolio import and validation) is observable there.
- Test fixtures are synthetic CSV rows and a synthetic Portfolio Statement PDF modeled on the real Trade Republic layouts. The real exports in the project root must not be committed or used as fixtures.
- Key scenarios to cover: re-import idempotency; Overrides and Exclusions surviving re-import; every row of the type mapping table, including Income Source and missing-IBAN cases; Refund netting; retroactive Default Category changes sparing Overrides; merge with conflicting Default Categories; Category deletion reassignment; Recurring Entry generation and editing; Sankey balance (inflows = outflows, From Reserves on deficit); German number parsing; PDF count/total mismatch rejection; Snapshot replacement on same date; Tags persisting across Snapshots.
- Frontend: no unit tests in v1 beyond type checking; chart interactions are verified manually against the running app.
- No prior art exists yet; this is a new codebase.

## Out of Scope

- Savings suggestions, goal forecasting, portfolio feedback (risk, buy/sell), and investment recommendations; these come in later versions.
- Purchase prices, cost basis and gain/loss of Holdings.
- Model-based (ML/LLM) categorization and any hosted LLM use.
- Banks other than Trade Republic, and importing the Income Source account's own statements.
- Currencies other than EUR (beyond using Trade Republic's pre-converted EUR amount).
- Multi-user support, authentication, remote hosting.
- Market data, country or sector breakdowns, per-Holding price history.
- Folder watching or automatic imports.
- Storing or re-parsing Portfolio Statement PDFs.

## Further Notes

- Spending paid directly from the Income Source account (e.g. a 36 € monthly insurance) is invisible to imports and is meant to be captured with Recurring Entries.
- The Category set by the type mapping (e.g. Investment Flow → Saveback) is a default and remains overridable like any other.
- `example.csv` and `example_portfolio.pdf` contain real personal financial data; add `*.csv` and `*.pdf` to `.gitignore` when the repository is initialized.
