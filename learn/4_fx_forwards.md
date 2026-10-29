# FX forwards

An **exchange rate** is the price of one currency in another. EURUSD = 1.11 means 1 euro costs 1.11 US
dollars: EUR is the **base** currency and USD the **quote** currency. The app follows EURUSD, GBPUSD and
USDJPY.

A **spot** trade exchanges the currencies now, at today's rate. An **FX forward** fixes the rate today for an
exchange on a future date, in 3, 6 or 12 months. Companies use forwards to lock in a rate: a European firm
that must pay dollars in a year knows today exactly how many euros it will cost.

The forward rate is not the spot rate, because the two currencies earn different interest. In the app, a
dollar deposit earns 4% a year and a euro deposit 2%. If the forward were equal to spot, you could borrow
euros at 2%, change them into dollars, earn 4%, and lock in the way back with the forward: a free profit.
To remove it, the forward follows **interest rate parity**:

Forward = spot × (1 + dollar rate)^T ÷ (1 + euro rate)^T, where T is the time in years

For example, on 3 March 2025 EURUSD was 1.11222. A 12-month forward on the Trade desk is
1.11222 × 1.04 ÷ 1.02 = **1.13403**. Buying 1,000,000 EUR forward means paying 1,134,030 USD for them on
3 March 2026. By 18 December 2025 the euro had risen to 1.13719, so the euros you will receive are worth more
and the P&L is **+$7,645**. A buyer of EURUSD gains when the euro strengthens; a seller gains when it weakens.

## Quiz

Q: EURUSD = 1.10. What does that mean?
A) 1 US dollar costs 1.10 euros
B) 1 euro costs 1.10 US dollars
C) The euro rate rose by 10%
Answer: B
Why: The first currency (EUR) is the base: the rate is its price in the second currency (USD).

Q: What is an FX forward?
A) Exchanging two currencies today at today's rate
B) Agreeing today on the rate for an exchange on a future date
C) A loan in a foreign currency
Answer: B
Why: A forward fixes the exchange rate today for a later date, so the future cost is known now.

Q: Dollar rates are 4% and euro rates 2%. Is the 1-year EURUSD forward above or below spot?
A) Above spot
B) Below spot
C) Equal to spot
Answer: A
Why: Forward = spot × 1.04 ÷ 1.02, about 2% above spot: the lower-rate currency (EUR) trades higher forward.
