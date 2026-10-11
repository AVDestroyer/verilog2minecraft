"""Small, dependency-free reader for the Litematica header data we need."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
from pathlib import Path
import struct
from typing import Any, BinaryIO

from .model import Vec3


@dataclass(frozen=True)
class LitematicRegion:
    name: str
    position: Vec3
    signed_size: Vec3

    @property
    def dimensions(self) -> Vec3:
        return tuple(abs(value) for value in self.signed_size)  # type: ignore[return-value]


@dataclass(frozen=True)
class LitematicSummary:
    name: str
    minecraft_data_version: int
    regions: tuple[LitematicRegion, ...]


class _NbtReader:
    def __init__(self, stream: BinaryIO):
        self.stream = stream

    def _read(self, size: int) -> bytes:
        data = self.stream.read(size)
        if len(data) != size:
            raise ValueError("truncated NBT payload")
        return data

    def _unpack(self, fmt: str) -> Any:
        size = struct.calcsize(">" + fmt)
        return struct.unpack(">" + fmt, self._read(size))[0]

    def _string(self) -> str:
        return self._read(self._unpack("H")).decode("utf-8")

    def _array(self, fmt: str) -> list[Any]:
        length = self._unpack("i")
        if length < 0:
            raise ValueError(f"negative NBT array length: {length}")
        return [self._unpack(fmt) for _ in range(length)]

    def payload(self, tag: int) -> Any:
        scalar_formats = {1: "b", 2: "h", 3: "i", 4: "q", 5: "f", 6: "d"}
        if tag in scalar_formats:
            return self._unpack(scalar_formats[tag])
        if tag == 7:
            length = self._unpack("i")
            if length < 0:
                raise ValueError(f"negative NBT byte-array length: {length}")
            return self._read(length)
        if tag == 8:
            return self._string()
        if tag == 9:
            item_tag = self._unpack("b")
            length = self._unpack("i")
            if length < 0:
                raise ValueError(f"negative NBT list length: {length}")
            return [self.payload(item_tag) for _ in range(length)]
        if tag == 10:
            result: dict[str, Any] = {}
            while True:
                item_tag = self._unpack("b")
                if item_tag == 0:
                    return result
                name = self._string()
                result[name] = self.payload(item_tag)
        if tag == 11:
            return self._array("i")
        if tag == 12:
            return self._array("q")
        raise ValueError(f"unsupported NBT tag: {tag}")

    def root(self) -> dict[str, Any]:
        tag = self._unpack("b")
        if tag != 10:
            raise ValueError(f"expected compound NBT root, found tag {tag}")
        self._string()  # Root name is normally empty and is not semantically used.
        return self.payload(tag)


def _vec3(value: Any, field: str) -> Vec3:
    if not isinstance(value, dict):
        raise ValueError(f"Litematica {field} is not a compound")
    try:
        coords = tuple(int(value[axis]) for axis in ("x", "y", "z"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid Litematica {field}") from exc
    return coords  # type: ignore[return-value]


def read_litematic_summary(path: Path) -> LitematicSummary:
    try:
        with gzip.open(path, "rb") as stream:
            root = _NbtReader(stream).root()
    except (OSError, EOFError, struct.error, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read Litematica file {path}: {exc}") from exc

    metadata = root.get("Metadata")
    raw_regions = root.get("Regions")
    if not isinstance(metadata, dict) or not isinstance(raw_regions, dict):
        raise ValueError(f"Litematica file lacks Metadata or Regions: {path}")

    regions: list[LitematicRegion] = []
    for name, raw_region in raw_regions.items():
        if not isinstance(raw_region, dict):
            raise ValueError(f"invalid Litematica region {name!r}: {path}")
        regions.append(
            LitematicRegion(
                name=name,
                position=_vec3(raw_region.get("Position"), "region Position"),
                signed_size=_vec3(raw_region.get("Size"), "region Size"),
            )
        )

    return LitematicSummary(
        name=str(metadata.get("Name", "")),
        minecraft_data_version=int(root.get("MinecraftDataVersion", 0)),
        regions=tuple(regions),
    )
