"""Storage layout comparison for the Solidity compiler's JSON output.

The tool checks slot geometry and recursive type metadata. It deliberately
does not claim to validate initializer, proxy, ABI, or permission safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LayoutError(ValueError):
    """Input lacks the metadata needed for a reliable comparison."""


@dataclass(frozen=True)
class Variable:
    label: str
    slot: int
    offset: int
    size: int
    signature: tuple[Any, ...]

    @property
    def start(self) -> int:
        return self.slot * 32 + self.offset

    @property
    def end(self) -> int:
        return self.start + self.size

    @property
    def gap(self) -> bool:
        return self.label == "__gap" or self.label.startswith("__gap_")


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LayoutError(f"{field} must be a non-negative integer")
    try:
        result = int(value, 10) if isinstance(value, str) else value
    except ValueError as exc:
        raise LayoutError(f"{field} must be a non-negative integer") from exc
    if result < 0:
        raise LayoutError(f"{field} must be a non-negative integer")
    return result


def load_layout(document: Any, selector: str | None = None) -> dict[str, Any]:
    """Accept raw storageLayout or solc standard-JSON output."""
    if not isinstance(document, dict):
        raise LayoutError("JSON root must be an object")
    if "storage" in document and "types" in document:
        if selector is not None:
            raise LayoutError("--contract is only for standard-JSON compiler output")
        return document
    contracts = document.get("contracts")
    if not isinstance(contracts, dict):
        raise LayoutError("Expected storageLayout or solc standard-JSON contracts")
    choices: dict[str, dict[str, Any]] = {}
    for source, names in contracts.items():
        if not isinstance(names, dict):
            continue
        for name, artifact in names.items():
            if isinstance(artifact, dict) and isinstance(artifact.get("storageLayout"), dict):
                choices[f"{source}:{name}"] = artifact["storageLayout"]
    if selector is None:
        if len(choices) != 1:
            raise LayoutError("Select one contract with --contract SOURCE:NAME")
        return next(iter(choices.values()))
    if selector not in choices:
        raise LayoutError(f"Contract {selector!r} has no storageLayout")
    return choices[selector]


def _signature(type_id: str, types: dict[str, Any], visiting: set[str]) -> tuple[Any, ...]:
    if type_id in visiting:
        raise LayoutError("Recursive type metadata")
    item = types.get(type_id)
    if not isinstance(item, dict):
        raise LayoutError(f"Missing type metadata: {type_id}")
    encoding = item.get("encoding")
    label = item.get("label")
    if not isinstance(encoding, str) or not isinstance(label, str):
        raise LayoutError(f"Malformed type metadata: {type_id}")
    if encoding not in {"inplace", "mapping", "dynamic_array", "bytes"}:
        raise LayoutError(f"Unsupported storage encoding: {encoding}")
    if encoding == "mapping" and not all(isinstance(item.get(key), str)
                                          for key in ("key", "value")):
        raise LayoutError("Mapping lacks key or value type")
    if encoding == "dynamic_array" and not isinstance(item.get("base"), str):
        raise LayoutError("Dynamic array lacks base type")
    if encoding == "inplace" and (label.startswith("struct ") or "[" in label) and not (
            isinstance(item.get("base"), str) or isinstance(item.get("members"), list)):
        raise LayoutError("Struct or fixed array lacks child type metadata")
    size = _integer(item.get("numberOfBytes"), "numberOfBytes")
    if size == 0:
        raise LayoutError("Zero-byte storage type")
    visiting = visiting | {type_id}
    children = []
    for field in ("key", "value", "base"):
        child = item.get(field)
        if child is not None:
            if not isinstance(child, str):
                raise LayoutError(f"Malformed {field} type")
            children.append((field, _signature(child, types, visiting)))
    members = item.get("members", [])
    if not isinstance(members, list):
        raise LayoutError("Malformed struct members")
    for member in members:
        if not isinstance(member, dict) or not isinstance(member.get("type"), str):
            raise LayoutError("Malformed struct member")
        if not isinstance(member.get("label"), str):
            raise LayoutError("Struct member lacks a label")
        slot = _integer(member.get("slot"), "member slot")
        offset = _integer(member.get("offset"), "member offset")
        if offset >= 32:
            raise LayoutError("Struct member offset exceeds slot")
        children.append(("member", member["label"], slot, offset,
                         _signature(member["type"], types, visiting)))
    return (encoding, label, size, tuple(children))


def _variables(layout: dict[str, Any]) -> list[Variable]:
    storage, types = layout.get("storage"), layout.get("types")
    if not isinstance(storage, list) or not isinstance(types, dict) or not storage:
        raise LayoutError("Non-empty storage and types are required; empty or namespaced layouts need manual review")
    result = []
    labels: set[str] = set()
    for entry in storage:
        if not isinstance(entry, dict) or not isinstance(entry.get("label"), str):
            raise LayoutError("Malformed storage entry")
        label, type_id = entry["label"], entry.get("type")
        if not isinstance(type_id, str) or label in labels:
            raise LayoutError("Missing type or duplicate variable label")
        labels.add(label)
        slot = _integer(entry.get("slot"), "slot")
        offset = _integer(entry.get("offset"), "offset")
        if offset >= 32:
            raise LayoutError("Offset exceeds slot")
        signature = _signature(type_id, types, set())
        size = signature[2]
        if offset + size > 32 and offset != 0:
            raise LayoutError("Multi-slot value has a nonzero offset")
        result.append(Variable(label, slot, offset, size, signature))
    ordered = sorted(result, key=lambda variable: variable.start)
    for left, right in zip(ordered, ordered[1:]):
        if left.end > right.start:
            raise LayoutError("Overlapping variables in one compiler layout")
    return result


def _issue(code: str, severity: str, label: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "variable": label, "detail": detail}


def compare_layouts(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Conservatively assess top-level storage variables and nested types."""
    before = _variables(old)
    after = _variables(new)
    old_by_name = {item.label: item for item in before}
    new_by_name = {item.label: item for item in after}
    issues: list[dict[str, str]] = []
    renamed: set[str] = set()
    for item in before:
        replacement = new_by_name.get(item.label)
        if item.gap:
            if replacement is None or (item.start, item.size) != (replacement.start, replacement.size):
                issues.append(_issue("STORAGE_GAP_CHANGE", "REVIEW", item.label,
                                     "Reserved gap changed; validate its accounting with an upgrade-aware checker"))
            continue
        if replacement is None:
            candidate = next((entry for entry in after
                              if entry.label not in old_by_name and entry.label not in renamed
                              and (entry.start, entry.signature) == (item.start, item.signature)), None)
            if candidate:
                renamed.add(candidate.label)
                issues.append(_issue("POSSIBLE_RENAME", "REVIEW", item.label,
                                     f"Same type and position now named {candidate.label}"))
            else:
                issues.append(_issue("REMOVED_VARIABLE", "FAIL", item.label,
                                     "Existing storage variable is absent"))
        elif item.start != replacement.start:
            issues.append(_issue("MOVED_VARIABLE", "FAIL", item.label,
                                 f"Byte position changed from {item.start} to {replacement.start}"))
        elif item.signature != replacement.signature:
            issues.append(_issue("TYPE_CHANGED", "FAIL", item.label,
                                 "Storage type or nested members changed"))
    old_end = max(item.end for item in before)
    for item in after:
        if item.label in old_by_name or item.label in renamed or item.gap:
            continue
        collisions = [existing for existing in before
                      if item.start < existing.end and existing.start < item.end]
        if any(not existing.gap for existing in collisions):
            issues.append(_issue("OCCUPIED_BYTES", "FAIL", item.label,
                                 "New variable overlaps previously occupied storage"))
        elif collisions:
            issues.append(_issue("USES_STORAGE_GAP", "REVIEW", item.label,
                                 "New variable consumes reserved gap bytes"))
        elif item.start < old_end:
            issues.append(_issue("INSERTED_IN_HOLE", "REVIEW", item.label,
                                 "New variable uses an earlier unoccupied byte range"))
    status = ("FAIL" if any(issue["severity"] == "FAIL" for issue in issues) else
              "REVIEW" if issues else "PASS")
    return {"status": status, "old_variables": len(before),
            "new_variables": len(after), "issues": issues}
