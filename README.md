# verilog2redstone

Compile a subset of Verilog into Minecraft redstone circuits, with real support for synchronous / sequential RTL.

Inspired by [itsfrank/MinecraftHDL](https://github.com/itsfrank/MinecraftHDL), but not a fork. MinecraftHDL’s pipeline (Verilog → Yosys JSON → graph → placement → routing → world) works for combinational logic; it breaks on registers and feedback because it treats the netlist as a single acyclic combinational DAG. This project aims to fix that by treating flip-flops as state boundaries and modeling clock/reset as control, not data.

Longer design notes live in [`plan.md`](plan.md).

## Status

Done so far:

1. **Yosys frontend script** — `read_verilog` → `hierarchy` → `proc` / `fsm` / `memory` → `techmap` → JSON, parameterized by file / top module / output path.
2. **Sequential-aware graph IR** — parse Yosys JSON into primary I/O, combinational cells, state cells, **data edges**, and **control edges**. Feedback through a flop is not treated as a combinational cycle.
3. **Examples + tests** — comb (`and2`, `mux2`), multi-bit (`adder4`), sequential (`minimal_toggle`, `counter4`), and a rejecting comb-loop case (`comb_loop`). Combinational loops are not allowed.

Not done yet: cell library / redstone macros, placement, routing, Minecraft export, or primitive characterization from update-based redstone techniques.

## Requirements

- [Yosys](https://yosyshq.net/yosys/) (tested with 0.33)
- Python 3.10+ (stdlib only for the graph frontend)

## Quick start

```bash
# Verilog → Yosys JSON (writes examples/build/<name>.json)
./scripts/synth.sh examples/minimal_toggle.v minimal_toggle

# Yosys JSON → sequential-aware graph summary
python3 -m compiler.graph examples/build/minimal_toggle.json

# Fail on combinational loops (default)
python3 -m compiler.graph examples/build/comb_loop.json

# Optional: dump the graph as JSON
python3 -m compiler.graph examples/build/minimal_toggle.json \
  --json-out examples/build/minimal_toggle.graph.json

# Run tests (synth + parse assertions; requires yosys)
python3 -m unittest discover -s tests -v
```

`examples/build/` is gitignored.

### Synth script

```bash
./scripts/synth.sh <verilog_file> [top_module] [output_json]
```

Defaults to `examples/build/<verilog_basename>.json`. The Yosys template is [`scripts/to_json.ys`](scripts/to_json.ys).

## Repository layout

```
compiler/
  graph/           # Yosys JSON → ModuleGraph IR
    cells.py       # Supported Yosys $_…_ cell allowlist + port roles
    ir.py          # Graph datatypes, cycle check, topo layers
    parse.py       # JSON parser
scripts/
  synth.sh         # Parameterized Yosys driver
  to_json.ys       # Yosys script template
examples/
  and2.v           # Pure combinational
  mux2.v
  adder4.v         # Multi-bit comb
  minimal_toggle.v # 1-bit sync-reset flop
  counter4.v       # Multi-bit sequential
  comb_loop.v      # Cross-coupled NOR latch (expected cycle)
  build/           # Generated JSON (ignored)
tests/
  test_graph_examples.py
plan.md            # Longer architecture / milestone plan
```

## Examples

| Example | What it stresses |
|---------|------------------|
| `and2` / `mux2` | Single-gate comb DAGs |
| `adder4` | Multi-bit ports, larger comb cloud |
| `minimal_toggle` | State boundary + feedback through `NOT` |
| `counter4` | 4× `$_SDFF_PP0_` + next-state XOR/AND logic |
| `comb_loop` | True comb cycle (SR latch); **rejected** by default |
## Graph model

The frontend builds a sequential-aware graph:

| Concept | Role |
|---------|------|
| Combinational cells | Boolean / MUX gates (`$_NOT_`, `$_AND_`, …) |
| State cells | Flops / latches (`$_SDFF_PP0_`, `$_DFF_P_`, …) |
| Data edges | Value flow for placement layering (`Q → NOT → D`, outputs) |
| Control edges | Clock / reset / enable into state cells (not used for topo sort) |

State cells are split at the register boundary for DAG analysis: `Q` is a source into combinational logic, `D` is a sink from it. The recurrence `Q(t+1) = f(Q(t))` lives in the state element + clock, not in the combinational graph.

**Combinational loops are unsupported.** Parsing rejects them by default (`CombCycleError`). Register feedback is fine; cross-coupled gates / `assign a = ~a`-style loops are not.

For `minimal_toggle`, the parsed result is roughly:

```
control:  clk → SDFF.C ,  rst → SDFF.R
data:     SDFF.Q → NOT.A → NOT.Y → SDFF.D
          SDFF.Q → q
layers:   [SDFF.Q] → [NOT, q] → [SDFF.D]
```

## Supported Yosys cells

Only an explicit allowlist in [`compiler/graph/cells.py`](compiler/graph/cells.py) is accepted. Types come from Yosys’s post-`techmap` gate library (`$_…_` cells in `simcells.v`), not substring matching.

Unsupported cells fail with a clear error. That is intentional: better to reject `$add` or an exotic flop than mis-map it.

## Cell support as a project goal

We will support **more** cell types over time, but **not** “every Yosys cell.”

- **Grow the allowlist** when real examples need a new gate or flop, with correct port roles (data vs control).
- **Goal worth having:** a documented, tested subset of Yosys cells that map cleanly onto Minecraft cell-library macros.
- **Goal not worth having:** full Yosys / full Verilog. Arithmetic, memories, and exotic sequential cells should either be lowered by Yosys into supported gates, or rejected with a good diagnostic.

The hard product work is Minecraft primitives, timing, placement, and routing — not collecting cell names.

## Next milestones

See [`plan.md`](plan.md). Short version:

1. Define a Minecraft cell library format (geometry, pins, semantics).
2. Characterize redstone gates / latches / clocks experimentally.
3. Combinational place-and-route, then synchronous boundaries.
