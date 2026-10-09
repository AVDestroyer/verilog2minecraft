# verilog2redstone

Compile a subset of Verilog into Minecraft redstone circuits, with real support for synchronous / sequential RTL.

Inspired by [itsfrank/MinecraftHDL](https://github.com/itsfrank/MinecraftHDL), but not a fork. MinecraftHDL’s pipeline (Verilog → Yosys JSON → graph → placement → routing → world) works for combinational logic; it breaks on registers and feedback because it treats the netlist as a single acyclic combinational DAG. This project aims to fix that by treating registers as state boundaries, keeping the clock separate from data flow, and lowering synchronous reset into next-state logic.

Longer design notes live in [`plan.md`](plan.md). The focused implementation
roadmap for the cell library, placement, routing, and routed-depth analysis is in
[`NEXT_STEPS.md`](NEXT_STEPS.md).

## Status

Done so far:

1. **Yosys frontend script** — lowers RTL and uses ABC to map combinational logic exclusively to `NOT`, `AND`, `OR`, `XOR`, `XNOR`, `NAND`, and `NOR`.
2. **Sequential-aware graph IR** — parses primary I/O, combinational cells, positive-edge logical `REGISTER` cells, **data edges**, and clock **control edges**. Feedback through a register is not treated as a combinational cycle.
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
  level_latch.v    # Unsupported level-sensitive latch (expected rejection)
  build/           # Generated JSON (ignored)
tests/
  test_graph_examples.py
plan.md            # Longer architecture / milestone plan
```

## Examples

| Example | What it stresses |
|---------|------------------|
| `and2` / `mux2` | Basic logic and decomposition into target gates |
| `adder4` | Multi-bit ports, larger comb cloud |
| `minimal_toggle` | State boundary + reset/feedback logic |
| `counter4` | 4× logical `REGISTER` + next-state logic |
| `comb_loop` | True comb cycle (SR latch); **rejected** by default |
| `level_latch` | Unsupported level-sensitive storage; **rejected** during synthesis |

## Graph model

The frontend builds a sequential-aware graph:

| Concept | Role |
|---------|------|
| Combinational cells | `NOT`, `AND`, `OR`, `XOR`, `XNOR`, `NAND`, and `NOR` |
| State cells | Positive-edge logical `REGISTER` (`$_DFF_P_`) |
| Data edges | Value flow for placement layering (`Q → NOT → D`, outputs) |
| Control edges | Clock attachment to registers (not used for topo sort) |

State cells are split at the register boundary for DAG analysis: `Q` is a source into combinational logic, `D` is a sink from it. The recurrence `Q(t+1) = f(Q(t))` lives in the state element + clock, not in the combinational graph.

**Combinational loops are unsupported.** Parsing rejects them by default (`CombCycleError`). Register feedback is fine; cross-coupled gates / `assign a = ~a`-style loops are not.

For `minimal_toggle`, the parsed result is roughly:

```
control:  clk → REGISTER.C
data:     (REGISTER.Q, rst) → next-state/reset logic → REGISTER.D
          REGISTER.Q → q
```

## Supported Yosys cells

Only an explicit allowlist in [`compiler/graph/cells.py`](compiler/graph/cells.py) is accepted. ABC maps combinational logic to `$_NOT_`, `$_AND_`, `$_OR_`, `$_XOR_`, `$_XNOR_`, `$_NAND_`, and `$_NOR_`. The only accepted sequential cell is `$_DFF_P_`, represented in the graph as a positive-edge logical `REGISTER`.

Before ABC mapping, `dffunmap` lowers synchronous reset and enable behavior into combinational logic on the register's `D` input. `dfflegalize` then realizes supported sequential behavior using positive-edge DFFs, adding combinational inversion when appropriate. Sequential behavior that cannot be expressed using the target DFF, such as a level-sensitive latch, is rejected.

Unsupported cells fail with a clear error. That is intentional: better to reject `$add` or an exotic flop than mis-map it.

## Cell support as a project goal

We will support **more** cell types over time, but **not** “every Yosys cell.”

- **Grow the physical library** only when a new primitive offers a measured advantage over the target gate basis.
- **Goal worth having:** a documented, tested target cell set that maps cleanly onto Minecraft macros.
- **Goal not worth having:** full Yosys / full Verilog. Arithmetic, memories, and exotic sequential cells should either be lowered by Yosys into supported gates, or rejected with a good diagnostic.

The hard product work is Minecraft primitives, timing, placement, and routing — not collecting cell names.

## Next milestones

See [`plan.md`](plan.md). Short version:

1. Define a Minecraft cell library format (geometry, pins, semantics).
2. Characterize redstone gates / latches / clocks experimentally.
3. Combinational place-and-route, then synchronous boundaries.
