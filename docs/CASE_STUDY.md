# Case study: the AI assistant of the Capital Markets Analytics app

*One page on how an AI feature went from a problem to a measured product. Companion to the [PRD](PRD.md).*

## The problem

The app shows a small trading book: three desks, 60 trades, daily P&L and risk. A visitor who wants a plain
answer ("which desk lost the most yesterday?") has to find the right page, read a chart, or know SQL. Recruiters
and students, the people the app is for, mostly don't. The question was: can a visitor ask in English and get a
correct answer from the live data, without the app ever giving advice or changing anything?

## Users and constraints

- **Visitors** (recruiters, students) want quick, correct answers and explanations of the terms.
- **The owner** wants to show the work and keep the data safe.
- Constraints: free to run (Google Gemini's free tier), questions are sent to Google so **no personal data**,
  the AI must **never give investment advice**, and it must **never book, change or delete a trade** on its own.

## Options considered

| Option | Why not |
|---|---|
| Fixed buttons ("P&L by desk", "Top losers") | Covers only the questions I thought of; no explanations |
| Text-to-SQL only | Answers numbers but can't explain DV01 or draft a trade |
| **An agent with tools** (chosen) | Picks the tool a question needs: SQL for data, the Learn notes for concepts, the trade desk for the visitor's own trades |

The agent is the only option that serves all three kinds of questions, so it was worth the extra risk, which the
guardrails below control.

## What was built

A LangChain agent on Gemini (LangGraph model-tools loop) with three tools:
1. **Read-only SQL** through the API, as a database user that can only `SELECT` from the marts: the AI cannot
   write, and the SQL it ran is shown with every answer.
2. **Retrieval over the Learn notes** (small RAG): concept questions are answered from the project's own lessons.
3. **Trade drafts**: the AI fills in a draft; only the visitor's click books it (four-eyes control).

Plus: a backup model when Google is busy, a clear message on outages, a privacy page, and 👍/👎 on every answer.

## How success is measured

| Criterion | Target | Last run |
|---|---|---|
| Correct answers on a golden set of 50 questions, checked against the database, the notes or the trade desk | ≥ 90% | 49/49 answered (1 skipped: Google outage) |
| Median answer time | < 5 s | 3.5 s |
| Must decline (advice, predictions, off topic, creative writing, prompt injection, SQL attacks) | 100% | 8/8 |
| Says "no data" instead of inventing a number | 100% | 2/2 |
| Visitors' thumbs up | ≥ 80% | shown live on the Evaluation page |

Every run is saved (docs/eval) and the app's **Evaluation** page shows the score by category, the answer times,
the wrong answers and the trend over runs.

## What went wrong, and what I learned

- **Outages are not errors.** Early runs failed on Google 503s. Now an outage skips the question and a backup
  model answers visitors: availability and accuracy are measured separately.
- **The check can be wrong, not the model.** Twice the model was right ("there is no series INDEX_ASIA"; a bond
  question answered from the DV01 lesson) and my scoring was too narrow. Fixing the test, not the model, is part
  of evaluation work.
- **Scope creep is one prompt away.** Visitors asked for poems and songs; the scope rule had to be explicit, and
  it is tested.

## What's next

Review the 👎 answers every week and add their questions to the golden set; expand the notes so concept
questions cover more of the Learn section; add a cost-per-answer metric before moving off the free tier.
