from collections.abc import Callable, Iterable


APPROVED_BROKER_TOOL_NAMES = (
    "get_wallet_balance",
    "prepare_budget_authorization",
    "get_research_allowance",
    "pay_knowledge_service",
    "get_policy_recommendation",
    "purchase_policy",
    "reject_policy",
    "get_policy_status",
)

FORBIDDEN_BROKER_TOOL_NAMES = {"oracle", "submit_oracle_resolution"}


def tool_name(tool: object) -> str:
    return getattr(tool, "name", getattr(tool, "__name__", tool.__class__.__name__))


def validate_broker_tools(tools: Iterable[Callable[..., object]]) -> None:
    names = [tool_name(tool) for tool in tools]
    forbidden = sorted(name for name in names if name in FORBIDDEN_BROKER_TOOL_NAMES)
    if forbidden:
        raise ValueError(f"forbidden broker tools: {', '.join(forbidden)}")
    unexpected = sorted(name for name in names if name not in APPROVED_BROKER_TOOL_NAMES)
    if unexpected:
        raise ValueError(f"unapproved broker tools: {', '.join(unexpected)}")
