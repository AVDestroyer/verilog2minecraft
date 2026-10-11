"""Tests for physical-cell metadata and Litematica header validation."""

from __future__ import annotations

from pathlib import Path
import unittest

from compiler.cell_library import load_cell_library
from compiler.cell_library.litematic import read_litematic_summary
from compiler.graph.cells import COMB_CELLS


REPO_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = REPO_ROOT / "litematica-cells"


class TestCellLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.library = load_cell_library(LIBRARY_ROOT)

    def test_active_library_exactly_covers_v1_combinational_cells(self) -> None:
        self.assertEqual(
            self.library.coordinate_space, "cell_local"
        )
        self.assertEqual(
            {cell.logical_type for cell in self.library.cells}, COMB_CELLS
        )

    def test_combinational_cells_share_orientation_convention(self) -> None:
        self.assertEqual(
            {cell.orientation.family for cell in self.library.cells},
            {"v1_comb_canonical_x"},
        )
        for cell in self.library.cells:
            self.assertEqual(cell.orientation.origin_name, "bottom_left")
            self.assertEqual(cell.orientation.origin, (0, 0, 0))
            self.assertEqual(cell.orientation.logic_flow, "+x")
            self.assertEqual(
                cell.orientation.minecraft_axis_directions, (-1, 1, -1)
            )
            self.assertEqual(cell.orientation.allowed_y_rotations, (0,))
            self.assertFalse(cell.orientation.allow_mirror)

    def test_pin_shapes_match_logical_cells(self) -> None:
        expected = {
            "$_NOT_": ({"A": (0, 1, 0)}, {"Y": (4, 1, 0)}),
            "$_OR_": (
                {"A": (0, 1, 2), "B": (0, 4, 1)},
                {"Y": (6, 1, 2)},
            ),
            "$_NAND_": (
                {"A": (0, 2, 1), "B": (5, 5, 1)},
                {"Y": (12, 1, 1)},
            ),
        }
        for cell in self.library.cells:
            with self.subTest(cell=cell.logical_type):
                expected_inputs, expected_outputs = expected[cell.logical_type]
                self.assertEqual(
                    {pin.name: pin.position for pin in cell.inputs},
                    expected_inputs,
                )
                self.assertEqual(
                    {pin.name: pin.position for pin in cell.outputs},
                    expected_outputs,
                )

    def test_cell_coordinates_map_independently_of_selection_order(self) -> None:
        nand = self.library.by_logical_type("$_NAND_")
        self.assertEqual(nand.cell_to_region_array((0, 2, 1)), (12, 2, 3))
        self.assertEqual(nand.cell_to_region_array((12, 1, 1)), (0, 1, 3))

        or_cell = self.library.by_logical_type("$_OR_")
        self.assertEqual(or_cell.cell_to_region_array((0, 1, 2)), (6, 1, 2))
        self.assertEqual(or_cell.cell_to_region_array((6, 1, 2)), (0, 1, 2))

        for cell in self.library.cells:
            with self.subTest(cell=cell.cell_id):
                self.assertEqual(cell.schematic.region_minimum, (0, 0, 0))

    def test_canonical_axes_match_minecraft_axes_for_every_cell(self) -> None:
        expected_steps = {
            (1, 0, 0): (-1, 0, 0),
            (0, 1, 0): (0, 1, 0),
            (0, 0, 1): (0, 0, -1),
        }
        for cell in self.library.cells:
            with self.subTest(cell=cell.cell_id):
                origin = cell.cell_to_schematic((0, 0, 0))
                for local_step, expected_world_step in expected_steps.items():
                    adjacent = cell.cell_to_schematic(local_step)
                    actual_world_step = tuple(
                        adjacent[index] - origin[index] for index in range(3)
                    )
                    self.assertEqual(actual_world_step, expected_world_step)

    def test_litematic_headers_match_metadata(self) -> None:
        for cell in self.library.cells:
            with self.subTest(cell=cell.cell_id):
                summary = read_litematic_summary(cell.schematic.path)
                region = next(r for r in summary.regions if r.name == cell.schematic.region)
                self.assertEqual(region.dimensions, cell.schematic.dimensions)
                self.assertEqual(region.position, cell.schematic.region_position)
                self.assertEqual(
                    region.signed_size, cell.schematic.region_signed_size
                )

    def test_d_latch_is_deferred(self) -> None:
        self.assertEqual(len(self.library.deferred_assets), 1)
        self.assertEqual(
            self.library.deferred_assets[0].name,
            "cell.litematic",
        )
        self.assertNotIn(
            "D_LATCH", {cell.logical_type for cell in self.library.cells}
        )

    def test_lookup_bridges_logical_and_physical_cells(self) -> None:
        nand = self.library.by_logical_type("$_NAND_")
        self.assertEqual(nand.cell_id, "nand_v1")
        self.assertEqual(nand.schematic.region, "NAND")


if __name__ == "__main__":
    unittest.main()
