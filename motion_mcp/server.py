"""MCP server for motion graphics (After Effects-like composition)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from mcp.server.mcpserver import MCPServer

from . import __version__
from . import compose as compose_mod
from . import effects as effects_mod
from . import keyframes as keyframes_mod
from . import render as render_mod

mcp = MCPServer(
    name="motion",
    version=__version__,
    instructions=(
        "Motion graphics / After Effects-like composition: layer comps with "
        "position/scale/rotation/opacity/blend keyframes, blur/glow/color/"
        "chroma-key/vignette effects, wave/barrel/swirl distortion, masks, "
        "animated text, slow-motion retiming, and ffmpeg rendering to MP4 "
        "or extraction to frames."
    ),
)


def _abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


@mcp.tool()
def motion_compose_layers(spec: dict[str, Any],
                          output_dir: str) -> dict[str, Any]:
    """Renderiza una composición por capas a una secuencia de frames PNG.

    spec:
      size: [w, h]
      fps: number
      duration_seconds: number
      background: color hex o "transparent"
      layers: [ { source, position, scale, rotation, opacity, blend, anchor } ]
        position/scale/rotation/opacity pueden ser valor fijo o lista de
        keyframes [{time, value}, ...] (inline), o bien animar con un bloque
        anidado "keyframes": { "<prop>": [{time, value}, ...] }.
    """
    return compose_mod.render_composition(spec, output_dir)


@mcp.tool()
def motion_keyframes(keyframes: list[dict[str, Any]],
                     times: list[float]) -> dict[str, Any]:
    """Interpola keyframes [{time, value}] en los tiempos dados (segundos).
    Soporta valores numéricos y listas/tuplas (x,y)/(r,g,b,a)."""
    kfs = [keyframes_mod.Keyframe(time=float(k["time"]), value=k["value"])
           for k in keyframes]
    values = keyframes_mod.keyframe_values(kfs, times)
    return {"ok": True, "values": values}


@mcp.tool()
def motion_apply_effect(image: str, effect: str, output: str,
                        **params: Any) -> dict[str, Any]:
    """Aplica un efecto a una imagen y guarda el resultado.

    effect: blur | glow | color | chroma_key | vignette | wave | barrel | swirl
    params: blur->radius; glow->radius,intensity;
            color->brightness,contrast,saturation;
            chroma_key->key_color,tolerance,softness;
            vignette->amount;
            wave->amplitude,wavelength,phase,vertical;
            barrel->strength (0.3=pez, negativo=cojín);
            swirl->strength
    """
    image = _abs(image)
    output = _abs(output)
    if not Path(image).is_file():
        return {"ok": False, "error": f"image not found: {image}"}
    img = effects_mod.load(image)
    try:
        out = effects_mod.apply_effect(img, effect, **params)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    out.save(output)
    return {"ok": True, "output": output, "effect": effect}


@mcp.tool()
def motion_add_mask(image: str, mask_type: str, output: str,
                    **params: Any) -> dict[str, Any]:
    """Aplica una máscara alpha a una imagen.

    mask_type: circle | rect | from_image
    circle: center [x,y], radius (px)
    rect: left, top, right, bottom
    from_image: mask_path (usa su canal alpha o luminancia)
    """
    image = _abs(image)
    output = _abs(output)
    if not Path(image).is_file():
        return {"ok": False, "error": f"image not found: {image}"}
    img = effects_mod.load(image)
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    if mask_type == "circle":
        cx, cy = params.get("center", [w / 2, h / 2])
        radius = float(params.get("radius", min(w, h) / 2))
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - cx) / max(radius, 1)) ** 2
                    + ((yy - cy) / max(radius, 1)) ** 2)
        v = np.clip(1 - d, 0, 1)
        mask = Image.fromarray((v * 255).astype(np.uint8), mode="L")
    elif mask_type == "rect":
        l, t_, r, b = (params.get("left", 0), params.get("top", 0),
                       params.get("right", w), params.get("bottom", h))
        mask = Image.new("L", (w, h), 255)
        m = Image.new("L", (w, h), 0)
        m.paste(255, (int(l), int(t_), int(r), int(b)))
        mask = m
    elif mask_type == "from_image":
        mp = _abs(params.get("mask_path", ""))
        if not Path(mp).is_file():
            return {"ok": False, "error": f"mask image not found: {mp}"}
        mk = effects_mod.load(mp).resize((w, h))
        mask = mk.split()[3] if mk.mode == "RGBA" else \
            mk.convert("L")
    else:
        return {"ok": False, "error": f"unknown mask_type: {mask_type}"}
    r, g, b, a = img.split()
    a = ImageChops_multiply_alpha(a, mask)
    out = Image.merge("RGBA", (r, g, b, a))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    out.save(output)
    return {"ok": True, "output": output, "mask_type": mask_type}


def ImageChops_multiply_alpha(a: Image.Image, mask: Image.Image) -> Image.Image:
    arr_a = np.array(a).astype(np.float32) / 255.0
    arr_m = np.array(mask).astype(np.float32) / 255.0
    return Image.fromarray((arr_a * arr_m * 255).astype(np.uint8), mode="L")


@mcp.tool()
def motion_add_text(image: str, text: str, output: str,
                    position: list[int] | None = None,
                    font_size: int = 40, color: str = "#ffffff",
                    anchor: str = "lt") -> dict[str, Any]:
    """Dibuja texto animado sobre una imagen y guarda el resultado."""
    image = _abs(image)
    output = _abs(output)
    if not Path(image).is_file():
        return {"ok": False, "error": f"image not found: {image}"}
    img = effects_mod.load(image)
    pos = tuple(position) if position else (0, 0)
    out = render_mod.add_text(img, text, pos, font_size, color, anchor)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    out.save(output)
    return {"ok": True, "output": output}


@mcp.tool()
def motion_render_sequence(frames_dir: str, output: str, fps: int = 30,
                           codec: str = "libx264", crf: int = 23,
                           pix_fmt: str = "yuv420p") -> dict[str, Any]:
    """Convierte una secuencia de frames PNG numerados en un video MP4."""
    return render_mod.render_sequence(frames_dir, output, fps, codec, crf,
                                      pix_fmt)


@mcp.tool()
def motion_extract_frames(video: str, output_dir: str,
                          fps: int | None = None,
                          start: float | None = None,
                          end: float | None = None) -> dict[str, Any]:
    """Extrae frames de un video a imágenes PNG numeradas."""
    return render_mod.extract_frames(video, output_dir, fps, start, end)


@mcp.tool()
def motion_retime(frames_dir: str, output_dir: str, speed: float = 0.5,
                  mode: str = "blend") -> dict[str, Any]:
    """Cámara lenta / rápida: re-muestrea una secuencia de frames.

    speed: 0.5 = cámara lenta 2x, 2.0 = rápida 2x. Renderiza la salida con
    motion_render_sequence al MISMO fps que la secuencia original para
    obtener la duración multiplicada por 1/speed.
    mode: "duplicate" (frames exactos) | "blend" (crossfade suave).
    """
    return render_mod.retime_sequence(_abs(frames_dir), _abs(output_dir),
                                      speed=speed, mode=mode)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
