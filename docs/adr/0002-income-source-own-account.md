# Income arrives via an Own Account flagged as Income Source

The user's salary lands at another bank and is then transferred to Trade Republic, the main account. Treating that transfer as an Internal Transfer (the default for Own Accounts) would make almost all income disappear from the charts. We considered giving the other account's Counterparty a Default Category of Income → Salary, and importing the other bank's CSV, but chose an **Income Source** flag on the Own Account: inbound transfers from it count as Income, outbound transfers to it stay Internal Transfers. The rule lives on the account, where it is visible, instead of being hidden in a Default Category that would misclassify outbound transfers.

## Consequences

Spending paid directly from the Income Source account is invisible to the import; the user records it as Manual Transactions or Recurring Entries.
