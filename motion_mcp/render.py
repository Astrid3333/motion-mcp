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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output": output, "fps": fps,
                "error": f"ffmpeg failed: {exc}"}
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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output_dir": str(out), "frame_count": 0,
                "fps": fps, "frames": [], "error": f"ffmpeg failed: {exc}"}
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


def retime_sequence(frames_dir: str, output_dir: str, speed: float = 0.5,
                    mode: str = "blend") -> dict[str, Any]:
    """Cámara lenta (speed<1) o rápida (speed>1) re-muestrando una secuencia.

    speed: factor de tiempo (0.5 = cámara lenta 2x). El índice de tiempo de
    salida i mapea a t = i * speed en la entrada. La salida se renderiza
    después con motion_render_sequence al fps original → duración multiplicada
    por 1/speed.

    mode: "duplicate" (elige el frame vecino, exacto) o "blend"
    (crossfade lineal entre los dos frames vecinos, suavizado).
    """
    src = Path(frames_dir)
    out = Path(output_dir)
    if speed <= 0:
        return {"ok": False, "error": f"speed must be > 0, got {speed}"}
    if mode not in ("duplicate", "blend"):
        return {"ok": False, "error": f"unknown mode: {mode}"}
    frames = sorted(src.glob("frame_*.png"))
    if not frames:
        return {"ok": False, "error": f"no frames found in {src}"}
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("frame_*.png"):
        old.unlink()
    n_in = len(frames)
    n_out = int((n_in - 1) // speed) + 1
    images: dict[int, Image.Image] = {}
    written = 0
    for i in range(n_out):
        t = i * speed
        i0 = min(int(t), n_in - 1)
        i1 = min(i0 + 1, n_in - 1)
        if mode == "duplicate" or i0 == i1:
            idx = i0
            if idx not in images:
                images[idx] = Image.open(frames[idx]).convert("RGBA")
            img = images[idx]
        else:
            for idx in (i0, i1):
                if idx not in images:
                    images[idx] = Image.open(frames[idx]).convert("RGBA")
            frac = t - i0
            img = Image.blend(images[i0], images[i1], frac)
        img.save(out / f"frame_{i:05d}.png")
        written += 1
    return {
        "ok": True,
        "output_dir": str(out),
        "frame_count": written,
        "input_frames": n_in,
        "speed": speed,
        "mode": mode,
        "duration_multiplier": 1.0 / speed,
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
