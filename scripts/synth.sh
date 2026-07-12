#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: ./scripts/synth.sh <verilog_file> [top_module] [output_json]

Arguments:
  verilog_file   Path to the Verilog/SystemVerilog source file.
  top_module     Optional top-level module name. If omitted, Yosys picks
                 the default top module after hierarchy -check.
  output_json    Optional output path. Defaults to
                 examples/build/<verilog_basename>.json

Examples:
  ./scripts/synth.sh examples/minimal_toggle.v
  ./scripts/synth.sh examples/minimal_toggle.v minimal_toggle
  ./scripts/synth.sh examples/minimal_toggle.v minimal_toggle examples/build/minimal_toggle.json
EOF
    exit 1
}

[[ $# -ge 1 ]] || usage

verilog_file="$1"
top_module="${2:-}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
verilog_basename="$(basename "${verilog_file%.v}")"
default_output_json="${repo_root}/examples/build/${verilog_basename}.json"
output_json="${3:-${default_output_json}}"

if [[ ! -f "$verilog_file" ]]; then
    echo "error: verilog file not found: $verilog_file" >&2
    exit 1
fi

template="${script_dir}/to_json.ys"
generated="$(mktemp "${TMPDIR:-/tmp}/verilog2redstone_synth.XXXXXX.ys")"

top_directive=""
if [[ -n "$top_module" ]]; then
    top_directive=" -top ${top_module}"
fi

# Resolve paths relative to the current working directory, not the repo root.
verilog_abs="$(cd "$(dirname "$verilog_file")" && pwd)/$(basename "$verilog_file")"
output_abs="$(mkdir -p "$(dirname "$output_json")" 2>/dev/null; cd "$(dirname "$output_json")" && pwd)/$(basename "$output_json")"

sed \
    -e "s|@VERILOG_FILE@|${verilog_abs}|g" \
    -e "s|@TOP_MODULE_DIRECTIVE@|${top_directive}|g" \
    -e "s|@OUTPUT_JSON@|${output_abs}|g" \
    "$template" > "$generated"

trap 'rm -f "$generated"' EXIT

(
    cd "$repo_root"
    yosys -q -s "$generated"
)

echo "Wrote ${output_json}"
