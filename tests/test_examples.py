"""Regression cases compiled from the Solidity source in examples/contracts."""

import json
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from slotdiff.core import LayoutError, compare_layouts, load_layout
from slotdiff.cli import main


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ROOT / "examples/layouts"


def layout(name: str) -> dict:
    return json.loads((LAYOUTS / f"{name}.json").read_text(encoding="utf-8"))


class CompiledLayoutTests(unittest.TestCase):
    def test_append_after_mapping_is_safe(self):
        report = compare_layouts(layout("VaultV1"), layout("VaultV2Append"))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["issues"], [])

    def test_reordering_packed_variables_fails(self):
        report = compare_layouts(layout("VaultV1"), layout("VaultV2Reordered"))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual({issue["code"] for issue in report["issues"]}, {"MOVED_VARIABLE"})

    def test_mapping_value_type_change_fails(self):
        report = compare_layouts(layout("VaultV1"), layout("VaultV2MappingType"))
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(issue["code"] == "TYPE_CHANGED" and issue["variable"] == "balance"
                            for issue in report["issues"]))

    def test_nested_struct_member_change_fails(self):
        report = compare_layouts(layout("PositionV1"), layout("PositionV2Changed"))
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(issue["code"] == "TYPE_CHANGED" for issue in report["issues"]))

    def test_gap_consumption_requires_review(self):
        report = compare_layouts(layout("GapV1"), layout("GapV2"))
        self.assertEqual(report["status"], "REVIEW")
        self.assertEqual({issue["code"] for issue in report["issues"]},
                         {"STORAGE_GAP_CHANGE", "USES_STORAGE_GAP"})

    def test_missing_type_metadata_never_passes(self):
        broken = layout("VaultV1")
        broken["types"] = {}
        with self.assertRaises(LayoutError):
            compare_layouts(broken, layout("VaultV2Append"))

    def test_cli_exit_codes(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(LAYOUTS / "VaultV1.json"),
                                   str(LAYOUTS / "VaultV2Append.json"), "--json"]), 0)
            self.assertEqual(main([str(LAYOUTS / "VaultV1.json"),
                                   str(LAYOUTS / "VaultV2Reordered.json"), "--json"]), 2)

    def test_standard_json_contract_selection(self):
        document = {"contracts": {"VaultVariants.sol": {
            "VaultV1": {"storageLayout": layout("VaultV1")},
            "VaultV2Append": {"storageLayout": layout("VaultV2Append")},
        }}}
        self.assertEqual(load_layout(document, "VaultVariants.sol:VaultV1"), layout("VaultV1"))
        with self.assertRaises(LayoutError):
            load_layout(document)


if __name__ == "__main__":
    unittest.main()
