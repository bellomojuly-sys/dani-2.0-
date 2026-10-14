"""The task toolbox skill: the written policy that tells the LLM when and in
what order to use the three tools.

It lives here as plain text (not buried in main.py) so it can be inspected and
tested on its own, and it is injected into the system message. TOOL_ORDER is
the same order in machine-readable form, so a test can check the policy against
the tools that are actually registered.
"""

# The order the model must follow: read the real tasks, decide and record the
# priority, then validate the result before trusting it.
TOOL_ORDER = ["read_tasks", "prioritize_tasks", "validate_priority_result"]

TOOLBOX_SKILL = (
    "You have a task toolbox. Use it in this exact order:\n"
    "1. Call read_tasks first to get the real tasks. Never work from memory.\n"
    "2. Decide the priority order yourself, then call prioritize_tasks, passing "
    "every task back most-important-first, each with a one-line reason.\n"
    "3. Call validate_priority_result with that priority and the ids from "
    "read_tasks, to check the report before you trust it.\n"
    "Only talk about tasks that read_tasks returned; never invent a task."
)
