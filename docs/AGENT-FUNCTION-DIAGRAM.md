# `agent.py` — function flow diagram

The whole "what should I do first?" run, in three phases: **① Setup** (where the
toolbox comes from), **② Loop** (the LLM → tool → LLM round), **③ Verify** (how a
result becomes a trustworthy answer). Read it top to bottom.

```mermaid
flowchart TD

    subgraph P1["① SETUP — where the toolbox comes from (tools.py · main.py)"]
        direction TB
        DEFS["<b>tools.py</b> — the real functions<br/>read_tasks returns t1 / t2 / t3<br/>prioritize_tasks · validate_priority_result"]
        SCHEMAS["<b>TOOL_SCHEMAS</b><br/>name → description the LLM reads"]
        TOOLSMAP["<b>TOOLS</b> dict<br/>name → the Python function"]
        MAIN["<b>main.py:84</b> run(client)<br/>hands TOOL_SCHEMAS to the loop"]
        DEFS --> SCHEMAS
        DEFS --> TOOLSMAP
        SCHEMAS --> MAIN
    end

    subgraph P2["② LOOP — run_tool_loop (agent.py)"]
        direction TB
        TURN["<b>Model turn</b><br/>client.chat.completions.create<br/>tools = TOOL_SCHEMAS"]
        READ["<b>read_tool_calls</b><br/>pull the tool requests<br/>out of the LLM message"]
        HASCALLS{"Any tool<br/>requested?"}
        RUN["<b>run_tool_call</b> (agent.py:42)<br/>look the name up in TOOLS,<br/>run it once · unknown → error"]
        FEED["add to trace, feed result<br/>back as a role:tool message"]
        CAP{"within<br/>max_iterations?"}

        TURN --> READ --> HASCALLS
        HASCALLS -- "yes" --> RUN --> FEED --> CAP
        CAP -- "yes, loop again" --> TURN
    end

    subgraph P3["③ VERIFY — final_outcome (agent.py)"]
        direction TB
        SRC{"read_tasks<br/>failed?"}
        VAL{"validation<br/>passed?"}
        OK["✅ ok: True + priority"]
        FAILSRC["⛔ task source unavailable<br/>no fabricated priority (D2-020)"]
        FAILVAL["⛔ result not validated"]

        SRC -- "yes" --> FAILSRC
        SRC -- "no" --> VAL
        VAL -- "no" --> FAILVAL
        VAL -- "yes" --> OK
    end

    MAIN ==> TURN
    HASCALLS -- "no, answers in text" --> ANSWERED["status: answered"]
    CAP -- "no, safety cap" --> STOPPED["status: stopped"]
    ANSWERED ==> SRC
    STOPPED ==> SRC

    TOOLSMAP -. "name lookup" .-> RUN

    classDef setup fill:#fff4d6,stroke:#b8860b,color:#5c4400;
    classDef loop  fill:#e7eefc,stroke:#3b5bdb,color:#1e2a5a;
    classDef gate  fill:#fdf0f6,stroke:#b5307a,color:#6b1247;
    classDef ok    fill:#d7f5dd,stroke:#2e7d32,color:#14532d;
    classDef fail  fill:#fde2e1,stroke:#c0392b,color:#7a1d16;

    class DEFS,SCHEMAS,TOOLSMAP,MAIN setup;
    class TURN,READ,RUN,FEED loop;
    class HASCALLS,CAP,SRC,VAL gate;
    class OK,ANSWERED ok;
    class FAILSRC,FAILVAL,STOPPED fail;
```

## How to read it

**① Setup — where the toolbox comes from** (yellow)
- `tools.py` holds the real functions. `read_tasks` is where the task strings
  (t1/t2/t3) physically live — the LLM never sees this code.
- Each tool has two name bindings: `TOOL_SCHEMAS` (name → the description the
  LLM reads, so it knows *when* to ask) and `TOOLS` (name → the Python function,
  so we can *run* what it asked for).
- `main.py:84` hands `TOOL_SCHEMAS` to the loop (thick arrow into ②). That is
  the moment the toolbox is handed over.

**② Loop — `run_tool_loop`** (blue, with pink decisions)
1. The LLM takes a turn with the schemas as `tools`.
2. `read_tool_calls` extracts any tool requests.
3. No tool → `status: answered`. Tool → `run_tool_call` looks the name up in
   `TOOLS` (dotted arrow from ①), runs it once, feeds the result back.
4. Loop again until the model answers, or `max_iterations` stops it →
   `status: stopped` (the safety cap).

**③ Verify — `final_outcome`** (green = good, red = honest refusal)
- `read_tasks` failed → ⛔ no priority at all, never a fabricated one (D2-020).
- validation (`validate_priority_result`) did not pass → ⛔.
- validation passed → ✅ the verified priority is returned.

**One-line summary:** the task strings are born in `tools.py`, the tool names are
handed to the LLM by `main.py`, the real call happens at `agent.py:42`, and no
answer is shown unless `final_outcome` verified it.

> `build_tool_result_message` (not drawn) does the same "run + wrap as role:tool"
> work as steps **run_tool_call + feed** combined; the loop does it inline instead.
