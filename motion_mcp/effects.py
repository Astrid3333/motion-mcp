"""Image effects: blur, glow, color grading, chroma key, vignette,
distortion (wave/barrel/swirl)."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def load(path_or_img) -> Image.Image:
    if isinstance(path_or_img, str):
        return Image.open(path_or_img).convert("RGBA")
    return path_or_img.convert("RGBA") if hasattr(path_or_img, "convert") \
        else Image.open(path_or_img).convert("RGBA")


def apply_blur(img: Image.Image, radius: float = 4.0) -> Image.Image:
    if radius <= 0:
        return img.copy()
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_glow(img: Image.Image, radius: float = 8.0, intensity: float = 0.6) \
        -> Image.Image:
    if radius <= 0:
        return img.copy()
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    base = load(img) if not isinstance(img, Image.Image) else img
    return Image.blend(base, blurred, intensity)


def apply_color(img: Image.Image, brightness: float = 1.0,
                contrast: float = 1.0, saturation: float = 1.0) -> Image.Image:
    out = img.copy()
    if brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(brightness)
    if contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(contrast)
    if saturation != 1.0:
        out = ImageEnhance.Color(out).enhance(saturation)
    return out


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def apply_chroma_key(img: Image.Image, key_color: str = "#00ff00",
                     tolerance: float = 40.0, softness: float = 10.0) \
        -> Image.Image:
    """Vuelve transparente el color clave (pantalla verde/azul)."""
    key = _hex_to_rgb(key_color)
    data = img.convert("RGBA")
    r, g, b, a = data.split()
    arr_r = np.array(r).astype(np.int16)
    arr_g = np.array(g).astype(np.int16)
    arr_b = np.array(b).astype(np.int16)
    dist = np.sqrt((arr_r - key[0]) ** 2 + (arr_g - key[1]) ** 2
                   + (arr_b - key[2]) ** 2)
    alpha = np.clip((dist - tolerance) / max(softness, 1), 0, 255).astype(np.uint8)
    a = Image.fromarray(255 - alpha, mode="L")
    out = Image.merge("RGBA", (r, g, b, a))
    return out


def apply_vignette(img: Image.Image, amount: float = 0.5) -> Image.Image:
    if amount <= 0:
        return img.copy()
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2, w / 2
    d = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    v = np.clip(1 - d * amount, 0, 1)
    mask = Image.fromarray((v * 255).astype(np.uint8), mode="L")
    darkened = ImageEnhance.Brightness(img).enhance(1 - amount * 0.6)
    out = Image.composite(darkened, img, mask)
    return out


# ---------------------------------------------------------------------------
# Distortion effects (pixel remapping with bilinear sampling)
# ---------------------------------------------------------------------------

def _sample_bilinear(arr: np.ndarray, sx: np.ndarray,
                     sy: np.ndarray) -> np.ndarray:
    """Muestrea arr (h,w,c) en coordenadas flotantes sx,sy (bilineal)."""
    h, w = arr.shape[:2]
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    fx = sx - x0
    fy = sy - y0
    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x0 + 1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y0 + 1, 0, h - 1)
    fx = fx[..., None]
    fy = fy[..., None]
    top = arr[y0c, x0c] * (1 - fx) + arr[y0c, x1c] * fx
    bot = arr[y1c, x0c] * (1 - fx) + arr[y1c, x1c] * fx
    return (top * (1 - fy) + bot * fy).astype(np.uint8)


def _distort_grid(img: Image.Image, sx: np.ndarray,
                  sy: np.ndarray) -> Image.Image:
    arr = np.array(img)
    return Image.fromarray(_sample_bilinear(arr, sx, sy))


def apply_distort_wave(img: Image.Image, amplitude: float = 12.0,
                       wavelength: float = 60.0, phase: float = 0.0,
                       vertical: bool = False) -> Image.Image:
    """Onda sinusoidal: desplaza cada fila/columna con sen(2πx/λ + phase)."""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if vertical:
        offset = amplitude * np.sin(2 * np.pi * yy / max(wavelength, 1)
                                    + phase)
        sx = xx + offset
        sy = yy
    else:
        offset = amplitude * np.sin(2 * np.pi * xx / max(wavelength, 1)
                                    + phase)
        sx = xx
        sy = yy + offset
    return _distort_grid(img, sx, sy)


def apply_distort_barrel(img: Image.Image, strength: float = 0.3) \
        -> Image.Image:
    """Distorsión de barril (>0, como ojo de pez) o cojín (<0)."""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    nx = (xx - cx) / max(cx, 1)
    ny = (yy - cy) / max(cy, 1)
    r2 = nx * nx + ny * ny
    factor = 1.0 + strength * r2
    sx = cx + nx * factor * cx
    sy = cy + ny * factor * cy
    return _distort_grid(img, sx, sy)


def apply_distort_swirl(img: Image.Image, strength: float = 1.5) \
        -> Image.Image:
    """Remolino: gira cada píxel un ángulo proporcional a la distancia."""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    nx = (xx - cx) / max(cx, 1)
    ny = (yy - cy) / max(cy, 1)
    r2 = nx * nx + ny * ny
    angle = -strength * np.exp(-r2 * 2.0)
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    sx = cx + (nx * cos_a - ny * sin_a) * cx
    sy = cy + (nx * sin_a + ny * cos_a) * cy
    return _distort_grid(img, sx, sy)


def apply_effect(img: Image.Image, effect: str, **params) -> Image.Image:
    """Aplica un efecto a una imagen."""
    if effect == "blur":
        return apply_blur(img, radius=params.get("radius", 4.0))
    if effect == "glow":
        return apply_glow(img, radius=params.get("radius", 8.0),
                          intensity=params.get("intensity", 0.6))
    if effect == "color":
        return apply_color(img,
                           brightness=params.get("brightness", 1.0),
                           contrast=params.get("contrast", 1.0),
                           saturation=params.get("saturation", 1.0))
    if effect == "chroma_key":
        return apply_chroma_key(img,
                                key_color=params.get("key_color", "#00ff00"),
                                tolerance=params.get("tolerance", 40.0),
                                softness=params.get("softness", 10.0))
    if effect == "vignette":
        return apply_vignette(img, amount=params.get("amount", 0.5))
    if effect == "wave":
        return apply_distort_wave(img,
                                  amplitude=params.get("amplitude", 12.0),
                                  wavelength=params.get("wavelength", 60.0),
                                  phase=params.get("phase", 0.0),
                                  vertical=bool(params.get("vertical",
                                                           False)))
    if effect == "barrel":
        return apply_distort_barrel(img,
                                    strength=params.get("strength", 0.3))
    if effect == "swirl":
        return apply_distort_swirl(img,
                                   strength=params.get("strength", 1.5))
    raise ValueError(f"unknown effect: {effect}")
