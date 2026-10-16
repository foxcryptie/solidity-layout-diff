# Solidity Layout Diff

An offline Python CLI for reviewing the storage-layout part of a Solidity
upgrade. It compares the `storageLayout` objects emitted by `solc`, reports the
variables affected, and returns an exit code suitable for CI.

**Scope:** This is a conservative first-pass diagnostic, not an upgrade-safety
certificate. Use an upgrade-aware validator such as OpenZeppelin's
`validateUpgrade` for the full implementation review.

## Quick start

Python 3.11+; no runtime dependencies or RPC credentials.

```bash
python -m pip install -e .
slotdiff examples/layouts/VaultV1.json examples/layouts/VaultV2Append.json
slotdiff examples/layouts/VaultV1.json examples/layouts/VaultV2Reordered.json --json
```

The checked-in layouts were compiled from
[`examples/contracts/VaultVariants.sol`](examples/contracts/VaultVariants.sol)
with `solc` 0.8.37. The first command returns `PASS`; the second returns
`FAIL` and identifies the moved `owner` and `feeBps` byte positions.

## Results

| Status | Exit | Meaning |
|---|---:|---|
| `PASS` | 0 | Existing variables retain their position and recursive type; new variables append after occupied storage. |
| `REVIEW` | 1 | Storage gaps, possible renames, or additions in earlier unused bytes need human or upgrade-aware validation. |
| `FAIL` | 2 | Existing variable moved, disappeared, changed type, or new storage overlaps occupied bytes. |
| `UNASSESSED` | 3 | Input is missing, ambiguous, malformed, or has no supported top-level storage. |

`PASS` covers only the storage properties above. It says nothing about
initializers, permissions, proxy kind, function selectors, ABI compatibility,
or runtime behavior. `REVIEW` is intentionally distinct from `FAIL`: shrinking
an OpenZeppelin-style `__gap` can be valid, but needs gap accounting.

## Compiler input

The CLI accepts either a raw `storageLayout` object or the full Solidity
standard-JSON compiler output. Select a contract when the latter contains more
than one:

```bash
slotdiff old-solc.json new-solc.json \
  --old-contract src/Vault.sol:VaultV1 \
  --new-contract src/Vault.sol:VaultV2 \
  --json
```

Request compiler layouts with this standard-JSON output selection:

```json
{"settings":{"outputSelection":{"*":{"*":["storageLayout"]}}}}
```

The compiler [documents the `storage` and `types` JSON fields](https://docs.soliditylang.org/en/latest/internals/layout_in_storage.html),
including slot, byte offset, encoding, and recursive type metadata. It also
marks this JSON output as experimental, so malformed or unfamiliar metadata
returns `UNASSESSED` instead of a green result.

## What is checked

- Slot and byte offset of every existing top-level variable, including packed
  variables.
- Recursive type metadata for mappings, arrays, and struct members.
- Collisions between new variables and bytes occupied by old variables.
- Storage-gap changes and possible renames, surfaced as `REVIEW`.

Variable names are used to match old and new entries. A rename at an identical
position and type is `REVIEW`, because the intent cannot be inferred from
compiler layout alone. Empty and namespaced storage layouts are currently
`UNASSESSED`. For a production upgrade, follow the
[OpenZeppelin upgrade validation guidance](https://docs.openzeppelin.com/upgrades-plugins/writing-upgradeable)
and review the complete contract behavior.

## Development

```bash
python -m unittest discover -s tests -v
python scripts/build_examples.py  # requires solc; regenerates checked-in layouts
```

CI runs the regression suite against checked-in layouts, so contributors do
not need `solc` just to run tests. The fixture source and regeneration script
make the expected compiler output reproducible.

