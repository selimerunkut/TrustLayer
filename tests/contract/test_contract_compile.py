from pathlib import Path
import json


def test_insurance_manager_solidity_compiles_via_solc():
    import subprocess

    source = Path("contracts/InsuranceManager.sol").read_text()
    input_json = {
        "language": "Solidity",
        "sources": {"InsuranceManager.sol": {"content": source}},
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "viaIR": True,
            "outputSelection": {"*": {"*": ["abi"]}},
        },
    }
    proc = subprocess.run(
        ["npx", "--yes", "solc@0.8.24", "--standard-json"],
        input=json.dumps(input_json).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = proc.stdout.decode()
    if payload.startswith(">>>"):
        payload = payload.splitlines()
        payload = "\n".join(payload[1:])
    output = json.loads(payload)
    errors = [item for item in output.get("errors", []) if item.get("severity") == "error"]
    assert not errors
    abi = output["contracts"]["InsuranceManager.sol"]["InsuranceManager"]["abi"]
    names = {item.get("name") for item in abi if item.get("type") == "function"}
    assert {"purchasePolicy", "rejectPolicy", "resolvePolicy", "refundPolicy", "payOut", "premiumVault"} <= names
