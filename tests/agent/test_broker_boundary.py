from backend.tools import APPROVED_BROKER_TOOL_NAMES, validate_broker_tools


def test_broker_tool_allowlist_excludes_oracle():
    assert "submit_oracle_resolution" not in APPROVED_BROKER_TOOL_NAMES

    def get_wallet_balance() -> None:
        return None

    def purchase_policy() -> None:
        return None

    validate_broker_tools([get_wallet_balance, purchase_policy])

    def oracle() -> None:
        return None

    oracle.__name__ = "oracle"
    try:
        validate_broker_tools([oracle])
    except ValueError as exc:
        assert "forbidden broker tools" in str(exc)
    else:
        raise AssertionError("oracle tool should be rejected")
