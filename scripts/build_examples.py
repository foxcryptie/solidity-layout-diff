"""Regenerate checked-in layout examples from actual Solidity compiler output."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/contracts/VaultVariants.sol"
OUTPUT = ROOT / "examples/layouts"


def main() -> None:
    source_name = "VaultVariants.sol"
    payload = {
        "language": "Solidity",
        "sources": {source_name: {"content": SOURCE.read_text(encoding="utf-8")}},
        "settings": {"outputSelection": {"*": {"*": ["storageLayout"]}}},
    }
    result = subprocess.run(["solc", "--standard-json"], input=json.dumps(payload),
                            text=True, capture_output=True, check=True)
    content = result.stdout[result.stdout.find("{"):]
    document = json.loads(content)
    errors = [item for item in document.get("errors", [])
              if item.get("severity") == "error"]
    if errors:
        raise RuntimeError(errors)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, artifact in document["contracts"][source_name].items():
        path = OUTPUT / f"{name}.json"
        path.write_text(json.dumps(artifact["storageLayout"], indent=2) + "\n",
                        encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
