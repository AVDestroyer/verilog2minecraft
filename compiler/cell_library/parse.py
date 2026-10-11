"""Load and validate the manifest-driven physical cell library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .litematic import read_litematic_summary
from .model import CellLibrary, Orientation, PhysicalCell, Pin, Schematic, Vec3


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{field} must be an array of strings")
    return tuple(value)


def _vec3(value: Any, field: str) -> Vec3:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        raise ValueError(f"{field} must be an array of three integers")
    return tuple(value)  # type: ignore[return-value]


def _unique(values: Iterable[str], field: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {field}: {value}")
        seen.add(value)


def _load_cell(metadata_path: Path) -> PhysicalCell:
    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read cell metadata {metadata_path}: {exc}") from exc
    data = _object(raw, str(metadata_path))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported cell schema in {metadata_path}")
    for field in ("id", "logical_type", "kind", "status"):
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(f"{metadata_path}: {field} must be a non-empty string")

    schematic_data = _object(data.get("schematic"), "schematic")
    schematic_path = metadata_path.parent / str(schematic_data.get("file", ""))
    dimensions = _vec3(schematic_data.get("dimensions"), "schematic.dimensions")
    if any(value <= 0 for value in dimensions):
        raise ValueError("schematic dimensions must be positive")
    region_name = str(schematic_data.get("region", ""))

    summary = read_litematic_summary(schematic_path)
    matching_regions = [r for r in summary.regions if r.name == region_name]
    if len(matching_regions) != 1:
        raise ValueError(
            f"expected one region {region_name!r} in {schematic_path}, "
            f"found {len(matching_regions)}"
        )
    litematic_region = matching_regions[0]
    if litematic_region.dimensions != dimensions:
        raise ValueError(
            f"dimension mismatch for {schematic_path}: metadata has {dimensions}, "
            f"schematic has {litematic_region.dimensions}"
        )

    orientation_data = _object(data.get("orientation"), "orientation")
    origin_data = _object(
        orientation_data.get("origin"), "orientation.origin"
    )
    rotations = orientation_data.get("allowed_y_rotations")
    if (
        not isinstance(rotations, list)
        or not rotations
        or not all(isinstance(v, int) and v in (0, 90, 180, 270) for v in rotations)
    ):
        raise ValueError(
            "orientation.allowed_y_rotations must contain 0/90/180/270"
        )
    origin = _vec3(origin_data.get("position"), "orientation.origin.position")
    axis_directions = _vec3(
        orientation_data.get("minecraft_axis_directions"),
        "orientation.minecraft_axis_directions",
    )
    if any(direction not in (-1, 1) for direction in axis_directions):
        raise ValueError("minecraft_axis_directions entries must be -1 or 1")

    raw_pins = data.get("pins")
    if not isinstance(raw_pins, list) or not raw_pins:
        raise ValueError("pins must be a non-empty array")
    pins: list[Pin] = []
    for index, raw_pin in enumerate(raw_pins):
        pin_data = _object(raw_pin, f"pins[{index}]")
        direction = pin_data.get("direction")
        if direction not in ("input", "output"):
            raise ValueError(f"pins[{index}].direction must be input or output")
        pins.append(
            Pin(
                name=str(pin_data.get("name", "")),
                direction=direction,
                position=_vec3(pin_data.get("position"), f"pins[{index}].position"),
            )
        )

    _unique((pin.name for pin in pins), "pin name")
    for label, position in [("origin", origin)] + [
        (f"pin {pin.name}", pin.position) for pin in pins
    ]:
        if any(
            coord < 0 or coord >= limit
            for coord, limit in zip(position, dimensions)
        ):
            raise ValueError(f"{label} {position} is outside dimensions {dimensions}")
    if not any(pin.direction == "input" for pin in pins):
        raise ValueError("cell must have at least one input pin")
    if not any(pin.direction == "output" for pin in pins):
        raise ValueError("cell must have at least one output pin")

    return PhysicalCell(
        cell_id=str(data.get("id", "")),
        logical_type=str(data.get("logical_type", "")),
        kind=str(data.get("kind", "")),
        status=str(data.get("status", "")),
        metadata_path=metadata_path,
        schematic=Schematic(
            path=schematic_path,
            region=region_name,
            dimensions=dimensions,
            region_position=litematic_region.position,
            region_signed_size=litematic_region.signed_size,
        ),
        orientation=Orientation(
            family=str(orientation_data.get("family", "")),
            coordinate_space=str(orientation_data.get("coordinate_space", "")),
            origin_name=str(origin_data.get("name", "")),
            origin=origin,
            logic_flow=str(orientation_data.get("logic_flow", "")),
            minecraft_axis_directions=axis_directions,
            allowed_y_rotations=tuple(rotations),
            allow_mirror=bool(orientation_data.get("allow_mirror", False)),
        ),
        pins=tuple(pins),
    )


def load_cell_library(root: str | Path) -> CellLibrary:
    root = Path(root)
    manifest_path = root / "library.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read cell-library manifest {manifest_path}: {exc}") from exc
    data = _object(raw, str(manifest_path))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported library schema in {manifest_path}")

    coordinate_data = _object(data.get("coordinate_system"), "coordinate_system")
    coordinate_space = coordinate_data.get("name")
    if not isinstance(coordinate_space, str) or not coordinate_space:
        raise ValueError("coordinate_system.name must be a non-empty string")

    metadata_files = _strings(data.get("cells"), "cells")
    deferred_files = _strings(data.get("deferred_assets", []), "deferred_assets")
    cells = tuple(_load_cell(root / relative) for relative in metadata_files)
    _unique((cell.cell_id for cell in cells), "cell id")
    _unique((cell.logical_type for cell in cells), "logical type")

    families = {cell.orientation.family for cell in cells}
    if len(families) > 1:
        raise ValueError(f"active cells do not share an orientation family: {families}")
    for cell in cells:
        if cell.orientation.coordinate_space != coordinate_space:
            raise ValueError(
                f"{cell.cell_id} uses coordinate space "
                f"{cell.orientation.coordinate_space!r}, expected {coordinate_space!r}"
            )

    deferred_assets = tuple(root / relative for relative in deferred_files)
    for path in deferred_assets:
        if not path.is_file():
            raise ValueError(f"deferred asset does not exist: {path}")

    return CellLibrary(
        root=root,
        schema_version=1,
        coordinate_space=coordinate_space,
        cells=cells,
        deferred_assets=deferred_assets,
    )
