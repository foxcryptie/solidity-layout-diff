# Solidity Layout Diff

Did an upgrade move or reinterpret a variable that was already in storage? `slotdiff` compares the `storageLayout` JSON emitted by `solc` and gives that question a CI-friendly exit code. It does not inspect the rest of an upgrade.

## Try the checked-in examples

Python 3.11+ is enough; there are no runtime dependencies or RPC calls.

```bash
python -m pip install -e .
slotdiff examples/layouts/VaultV1.json examples/layouts/VaultV2Append.json
slotdiff examples/layouts/VaultV1.json examples/layouts/VaultV2Reordered.json --json
```

The first pair appends storage and returns `PASS`. The second moves packed variables and returns `FAIL`; the output names `owner` and `feeBps` and shows their changed byte positions. These JSON files were compiled from [`VaultVariants.sol`](examples/contracts/VaultVariants.sol) with `solc` 0.8.37.

| Result | Exit code | What to do |
| --- | ---: | --- |
| `PASS` | 0 | Existing variables kept their position and recursive type; additions are after occupied storage. Continue the rest of the upgrade review. |
| `REVIEW` | 1 | A gap changed, a name may have changed, or new data uses an earlier free byte. Check the intent with an upgrade-aware tool. |
| `FAIL` | 2 | An existing variable moved, disappeared, or changed type, or a new variable overlaps occupied bytes. |
| `UNASSESSED` | 3 | Input is missing, ambiguous, malformed, or has no supported top-level storage. Do not treat it as a pass. |

Names are used to match variables. A same-position, same-type rename is therefore `REVIEW`, not an automatic pass. Empty and namespaced layouts are currently `UNASSESSED`.

## Input from your own build

Pass a raw `storageLayout` object or full Solidity standard-JSON output. If the compiler output contains multiple contracts, select one on each side:

```bash
slotdiff old-solc.json new-solc.json \
  --old-contract src/Vault.sol:VaultV1 \
  --new-contract src/Vault.sol:VaultV2 \
  --json
```

Ask `solc` for layouts with `{"settings":{"outputSelection":{"*":{"*":["storageLayout"]}}}}`. The [compiler documentation](https://docs.soliditylang.org/en/latest/internals/layout_in_storage.html) describes the fields and marks this output experimental.

`slotdiff` checks slots, byte offsets, and recursive type metadata for mappings, arrays, and structs. It does not check initializers, permissions, proxy kind, selectors, ABI compatibility, or runtime behavior. Use an [upgrade-aware validator](https://docs.openzeppelin.com/upgrades-plugins/writing-upgradeable) for a production upgrade.

## Development

```bash
python -m unittest discover -s tests -v
python scripts/build_examples.py  # requires solc; regenerates the fixtures
```

CI runs the tests against the checked-in layouts, so `solc` is only needed when regenerating them.
