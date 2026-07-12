"""End-to-end and unit tests for the sequential-aware graph IR."""

from __future__ import annotations

import unittest

from compiler.graph import CombCycleError, parse_yosys_json_file
from tests.helpers import synth


class TestExampleGraphs(unittest.TestCase):
    def test_and2_is_simple_comb_dag(self) -> None:
        path = synth("and2.v", "and2")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(g.name, "and2")
        self.assertEqual([p.name for p in g.primary_inputs], ["a", "b"])
        self.assertEqual([p.name for p in g.primary_outputs], ["y"])
        self.assertEqual(len(g.comb_cells), 1)
        self.assertEqual(g.comb_cells[0].yosys_type, "$_AND_")
        self.assertEqual(g.state_cells, [])
        self.assertEqual(g.control_edges, [])
        self.assertFalse(g.has_comb_cycle())
        layers = g.topo_layers()
        self.assertGreaterEqual(len(layers), 2)
        self.assertIn("a", layers[0])
        self.assertIn("b", layers[0])

    def test_mux2_emits_mux_cell(self) -> None:
        path = synth("mux2.v", "mux2")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual([c.yosys_type for c in g.comb_cells], ["$_MUX_"])
        self.assertEqual(len(g.data_edges), 4)

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
        self.assertTrue({"$_AND_", "$_XOR_"}.issubset(types))
        # Each bit of sum should be driven somehow into the output port.
        sum_bits = {e.dst.bit for e in g.data_edges if e.dst.node == "sum"}
        self.assertEqual(sum_bits, {0, 1, 2, 3})

    def test_minimal_toggle_splits_state_boundary(self) -> None:
        path = synth("minimal_toggle.v", "minimal_toggle")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(len(g.state_cells), 1)
        self.assertEqual(g.state_cells[0].yosys_type, "$_SDFF_PP0_")
        roles = {e.role for e in g.control_edges}
        self.assertEqual(roles, {"clock", "reset"})
        self.assertFalse(g.has_comb_cycle())
        # Feedback is Q -> NOT -> D, not a comb cycle through the flop.
        q_sources = [e for e in g.data_edges if e.src.port == "Q"]
        d_sinks = [e for e in g.data_edges if e.dst.port == "D"]
        self.assertTrue(q_sources)
        self.assertTrue(d_sinks)

    def test_counter4_multibit_state(self) -> None:
        path = synth("counter4.v", "counter4")
        g = parse_yosys_json_file(path)
        g.validate()
        self.assertEqual(len(g.state_cells), 4)
        self.assertTrue(all(c.yosys_type == "$_SDFF_PP0_" for c in g.state_cells))
        q = next(p for p in g.primary_outputs if p.name == "q")
        self.assertEqual(q.width, 4)
        clocks = [e for e in g.control_edges if e.role == "clock"]
        resets = [e for e in g.control_edges if e.role == "reset"]
        self.assertEqual(len(clocks), 4)
        self.assertEqual(len(resets), 4)
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


class TestIrHelpers(unittest.TestCase):
    def test_unsupported_cell_raises(self) -> None:
        from compiler.graph.cells import classify_cell

        with self.assertRaises(ValueError):
            classify_cell("$_DFF_PP0_")  # async-reset variant not in allowlist yet


if __name__ == "__main__":
    unittest.main()
