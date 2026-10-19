# Financial Manager

A personal, locally run tool that turns bank and broker exports into a picture of where money comes from, where it goes, and how it is invested.

## Language

### Cash flow

**Transaction**:
A single money movement on the account, as exported by the bank.
_Avoid_: Booking, entry, payment

**Manual Transaction**:
A Transaction entered by the user rather than imported, e.g. to cover spending made outside the main account.

**Recurring Entry**:
A rule that generates a Manual Transaction at a fixed interval (e.g. 36 € insurance on the 1st of every month).
_Avoid_: Standing order, subscription

**Override**:
A user change to an imported Transaction's amount, date, Counterparty or Category; it survives re-imports and can be reset to the bank's original.
_Avoid_: Edit, correction

**Excluded**:
The state of an imported Transaction the user removed; it is hidden everywhere and stays removed on re-import, but can be restored.
_Avoid_: Deleted, hidden

**Counterparty**:
The other party in a Transaction, whichever way the money flows. One Counterparty can be known under several Aliases.
_Avoid_: Recipient, sender, payee, merchant

**Alias**:
A raw name under which a Counterparty appears in bank exports (e.g. "DM-FIL. A1EN" for the Counterparty "dm"). It is taken from the Transaction's name, or from its description when the name says too little; never from the export's counterparty name field, which is unreliable.
_Avoid_: Raw name, variant

**Flow Type**:
One of four fixed kinds of money movement: Income, Expense, Investment Flow, Internal Transfer. Every Category belongs to exactly one Flow Type.
_Avoid_: Transaction type, direction

**Category**:
The class a Transaction belongs to (e.g. Expense → Food → Groceries). Categories form an editable hierarchy of at most two levels under each Flow Type; a Transaction has exactly one.
_Avoid_: Label, type

**Refund**:
Money coming back on an Expense Category; it reduces spending in that Category rather than counting as Income.

**Own Account**:
An account of the user's at another bank, identified by IBAN; transfers to or from it are Internal Transfers, unless it is an Income Source.

**Income Source**:
An Own Account through which the user's income arrives; transfers in from it count as Income, transfers out to it remain Internal Transfers.
_Avoid_: Salary account, feeder account

**Default Category**:
The Category remembered for a Counterparty and suggested for its future Transactions; a single Transaction may override it.
_Avoid_: Known label, rule

**Uncategorized**:
The state of a Transaction for which no Category could be determined and which awaits review.

**Investment Flow**:
A Transaction that moves money into or out of securities (buys, sells, savings plans); it is neither income nor spending.
_Avoid_: Trade expense

**Internal Transfer**:
A Transaction moving money between the user's own accounts; it is neither income nor spending.

### Investments

**Portfolio Statement**:
The broker's PDF listing all securities held as of a given date.
_Avoid_: Depotauszug, portfolio PDF

**Holding**:
One security (identified by its ISIN) held in a quantity at a price, as listed in a Portfolio Statement.
_Avoid_: Investment, position, asset

**Portfolio Snapshot**:
The set of all Holdings as of one Portfolio Statement's date. "The Portfolio" means the latest Portfolio Snapshot.
_Avoid_: Depot

**Tag**:
A free-form marker attached to a Holding (by ISIN); a Holding can carry any number of Tags and keeps them across Snapshots.
_Avoid_: Label, category
