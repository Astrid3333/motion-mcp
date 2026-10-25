"""Layered composition of images and video frames (After Effects-like)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageEnhance, ImageOps

from .keyframes import interpolate


BLEND_MODES = {"normal", "multiply", "screen", "overlay", "add"}


@dataclass
class LayerSpec:
    source: str
    position: Any = field(default_factory=lambda: [0, 0])
    scale: Any = 1.0
    rotation: Any = 0.0
    opacity: Any = 1.0
    blend: str = "normal"
    anchor: str = "center"


def _layer_from_spec(raw: dict[str, Any]) -> LayerSpec:
    """Construye un LayerSpec aceptando keyframes anidados o inline.

    Acepta dos formas de animar:
      - inline:    {"position": [{"time": 0, "value": ...}, ...]}
      - anidados:  {"keyframes": {"position": [{"time": 0, "value": ...}]}}
    """
    l = dict(raw)
    for prop, kf_list in (l.pop("keyframes", {}) or {}).items():
        l[prop] = kf_list
    return LayerSpec(**l)


def _coerce(value: Any, t: float) -> Any:
    """Resuelve un valor fijo o una lista de keyframes en el tiempo t."""
    if isinstance(value, list) and value and isinstance(value[0], dict):
        kfs = []
        for k in value:
            kfs.append(
                __import__("motion_mcp.keyframes", fromlist=["Keyframe"]).Keyframe(
                    time=float(k["time"]), value=k["value"]
                )
            )
        return interpolate(kfs, t)
    return value


def _load_frame(source: str, t: float, tmpdir: str) -> Image.Image:
    """Carga un frame de una imagen o de un video en el tiempo t (segundos)."""
    path = Path(source)
    ext = path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        return Image.open(path).convert("RGBA")
    # Video: extraer frame con ffmpeg
    out = Path(tmpdir) / f"frame_{os.getpid()}_{t}.png"
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(t), "-i", str(path),
            "-frames:v", "1", str(out),
        ],
        capture_output=True,
        timeout=60,
    )
    if not out.exists():
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return Image.open(out).convert("RGBA")


def _apply_transform(img: Image.Image, scale: float, rotation: float,
                     opacity: float, anchor: str) -> Image.Image:
    w, h = img.size
    if scale != 1.0:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
    if rotation:
        img = img.rotate(-rotation, resample=Image.BICUBIC, expand=True,
                         fillcolor=(0, 0, 0, 0))
    if opacity < 1.0:
        alpha = img.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        img.putalpha(alpha)
    return img


def _blend(base: Image.Image, layer: Image.Image, mode: str) -> Image.Image:
    base = base.convert("RGBA")
    layer = layer.convert("RGBA")
    if mode == "normal":
        return Image.alpha_composite(base, layer)
    if mode == "add":
        r = ImageChops.add(base, layer)
        return Image.merge("RGBA", (*r.split()[:3], base.split()[3]))
    if mode == "multiply":
        r = ImageChops.multiply(base, layer)
        return Image.merge("RGBA", (*r.split()[:3], base.split()[3]))
    if mode == "screen":
        r = ImageChops.screen(base, layer)
        return Image.merge("RGBA", (*r.split()[:3], base.split()[3]))
    if mode == "overlay":
        r = ImageChops.overlay(base, layer)
        return Image.merge("RGBA", (*r.split()[:3], base.split()[3]))
    return Image.alpha_composite(base, layer)


def render_composition(spec: dict[str, Any], output_dir: str) -> dict[str, Any]:
    """Renderiza una composición por capas a una secuencia de frames PNG.

    spec:
      size: [w, h]
      fps: number
      duration_seconds: number
      background: color hex o "transparent"
      layers: [ { source, position, scale, rotation, opacity, blend, anchor } ]

    Devuelve { ok, output_dir, frame_count, fps, frames: [paths] }.
    """
    size = tuple(spec.get("size", [1920, 1080]))
    fps = float(spec.get("fps", 30))
    duration = float(spec.get("duration_seconds", 5))
    bg = spec.get("background", "transparent")
    layers = [_layer_from_spec(l) for l in spec.get("layers", [])]

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tmpdir = tempfile.mkdtemp(prefix="motion-mcp-comp-")
    frames: list[str] = []
    total = max(1, int(round(duration * fps)))
    for i in range(total):
        t = i / fps
        canvas = Image.new("RGBA", size, (0, 0, 0, 0) if bg == "transparent"
                           else _hex_rgb(bg))
        for layer in layers:
            img = _load_frame(layer.source, t, tmpdir)
            pos = _coerce(layer.position, t)
            scale = _coerce(layer.scale, t)
            rot = _coerce(layer.rotation, t)
            opa = _coerce(layer.opacity, t)
            img = _apply_transform(img, float(scale), float(rot), float(opa),
                                   layer.anchor)
            # centrar / anclar
            lw, lh = img.size
            cx, cy = size[0] // 2, size[1] // 2
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                x, y = float(pos[0]), float(pos[1])
            else:
                x, y = cx, cy
            if layer.anchor == "center":
                x -= lw / 2
                y -= lh / 2
            layer_img = Image.new("RGBA", size, (0, 0, 0, 0))
            # sin máscara: el alpha propio de img ya controla la opacidad;
            # alpha_composite después hace la mezcla exactamente una vez
            layer_img.paste(img, (int(x), int(y)))
            canvas = _blend(canvas, layer_img, layer.blend)
        frame_path = out / f"frame_{i:05d}.png"
        canvas.convert("RGB").save(frame_path)
        frames.append(str(frame_path))

    return {
        "ok": True,
        "output_dir": str(out),
        "frame_count": len(frames),
        "fps": fps,
        "duration_seconds": duration,
        "frames": frames,
    }


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
