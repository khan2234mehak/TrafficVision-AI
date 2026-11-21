"""Per-camera computer-vision configuration (coordinates are normalised 0..1 so they survive resolution changes)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Point = tuple[float, float]


def _check_point(p: Point) -> Point:
    if not (0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0):
        raise ValueError("coordinates must be normalised between 0 and 1")
    return p


class CountingLine(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    p1: Point
    p2: Point

    @field_validator("p1", "p2")
    @classmethod
    def _norm(cls, v: Point) -> Point:
        return _check_point(v)


class Zone(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    type: Literal["density", "restricted", "wrong_way"] = "density"
    polygon: list[Point] = Field(min_length=3, max_length=40)
    # wrong_way: unit-ish vector describing the ALLOWED travel direction (image coordinates, y grows downwards)
    direction: Point | None = None
    capacity: int = Field(default=15, ge=1, le=500)  # density zones: vehicles that mean "full"
    min_dwell_s: float = Field(default=1.0, ge=0.0, le=60.0)  # restricted zones

    @field_validator("polygon")
    @classmethod
    def _poly(cls, v: list[Point]) -> list[Point]:
        for p in v:
            _check_point(p)
        return v


class SignalConfig(BaseModel):
    """Red-light detection ONLY runs when enabled with a stop line. The signal state is configured
    (manual override or fixed cycle) - it is NOT read from the video."""
    enabled: bool = False
    mode: Literal["manual", "cycle"] = "manual"
    manual_state: Literal["red", "green"] = "red"
    red_seconds: float = Field(default=30.0, gt=0)
    green_seconds: float = Field(default=30.0, gt=0)
    cycle_offset_s: float = 0.0
    stop_line: tuple[Point, Point] | None = None
    violation_direction: Literal["in", "out"] = "in"


class Calibration(BaseModel):
    """Speed estimation needs a real-world scale. Without it overspeed detection stays OFF."""
    enabled: bool = False
    meters_per_pixel: float | None = Field(default=None, gt=0)
    speed_limit_kmh: float = Field(default=60.0, gt=0, le=250)


class CameraCVConfig(BaseModel):
    counting_lines: list[CountingLine] = Field(default_factory=list, max_length=12)
    zones: list[Zone] = Field(default_factory=list, max_length=20)
    signal: SignalConfig = Field(default_factory=SignalConfig)
    calibration: Calibration = Field(default_factory=Calibration)


def default_cv_config() -> dict:
    return CameraCVConfig(
        counting_lines=[CountingLine(id="line-1", name="Main counting line", p1=(0.05, 0.6), p2=(0.95, 0.6))],
        zones=[Zone(id="zone-density", name="Whole road", type="density",
                    polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], capacity=15)],
    ).model_dump(mode="json")
