"""End-to-end and unit tests for the sequential-aware graph IR."""

from __future__ import annotations

import subprocess
import unittest

from compiler.graph import CombCycleError, parse_yosys_json, parse_yosys_json_file
from compiler.graph.cells import (
    COMB_CELLS,
    LOGICAL_REGISTER,
    REGISTER_YOSYS_TYPE,
)
from tests.helpers import synth


class TestExampleGraphs(unittest.TestCase):
    def test_and2_is_mapped_to_v1_gates(self) -> None:
        path = synth("and2.v", "and2")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(g.name, "and2")
        self.assertEqual([p.name for p in g.primary_inputs], ["a", "b"])
        self.assertEqual([p.name for p in g.primary_outputs], ["y"])
        self.assertGreaterEqual(len(g.comb_cells), 1)
        self.assertTrue(
            {cell.yosys_type for cell in g.comb_cells}.issubset(COMB_CELLS)
        )
        self.assertEqual(g.state_cells, [])
        self.assertEqual(g.control_edges, [])
        self.assertFalse(g.has_comb_cycle())
        layers = g.topo_layers()
        self.assertGreaterEqual(len(layers), 2)
        self.assertIn("a", layers[0])
        self.assertIn("b", layers[0])

    def test_mux2_maps_to_target_gates(self) -> None:
        path = synth("mux2.v", "mux2")
        g = parse_yosys_json_file(path)
        g.validate()
        types = {c.yosys_type for c in g.comb_cells}
        self.assertTrue(types)
        self.assertTrue(types.issubset(COMB_CELLS))
        self.assertNotIn("$_MUX_", types)

    def test_adder4_multibit_ports(self) -> None:
        path = synth("adder4.v", "adder4")
        g = parse_yosys_json_file(path)
        g.validate()
        ports = {p.name: p for p in g.primary_inputs + g.primary_outputs}
        self.assertEqual(ports["a"].width, 4)
        self.assertEqual(ports["b"].width, 4)
        self.assertEqual(ports["sum"].width, 4)
        self.assertEqual(ports["cout"].width, 1)
        self.assertEqual(g.state_cells, [])
        self.assertGreater(len(g.comb_cells), 1)
        types = {c.yosys_type for c in g.comb_cells}
        self.assertTrue(types.issubset(COMB_CELLS))
        # Each bit of sum should be driven somehow into the output port.
        sum_bits = {e.dst.bit for e in g.data_edges if e.dst.node == "sum"}
        self.assertEqual(sum_bits, {0, 1, 2, 3})

    def test_minimal_toggle_splits_state_boundary(self) -> None:
        path = synth("minimal_toggle.v", "minimal_toggle")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(len(g.state_cells), 1)
        self.assertEqual(g.state_cells[0].yosys_type, REGISTER_YOSYS_TYPE)
        self.assertEqual(g.state_cells[0].logical_type, LOGICAL_REGISTER)
        self.assertEqual(g.state_cells[0].clock_edge, "positive")
        serialized = g.to_dict()["state_cells"][0]
        self.assertEqual(serialized["logical_type"], LOGICAL_REGISTER)
        self.assertEqual(serialized["clock_edge"], "positive")
        roles = {e.role for e in g.control_edges}
        self.assertEqual(roles, {"clock"})
        self.assertFalse(g.has_comb_cycle())
        # Reset has been lowered into the D logic. Feedback still crosses the
        # Q/D register boundary instead of becoming a combinational cycle.
        q_sources = [e for e in g.data_edges if e.src.port == "Q"]
        d_sinks = [e for e in g.data_edges if e.dst.port == "D"]
        self.assertTrue(q_sources)
        self.assertTrue(d_sinks)

    def test_counter4_multibit_state(self) -> None:
        path = synth("counter4.v", "counter4")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(len(g.state_cells), 4)
        self.assertTrue(
            all(c.yosys_type == REGISTER_YOSYS_TYPE for c in g.state_cells)
        )
        self.assertTrue(
            all(c.logical_type == LOGICAL_REGISTER for c in g.state_cells)
        )
        q = next(p for p in g.primary_outputs if p.name == "q")
        self.assertEqual(q.width, 4)
        clocks = [e for e in g.control_edges if e.role == "clock"]
        resets = [e for e in g.control_edges if e.role == "reset"]
        self.assertEqual(len(clocks), 4)
        self.assertEqual(resets, [])
        self.assertFalse(g.has_comb_cycle())
        layers = g.topo_layers()
        # All Q pins should be sources in the first layer.
        first = set(layers[0])
        for cell in g.state_cells:
            self.assertIn(f"{cell.name}.Q", first)

    def test_comb_loop_is_rejected(self) -> None:
        path = synth("comb_loop.v", "comb_loop")
        with self.assertRaises(CombCycleError) as ctx:
            parse_yosys_json_file(path)
        self.assertIn("cycle", str(ctx.exception).lower())

        # Debug path: parsing without the acyclicity check still sees the cycle.
        g = parse_yosys_json_file(path, require_acyclic=False)
        self.assertTrue(g.has_comb_cycle())
        cycle = g.find_comb_cycle()
        self.assertIsNotNone(cycle)
        assert cycle is not None
        self.assertGreaterEqual(len(cycle), 3)

    def test_level_latch_cannot_be_legalized_to_target_dff(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            synth("level_latch.v", "level_latch")


class TestIrHelpers(unittest.TestCase):
    def test_target_cell_allowlist_is_exact(self) -> None:
        self.assertEqual(
            COMB_CELLS,
            {
                "$_NOT_",
                "$_NAND_",
                "$_OR_",
            },
        )

    def test_other_combinational_cells_are_rejected(self) -> None:
        from compiler.graph.cells import classify_cell

        for cell_type in ("$_AND_", "$_NOR_", "$_XOR_", "$_XNOR_"):
            with self.subTest(cell_type=cell_type):
                with self.assertRaisesRegex(ValueError, "unsupported Yosys cell"):
                    classify_cell(cell_type)

    def test_unsupported_sequential_cells_raise(self) -> None:
        from compiler.graph.cells import classify_cell

        for cell_type in ("$_DFF_N_", "$_SDFF_PP0_", "$_DLATCH_P_"):
            with self.subTest(cell_type=cell_type):
                with self.assertRaisesRegex(ValueError, "unsupported sequential"):
                    classify_cell(cell_type)

    def test_parser_names_rejected_sequential_cell(self) -> None:
        data = {
            "modules": {
                "top": {
                    "cells": {
                        "bad_latch": {
                            "type": "$_DLATCH_P_",
                            "port_directions": {},
                            "connections": {},
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(
            ValueError, "cell bad_latch: unsupported sequential"
        ):
            parse_yosys_json(data)


if __name__ == "__main__":
    unittest.main()
