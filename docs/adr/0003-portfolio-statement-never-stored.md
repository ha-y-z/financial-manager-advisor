# Portfolio Statements are never stored

The broker's Portfolio Statement PDF contains personal data (name, address, account numbers) next to the Holdings. On import, only the Holdings table (ISIN, name, quantity, price, market value) and the statement date are extracted in memory; the PDF itself is discarded and never written to disk or passed to any LLM. This means a Snapshot cannot be re-parsed later if the parser improves; the user must re-upload the original file.
