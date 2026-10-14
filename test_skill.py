from skill import TOOLBOX_SKILL, TOOL_ORDER
from tools import TOOLS


def test_skill_names_the_three_tools_in_the_right_order():
    # Each tool name must appear in the policy text, and in this order.
    positions = [TOOLBOX_SKILL.index(name) for name in TOOL_ORDER]
    assert positions == sorted(positions)


def test_tool_order_covers_exactly_the_registered_tools():
    assert set(TOOL_ORDER) == set(TOOLS)


def test_skill_forbids_inventing_tasks():
    assert "never invent" in TOOLBOX_SKILL.lower()
