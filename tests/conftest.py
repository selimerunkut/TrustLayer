import pytest


@pytest.fixture
def oracle_privileged_headers(monkeypatch) -> dict[str, str]:
    token = "oracle-token"
    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", token)
    return {"X-Oracle-Token": token}


@pytest.fixture
def trustlayer_internal_headers(monkeypatch) -> dict[str, str]:
    token = "trustlayer-token"
    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", token)
    return {"X-TrustLayer-Token": token}
