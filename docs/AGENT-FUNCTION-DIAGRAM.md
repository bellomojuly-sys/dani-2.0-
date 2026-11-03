# `agent.py` — function flow diagram

How the functions in `agent.py` call each other and how data flows through
the LLM → tool → LLM round. Read top to bottom: it describes one full run.

```mermaid
flowchart TD
    subgraph SETUP["Setup: where the toolbox comes from"]
        direction TB
        DEFS["tools.py — the real Python functions<br/>read_tasks → returns t1/t2/t3 strings<br/>prioritize_tasks · validate_priority_result"]
        SCHEMAS["TOOL_SCHEMAS (tools.py)<br/><i>name → description the LLM reads<br/>e.g. 'read_tasks: return the user's tasks'</i>"]
        TOOLSMAP["TOOLS dict (tools.py)<br/><i>name string → Python function<br/>'read_tasks' maps to read_tasks()</i>"]
        DEFS --> SCHEMAS
        DEFS --> TOOLSMAP
    end

    SCHEMAS --> MAIN["main.py:84 — run(client)<br/><i>hands TOOL_SCHEMAS to the loop</i>"]
    MAIN --> START([Entry: run_tool_loop])
    START --> TURN{{"Model turn<br/>client.chat.completions.create<br/><i>tools = TOOL_SCHEMAS</i>"}}

    TURN --> READ["read_tool_calls(message)<br/><i>extract the tool requests<br/>from the LLM message</i>"]

    READ --> HASCALLS{Any<br/>tool calls?}

    HASCALLS -->|No, answers in text| ANSWERED["status: answered<br/>+ final + trace"]
    HASCALLS -->|Yes| RUN["run_tool_call(call, TOOLS)<br/><i>look the name up in TOOLS,<br/>run the tool exactly ONCE<br/>unknown name → {error}</i>"]
    TOOLSMAP -.name lookup.-> RUN

    RUN --> APPEND["append to trace<br/>{name, result}<br/>and feed the result back<br/>as a role: tool message"]
    APPEND --> CAP{Within<br/>max_iterations?}
    CAP -->|Yes| TURN
    CAP -->|No, safety cap| STOPPED["status: stopped<br/>trace, final: None"]

    ANSWERED --> OUTCOME["final_outcome(loop_result)"]
    STOPPED --> OUTCOME

    OUTCOME --> SRC{read_tasks<br/>failed?}
    SRC -->|Yes| FAILSRC["ok: False<br/>'task source unavailable'<br/><i>no fabricated priority (D2-020)</i>"]
    SRC -->|No| VAL{validate_priority_result<br/>valid == True?}
    VAL -->|No| FAILVAL["ok: False<br/>'result not validated'"]
    VAL -->|Yes| OK["ok: True<br/>'validated'<br/>+ priority"]

    subgraph HELPER["Equivalent helper (not used inside the loop)"]
        BUILD["build_tool_result_message(call)<br/><i>run_tool_call + wrap<br/>as a role: tool message</i>"]
    end
    BUILD -.uses.-> RUN

    classDef ok fill:#d7f5dd,stroke:#2e7d32,color:#14532d;
    classDef fail fill:#fde2e1,stroke:#c0392b,color:#7a1d16;
    classDef proc fill:#e7eefc,stroke:#3b5bdb,color:#1e2a5a;
    classDef setup fill:#fff4d6,stroke:#b8860b,color:#5c4400;
    class OK ok;
    class FAILSRC,FAILVAL,STOPPED fail;
    class READ,RUN,APPEND,BUILD,OUTCOME proc;
    class DEFS,SCHEMAS,TOOLSMAP,MAIN setup;
```

## Reading the diagram

**Setup — where the toolbox comes from** (yellow nodes, `tools.py` + `main.py`)
- `tools.py` holds the real Python functions. `read_tasks` is where the task
  strings (t1/t2/t3) physically live — the LLM never sees this code.
- Each function has two name bindings: `TOOL_SCHEMAS` (name → the description
  the LLM reads, so it knows *when* to ask) and `TOOLS` (name string → the
  Python function, so we can *run* what it asked for).
- `main.py` hands `TOOL_SCHEMAS` to `run_tool_loop`. That is the moment the
  toolbox is handed over.
- When the LLM says "read_tasks", `run_tool_call` looks that name up in
  `TOOLS` (dotted arrow) and runs the real function — the LLM gets the real
  data back, it cannot invent it.

**The loop** (`run_tool_loop`)
1. The LLM takes a turn → `read_tool_calls` extracts any tool requests.
2. No tool requested → `status: answered`. Tools requested → `run_tool_call`
   runs each tool **once** (unknown name = `{error}`, never a crash).
3. The result goes into the `trace` and is fed back to the LLM as a
   `role: tool` message.
4. Repeat until the model answers, or `max_iterations` cuts the round →
   `status: stopped` (the safety cap).

**The verification** (`final_outcome`), the three outcomes in colour:
- 🟥 `read_tasks` failed → `ok: False`, no fabricated priority (D2-020).
- 🟥 validation did not pass → `ok: False`.
- 🟩 `validate_priority_result` valid → `ok: True` + priority.

`build_tool_result_message` does the same "run + wrap as `role: tool`" work,
but it is not used inside the loop (there the step is done inline).
