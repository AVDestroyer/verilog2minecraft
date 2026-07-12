# Minecraft HDL 2 Project Plan

## Summary

This project explores a modern HDL-to-Minecraft-redstone compiler inspired by `itsfrank/MinecraftHDL`, but aimed at a larger feature set, especially synchronous/sequential RTL. The old project proved the basic flow is viable: Verilog -> Yosys JSON -> graph IR -> gate placement -> channel routing -> Minecraft world generation. Its core limitation is structural: it assumes an acyclic combinational graph, so feedback, registers, counters, and FSMs do not fit naturally.

The new project should treat Minecraft redstone as a real backend target with its own timing, placement, routing, version, and verification constraints. Modern update-based redstone techniques from the referenced video may enable compact gates, latches, same-tick computation, and controlled multi-update clocks, but these must be characterized carefully before becoming compiler primitives.

## Required Context For Future Codex Sessions

Before planning or implementing major changes, ingest these sources:

- YouTube video: `https://youtu.be/xyw455piBUE?si=6QFS2r2D6B0acUX5`
  - Title observed: `How 4 blocks revolutionized Computational Redstone`.
  - Fetch the transcript with the YouTube transcript tool when available.
  - Extract the redstone primitive claims: trapdoor/dust T-flip-flop behavior, rail/note-block update shaping, NOT/OR gates, D latch, XOR/OR/NAND/NOR/AND/XNOR examples, same-tick latching, ordered latch networks, update doublers, and controlled multiple updates per tick.
  - Treat the transcript as design input, not proof. Auto-captions and redstone-version behavior must be validated experimentally.

- GitHub repo: `https://github.com/itsfrank/MinecraftHDL`
  - Clone or inspect the repo before changing architecture.
  - Read at minimum: `README.md`, `markdown/GETTING_STARTED.md`, `markdown/SAMPLES.md`, `markdown/BACKGROUND.md`, `markdown/minecrafthdl-digital-synthesis.pdf`.
  - Inspect the implementation packages: `GraphBuilder`, `MinecraftGraph`, `minecrafthdl/synthesis`, and `minecrafthdl/synthesis/routing`.
  - Keep this project independent unless a later decision explicitly chooses to fork or port code.

## Prior Art: MinecraftHDL

Observed architecture:

- Yosys converts Verilog into JSON using `read_verilog`, `hierarchy`, `proc`, `fsm`, `memory`, `techmap`, `opt`, then `json`.
- `GraphBuilder` parses the first JSON module into a custom bidirectional graph.
- Vertices represent inputs, outputs, constants, and function cells.
- Supported function types include `AND`, `OR`, `XOR`, `INV`, `MUX`, `RELAY`, `HIGH`, `LOW`, and a partial `D_LATCH`.
- `IntermediateCircuit` topologically layers the graph from inputs/constants to outputs.
- Edges spanning multiple layers are split with `RELAY` cells.
- Gates are hardcoded Minecraft block-volume macros.
- Routing is done channel-by-channel between adjacent layers using pins, nets, tracks, a vertical constraint graph, and dogleg-style cycle breaking.
- `Circuit` stores a 3D block array and places it into the Minecraft world through Forge.
- The `Synthesizer` block provides the in-game UI and triggers circuit generation.

Important limitations:

- The layering pass requires all predecessors to be placed before a node can be placed, so cyclic/sequential netlists break the model.
- Cell recognition is loose substring matching rather than a formal target-cell mapping.
- Ports, bus bits, control signals, and special cell pins are lightly modeled.
- Routing assumes steady redstone-power wires, not update-event wires.
- Timing is mostly avoided; repeaters are inserted for signal strength, not for a formal clocking model.
- Sequential support is not just adding DFF cells; it changes graph partitioning, timing, placement, and routing.

## New Project Directions

Keep design details open for now, but explore these subsystems:

- HDL frontend: likely Yosys, with an explicit supported RTL subset.
- Compiler IR: typed modules, ports, nets, cells, constants, bit vectors, clocks, resets, enables, and state elements.
- Technology mapping: map Yosys cells into a Minecraft-specific cell library instead of accepting arbitrary JSON cell names.
- Cell library: characterize macro dimensions, pins, orientation, block contents, semantics, update behavior, and constraints.
- Placement: support both combinational DAG regions and stateful boundaries.
- Routing: distinguish signal-value routing from update/clock/latch routing.
- Verification: test netlist behavior before world generation and validate placed circuits against expected cell semantics.

## Major Design Questions

Open questions for later sessions:

- Exact target Minecraft Java Edition version.
- Output format: Fabric/Forge mod, datapack/functions, structure/NBT, schematic, or multiple exporters.
- Backend model: classical redstone, update-event redstone, or hybrid.
- Initial HDL subset: simple synchronous Verilog, resets, enables, memories, latches, FSMs, multi-clock designs.
- Clock semantics: conventional ticks, update-count clocks, same-tick latch waves, or another discipline.
- Routing strategy: adapt MinecraftHDL’s channel router or build a new router around update ordering and 3D macro constraints.
- Verification strategy: Minecraft integration tests, external redstone/update simulator, cell characterization, or combined approach.
- Scale goals: educational circuits, practical redstone CPUs, or compact high-speed update-logic demos.

## Suggested Milestones

1. Reproduce and document old MinecraftHDL behavior.
   - Summarize pipeline and supported cells.
   - Inspect combinational and sequential sample Yosys JSON.
   - Identify exactly where sequential netlists fail.

2. Build a minimal modern compiler skeleton.
   - Parse Yosys JSON into typed IR.
   - Preserve ports, bits, constants, cells, and special pins.
   - Emit clear diagnostics for unsupported constructs.

3. Define a provisional Minecraft cell library format.
   - Represent dimensions, pins, block layout, orientation, semantics, and constraints.
   - Keep it backend-neutral enough for classical or update-based cells.

4. Characterize redstone primitives.
   - Create small reproducible tests for each candidate gate, latch, wire, update generator, and clock primitive.
   - Record version assumptions, update ordering assumptions, and failure modes.
   - Promote primitives only after validation.

5. Implement combinational placement/routing first.
   - Recreate a simple MinecraftHDL-like subset: AND/OR/NOT/XOR/MUX/constants/IO.
   - Use this to validate IR, mapping, macro placement, routing, and export.

6. Add synchronous boundaries.
   - Treat registers/latches as explicit state cells.
   - Separate combinational regions between state elements.
   - Add clock/update routing only after cell behavior is validated.

7. Expand examples.
   - Start with muxes, adders, and 7-seg decoders.
   - Then counters, FSMs, register files, and a tiny ALU.
   - Eventually attempt a minimal CPU-style design if scale permits.

## Risks And Watchpoints

- Minecraft update behavior may be version-specific or patched.
- Same-tick/update-event logic may be hard to reason about without a simulator.
- Generated circuits may become too large without careful macro and routing choices.
- Yosys may emit cells that need normalization before mapping.
- Multi-bit buses and memories need deliberate handling.
- A useful tool needs excellent diagnostics for unsupported HDL constructs.
- Redstone primitive claims from videos must be reproduced, not assumed.

## Working Assumptions For Now

- Use Yosys as the HDL frontend unless later investigation finds a better choice.
- Treat MinecraftHDL as architectural prior art, not code to directly extend.
- Start with a small, well-tested synchronous subset rather than arbitrary Verilog.
- Keep redstone primitive selection open until experiments confirm behavior.
- Prefer reproducible exports and tests over an in-game-only workflow.
