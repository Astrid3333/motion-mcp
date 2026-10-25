"""Render: frames <-> video with ffmpeg, and text overlay."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def render_sequence(frames_dir: str, output: str, fps: int = 30,
                    codec: str = "libx264", crf: int = 23,
                    pix_fmt: str = "yuv420p") -> dict[str, Any]:
    """Convierte una secuencia de frames PNG numerados en un video MP4."""
    frames = Path(frames_dir)
    output = str(Path(output).expanduser().resolve())
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    pattern = str(frames / "frame_%05d.png")
    cmd = [
        "ffmpeg", "-y", "-r", str(fps), "-i", pattern,
        "-c:v", codec, "-crf", str(crf), "-pix_fmt", pix_fmt, output,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    ok = proc.returncode == 0 and Path(output).exists()
    return {
        "ok": ok,
        "output": output,
        "fps": fps,
        "returncode": proc.returncode,
        "stderr": proc.stderr[-500:] if not ok else "",
    }


def extract_frames(video: str, output_dir: str, fps: int | None = None,
                   start: float | None = None,
                   end: float | None = None) -> dict[str, Any]:
    """Extrae frames de un video a imágenes PNG."""
    video = str(Path(video).expanduser().resolve())
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", video]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    if fps is not None:
        cmd += ["-r", str(fps)]
    cmd += [str(out / "frame_%05d.png")]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    produced = sorted(p for p in out.iterdir() if p.suffix == ".png")
    return {
        "ok": proc.returncode == 0,
        "output_dir": str(out),
        "frame_count": len(produced),
        "fps": fps,
        "frames": [str(p) for p in produced],
        "returncode": proc.returncode,
        "stderr": proc.stderr[-500:] if proc.returncode != 0 else "",
    }


def _default_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def add_text(img: Image.Image, text: str, position: tuple[int, int] = (0, 0),
             font_size: int = 40, color: str = "#ffffff",
             anchor: str = "lt") -> Image.Image:
    """Dibuja texto sobre una imagen. anchor: PIL text anchor (lt, rt, lb, rb,
    mm, etc.)."""
    import os  # noqa: F401  (ensured at module level via caller)
    out = img.convert("RGBA").copy()
    draw = ImageDraw.Draw(out)
    font = _default_font(font_size)
    r, g, b = _hex_rgb(color)
    draw.text(position, text, font=font, fill=(r, g, b, 255), anchor=anchor)
    return out


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
