"""Keyframe interpolation for motion properties."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Keyframe:
    time: float  # seconds
    value: Any


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_tuple(a, b, t):
    return tuple(_lerp(x, y, t) for x, y in zip(a, b))


def interpolate(keyframes: list[Keyframe], time: float) -> Any:
    """Devuelve el valor interpolado en `time` segundos.

    Los keyframes deben estar ordenados por `time`. Interpolación lineal entre
    el keyframe anterior y el siguiente; fuera de rango se clampa al valor del
    extremo más cercano. Soporta floats, ints y tuplas (x, y) / (r, g, b, a).
    """
    if not keyframes:
        return None
    kfs = sorted(keyframes, key=lambda k: k.time)
    if time <= kfs[0].time:
        return kfs[0].value
    if time >= kfs[-1].time:
        return kfs[-1].value
    prev, nxt = kfs[0], kfs[1]
    for i in range(1, len(kfs)):
        if time <= kfs[i].time:
            prev, nxt = kfs[i - 1], kfs[i]
            break
    span = nxt.time - prev.time
    t = 0.0 if span == 0 else (time - prev.time) / span
    a, b = prev.value, nxt.value
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _lerp(float(a), float(b), t)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) \
            and len(a) == len(b):
        out = _lerp_tuple(tuple(a), tuple(b), t)
        return list(out) if isinstance(a, list) else out
    return a if t < 0.5 else b


def keyframe_values(keyframes: list[Keyframe], times: list[float]) -> list[Any]:
    return [interpolate(keyframes, t) for t in times]
