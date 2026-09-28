# Capital Markets Analytics Dashboard

A self-learning data project to understand how capital markets work, by collecting real market data, analyzing it, and turning it into visual insights.

> **Status: in progress.** See the roadmap below.

## Why this project

I'm building this project to learn about capital markets hands-on. The focus is not the code itself, but what the data shows: how stock prices, government bond yields and exchange rates move, and how they relate to each other. Python, SQL and Power BI are the tools I use to explore these questions.

## What are capital markets?

Capital markets are where governments, companies and investors raise and trade money through financial products. This project covers three of the main ones:

| Asset class | What it is | What the data shows |
|---|---|---|
| **Equities (stocks)** | Shares of ownership in companies | Stock index prices and daily returns (%) |
| **Rates (government bonds)** | Loans to a government; the *yield* is the interest rate it pays | Bond yields and their daily change in basis points (1 bp = 0.01%) |
| **FX (foreign exchange)** | The price of one currency in another | Exchange rates such as EUR/USD, and their daily changes |

## Questions this dashboard will answer

- How much did major stock markets gain or lose over time?
- How do government bond yields differ across maturities (the **yield curve**)?
- How do major currencies move against the US dollar?
- When stock markets fall, what happens to bonds and currencies?

## How it works (planned)

```
Public REST APIs  →  Python (collect & clean)  →  PostgreSQL (store)  →  Power BI (visualize)
                          ↑
          pytest data-quality checks, run automatically with GitHub Actions
```

## Roadmap

- [x] Define the project goals and scope
- [ ] Day 1: capital markets basics
- [ ] Explore market data REST APIs and JSON in Postman
- [ ] Collect equity, bond yield and FX data with Python
- [ ] Clean the data and calculate daily returns and basis-point changes
- [ ] Add pytest data-quality checks and GitHub Actions (CI)
- [ ] Store the data in PostgreSQL
- [ ] Read ECB exchange rates published in XML
- [ ] Build the Power BI dashboard
- [ ] Write up the key insights

## Tools

Python · pandas · REST APIs · JSON · XML · Postman · SQL · PostgreSQL · Unix · Power BI · pytest · GitHub Actions

---

*Author: Nour Hmadi · [LinkedIn](https://www.linkedin.com/in/nour-hmadi-b86a29438) · [GitHub](https://github.com/nour-hmadi)*
