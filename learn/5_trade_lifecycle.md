# Trade lifecycle

A trade is not finished when it is agreed. In a bank it passes through three teams, and platforms like Murex
follow it through every step, "front to back":

- **Front office:** traders agree and book the trade.
- **Middle office:** risk and P&L teams check, value and measure the trade every day.
- **Back office:** operations teams confirm the trade with the other bank and settle it, exchanging the
  cash and the securities.

This app follows the same path. When you click **Book trade** on the Trade desk:

1. **Capture:** the page sends the trade to the API.
2. **Validation:** the API rejects bad input, such as a weekend date, an unknown bond or a negative quantity.
3. **Pricing:** the trade is priced at that day's market: the index close, the bond price or the FX forward.
4. **Storage:** it is saved in a PostgreSQL database in the cloud with its own trade ID (T9xxxx).
5. **Valuation and risk:** it is valued at the latest market prices, with its P&L and DV01. For the official
   book, a pipeline recalculates every trade each weekday morning and the Portfolio page shows the results.
6. **Messaging:** the trade can be sent as an **XML** message, the format systems use to pass trades to each
   other, for example from the trading platform to settlement. Every message is checked against an **XSD**
   schema first, so the receiving system never gets a malformed trade.
7. **Settlement:** on the settlement or maturity date, the cash and securities change hands. The app stops
   here: it shows a forward's maturity date, but no real money moves.

Changing or cancelling a trade is part of the lifecycle too. Real systems keep every version with an
**audit trail** (who changed what, and when), because regulators and auditors can ask for it.

## Quiz

Q: Which team confirms and settles trades?
A) Front office
B) Middle office
C) Back office
Answer: C
Why: The back office confirms trades with the other bank and settles them by exchanging cash and securities.

Q: Why is every XML trade message checked against an XSD schema before it is sent?
A) To make the message smaller
B) So the receiving system never gets a malformed trade
C) To encrypt the message
Answer: B
Why: The XSD defines the exact structure a valid message must follow, so errors are caught before sending.

Q: Which team measures the P&L and risk of all trades every day?
A) Middle office
B) Front office
C) Back office
Answer: A
Why: The middle office values every trade independently and reports the P&L and risk.
