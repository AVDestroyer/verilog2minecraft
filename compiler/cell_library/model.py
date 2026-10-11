"""Typed physical-cell metadata used after logical technology mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


Vec3 = tuple[int, int, int]
PinDirection = Literal["input", "output"]


@dataclass(frozen=True)
class Pin:
    name: str
    direction: PinDirection
    position: Vec3


@dataclass(frozen=True)
class Schematic:
    path: Path
    region: str
    dimensions: Vec3
    region_position: Vec3
    region_signed_size: Vec3

    @property
    def region_minimum(self) -> Vec3:
        """Minimum schematic corner used as the BlockStates array origin."""
        return tuple(
            position
            if signed_size > 0
            else position - (abs(signed_size) - 1)
            for position, signed_size in zip(
                self.region_position, self.region_signed_size
            )
        )  # type: ignore[return-value]

    def array_to_schematic(self, position: Vec3) -> Vec3:
        """Map a region-array coordinate to the file's schematic coordinate."""
        return tuple(
            minimum + index
            for minimum, index in zip(self.region_minimum, position)
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class Orientation:
    family: str
    coordinate_space: str
    origin_name: str
    origin: Vec3
    logic_flow: str
    minecraft_axis_directions: Vec3
    allowed_y_rotations: tuple[int, ...]
    allow_mirror: bool


@dataclass(frozen=True)
class PhysicalCell:
    cell_id: str
    logical_type: str
    kind: str
    status: str
    metadata_path: Path
    schematic: Schematic
    orientation: Orientation
    pins: tuple[Pin, ...]

    @property
    def inputs(self) -> tuple[Pin, ...]:
        return tuple(pin for pin in self.pins if pin.direction == "input")

    @property
    def outputs(self) -> tuple[Pin, ...]:
        return tuple(pin for pin in self.pins if pin.direction == "output")

    def cell_to_region_array(self, position: Vec3) -> Vec3:
        """Map a canonical cell-local coordinate to a Litematica array index."""
        return tuple(
            coordinate if cell_direction > 0 else dimension - 1 - coordinate
            for coordinate, dimension, cell_direction in zip(
                position,
                self.schematic.dimensions,
                self.orientation.minecraft_axis_directions,
            )
        )  # type: ignore[return-value]

    def cell_to_schematic(self, position: Vec3) -> Vec3:
        """Map a canonical cell-local coordinate to schematic/world axes."""
        return self.schematic.array_to_schematic(
            self.cell_to_region_array(position)
        )


@dataclass(frozen=True)
class CellLibrary:
    root: Path
    schema_version: int
    coordinate_space: str
    cells: tuple[PhysicalCell, ...]
    deferred_assets: tuple[Path, ...]

    def by_logical_type(self, logical_type: str) -> PhysicalCell:
        matches = [cell for cell in self.cells if cell.logical_type == logical_type]
        if not matches:
            raise KeyError(f"no physical cell for logical type: {logical_type}")
        if len(matches) > 1:
            raise ValueError(
                f"multiple physical cells for logical type: {logical_type}"
            )
        return matches[0]
