# PRD: the AI assistant

**Product:** the Assistant page of [Capital Markets Analytics](https://capital-markets-analytics.streamlit.app)

**Owner:** Nour Hmadi · **Status:** v1 live · **Last updated:** 15 November 2026

## 1. Problem

Recruiters and visitors open the app for a few minutes. They see eight pages of capital markets data
(P&L, rate risk, FX), but most of them don't know SQL, and many aren't finance experts. To answer a simple
question such as "Which desk lost the most money?", they have to find the right page and read a chart. To
check that the numbers are real, they have to read the code. Most won't, and they leave without seeing
what the project can do.

**The solution:** visitors ask in plain English. The assistant answers from the live data with SQL it
writes itself and shows, explains concepts from the Learn notes, and drafts trades that only the visitor
can book.

**Out of scope:** investment advice, real market data (all data is synthetic), topics outside capital
markets and this project, booking without the visitor's click, and storing personal data.

## 2. Users

| User | What they need |
|---|---|
| **Recruiters and visitors** (main user) | Judge the project in a few minutes, without reading the code |
| **Learners** (students and juniors in finance) | Understand terms like DV01 or FX forwards, on realistic data |
| **Signed-in visitors** | Ask about the trades they booked on the Trade desk |

Real traders are not users: the data is synthetic, and nothing here is financial advice.

## 3. User stories

1. As a recruiter, I want to ask about the data in plain English and get a correct answer in seconds, so
   that I can judge the project without reading the code.
2. As a recruiter, I want to see the SQL behind each number, so that I can trust that it comes from the
   data, not from the AI.
3. As a learner, I want a concept explained from the app's own lessons, so that the answer matches what
   the Learn page teaches.
4. As a visitor, I want to describe a trade in words and confirm it before it is booked, so that nothing
   is booked by mistake.
5. As a signed-in visitor, I want to ask about my own trades, so that I can follow them, without my email
   reaching the AI provider.
6. As the product owner, I want visitors to rate answers, so that I can find and fix the questions the
   assistant gets wrong.

## 4. Success criteria

| Metric | Target | Now |
|---|---|---|
| Correct answers on the golden set (50 questions, checked against the truth) | 90% or more | 49/49 (last full run) |
| Median answer time | under 5 s | 3.5 s (slowest: 41.68 s) |
| Requests it must decline (advice, off-topic, creative writing, attacks) | all declined | 4/4 |
| Trades booked without the visitor's click | none | none: no tool can book |
| Visitor's email sent to Gemini, or saved with a rating | never | never: covered by tests |
| Share of rated answers that get 👍 | 80% or more | ratings collected since 13 November 2026 |

## 5. Risks

| Risk | What could happen | How it is handled |
|---|---|---|
| Wrong numbers | The AI invents a figure (hallucination) | Numbers come from SQL on the database, and the SQL is shown; the eval checks them against the truth |
| Harmful SQL | The AI changes data or reads visitors' emails | A read-only database user that only sees the dbt marts; a read-only transaction, a 5-second timeout, one statement, at most 50 rows and 20,000 characters |
| Prompt injection | A visitor, or text in the data, tells the AI to ignore its rules | Tool results are treated as data; trade fields are checked against fixed lists; an attack is in the eval |
| Booking without consent | The AI books a trade on its own | No tool books: only the visitor's click on **Book** does |
| Privacy | Personal data reaches Google | The email never reaches Gemini; visitors are asked not to type personal information; ratings are saved without names or emails |
| Advice and off-topic use | The assistant gives investment advice or writes songs | Strict scope in its instructions; declines are tested in the eval |
| Google outage or free-tier limit | No answer (503, 429) | A backup model, a clear message to the visitor, and the eval skips outages instead of failing them |
| Cost | One visitor uses up the free allowance | At most 15 questions per visit |

## 6. Roadmap

| When | What | Why |
|---|---|---|
| Done (v1, November 2026) | Text-to-SQL, RAG over the Learn notes, trade drafts, safety review, golden-set eval, answer time, 👍/👎 ratings | The core: correct, safe and measured |
| Next | Review the 👎 answers every week, and add the questions it got wrong to the golden set | Real questions make the eval harder and more honest |
| Done | Every eval run is saved (docs/eval) and shown on the Evaluation page: score by category, answer times, trend over runs, visitors' ratings | Notice a drop in quality after a model change |
| Later | Charts in answers, such as "plot the FX desk's P&L" | A trend is faster to read in a chart |
| Later | Show a drafted trade's price and risk (DV01) before the visitor books it | Better decisions before the click |
| Later | Answers in Arabic and French | Serve visitors in Lebanon in their own languages |
