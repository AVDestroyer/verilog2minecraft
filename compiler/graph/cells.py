"""Yosys cells accepted by the Minecraft target graph IR."""

from __future__ import annotations

from enum import Enum, auto
from typing import FrozenSet


class CellKind(Enum):
    COMB = auto()
    STATE = auto()


COMB_CELLS: FrozenSet[str] = frozenset(
    {
        "$_NOT_",
        "$_NAND_",
        "$_OR_",
    }
)

LOGICAL_REGISTER = "REGISTER"
REGISTER_YOSYS_TYPE = "$_DFF_P_"

# A logical REGISTER captures D on the positive edge of C and exposes the
# stored value on Q. Reset and enable behavior must be lowered into the D path
# before the graph is parsed.
STATE_CELLS: dict[str, dict[str, str]] = {
    REGISTER_YOSYS_TYPE: {
        "data_in": "D",
        "data_out": "Q",
        "clock": "C",
    },
}


def _looks_sequential(yosys_type: str) -> bool:
    upper = yosys_type.upper()
    return any(token in upper for token in ("DFF", "LATCH", "$_FF_", "$_SR_"))


def classify_cell(yosys_type: str) -> CellKind:
    if yosys_type in COMB_CELLS:
        return CellKind.COMB
    if yosys_type in STATE_CELLS:
        return CellKind.STATE
    if _looks_sequential(yosys_type):
        raise ValueError(
            f"unsupported sequential cell type: {yosys_type}; "
            f"target supports only {REGISTER_YOSYS_TYPE} "
            f"(positive-edge logical {LOGICAL_REGISTER})"
        )
    raise ValueError(f"unsupported Yosys cell type: {yosys_type}")


def state_port_roles(yosys_type: str) -> dict[str, str]:
    try:
        return STATE_CELLS[yosys_type]
    except KeyError as exc:
        raise ValueError(f"not a known state cell: {yosys_type}") from exc


def state_logical_type(yosys_type: str) -> str:
    if yosys_type != REGISTER_YOSYS_TYPE:
        raise ValueError(f"not a known state cell: {yosys_type}")
    return LOGICAL_REGISTER


def state_clock_edge(yosys_type: str) -> str:
    if yosys_type != REGISTER_YOSYS_TYPE:
        raise ValueError(f"not a known state cell: {yosys_type}")
    return "positive"
