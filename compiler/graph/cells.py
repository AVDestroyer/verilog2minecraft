"""Yosys cell-type classification for the sequential-aware graph IR.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import FrozenSet


class CellKind(Enum):
    COMB = auto()
    STATE = auto()


# Combinational gate primitives emitted after `techmap`.
COMB_CELLS: FrozenSet[str] = frozenset(
    {
        "$_NOT_",
        "$_BUF_",
        "$_AND_",
        "$_NAND_",
        "$_OR_",
        "$_NOR_",
        "$_XOR_",
        "$_XNOR_",
        "$_ANDNOT_",
        "$_ORNOT_",
        "$_MUX_",
        "$_NMUX_",
        "$_AOI3_",
        "$_OAI3_",
        "$_AOI4_",
        "$_OAI4_",
    }
)

# Edge-triggered flops / latches we currently treat as state boundaries.
# Port roles below are the common Yosys gate-level names after techmap.
STATE_CELLS: dict[str, dict[str, str]] = {
    # Positive-edge DFF, sync reset to 0: C=clk, D=data, Q=state, R=reset
    "$_SDFF_PP0_": {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
        "reset": "R",
    },
    "$_SDFF_PP1_": {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
        "reset": "R",
    },
    "$_DFF_P_": {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
    },
    "$_DFF_N_": {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
    },
    "$_DFFE_PP_": {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
        "enable": "E",
    },
    "$_DLATCH_P_": {
        "data_in": "D",
        "data_out": "Q",
        "enable": "E",
    },
    "$_DLATCH_N_": {
        "data_in": "D",
        "data_out": "Q",
        "enable": "E",
    },
}


def classify_cell(yosys_type: str) -> CellKind:
    if yosys_type in COMB_CELLS:
        return CellKind.COMB
    if yosys_type in STATE_CELLS:
        return CellKind.STATE
    raise ValueError(f"unsupported Yosys cell type: {yosys_type}")


def state_port_roles(yosys_type: str) -> dict[str, str]:
    try:
        return STATE_CELLS[yosys_type]
    except KeyError as exc:
        raise ValueError(f"not a known state cell: {yosys_type}") from exc
