# Test review — Dani V1 (25 November 2026)

## Coverage
- 510 tests, all green; no test calls a real API (fakes only).
- Product code: **100% line and branch coverage** (`python3 -m pytest --cov=. --cov-branch`).
  Three defensive checks in `/api/confirm` that no normal flow can reach are
  marked `pragma: no cover - defensive`.

## Mutation testing (the test of the tests)
`python3 -m mutmut run` on every product module (`setup.cfg`):

| Mutants | Killed | Survived | Timeout |
|---|---|---|---|
| 7854 | 6192 (79%) | 1649 | 13 |

Survivors per module:

```
    264     server
    251     notion_client
    138     render
    128     memory_store
     89     chat
     75     gcal_client
     71     mail_client
     65     fitbit_client
     59     telegram_client
     59     dashboard
     53     reader
     38     twilio_client
     38     forecast
     36     propose
     35     notify
     35     ical_client
     34     live
     28     evals
     27     wake
     27     mood
     25     wake_call
     13     focus
     12     usage
      9     reminders
      9     planner
      8     context
      8     briefing
      7     agent
      4     store
      2     cycle
      1     tracing
      1     main
```

### What the survivors are
1. **Real gaps — to kill.** Tests that run a line but do not check its exact
   output: the field names and headers sent to Supabase, Notion, Telegram,
   Twilio and Fitbit (`ref` → `REF`, `Prefer`, a client id replaced by
   `None`), and boundaries (`<=` → `<`; the first one, due dates in
   `read_tasks`, is fixed with a test).
2. **Equivalent or harmless — to mark, not to test.** Changes that do not
   change behaviour: a network timeout 20 → 21 s, the casing of a tool
   description, `"Date"` → `"DATE"` (mail headers are case-insensitive).

### Plan
1. Logic modules first (reader, forecast, propose, mood, wake, wake_call,
   reminders, focus, live, planner): every non-equivalent survivor killed.
2. API clients (memory_store, notion_client, telegram_client, twilio_client,
   fitbit_client, mail_client, gcal_client, ical_client, notify): assert the
   exact request (URL, method, headers, body) in one test per call.
3. server.py and the old dashboard (render, dashboard): last; render.py is the
   5 November static page and may be retired instead.
4. Target: no surviving non-equivalent mutant; equivalent ones listed here.
