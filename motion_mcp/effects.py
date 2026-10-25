"""Image effects: 27 efectos — base (blur/glow/color/chroma-key/vignette),
distorsión (wave/barrel/swirl), estilo (pixelate/mirror/noise/rgb_split/
scanlines/zoom/rotate/roll), color y valor (invert/grayscale/sepia/posterize/
threshold/duotone/hue/solarize/sharpen/emboss/edge). Catálogo en EFFECTS."""

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
    arr_r = np.array(r).astype(np.float32)
    arr_g = np.array(g).astype(np.float32)
    arr_b = np.array(b).astype(np.float32)
    dist = np.sqrt((arr_r - key[0]) ** 2 + (arr_g - key[1]) ** 2
                   + (arr_b - key[2]) ** 2)
    # cerca de la clave -> 0 (transparente); lejos -> 255 (opaco)
    alpha = (np.clip((dist - tolerance) / max(softness, 1), 0, 1)
             * 255).astype(np.uint8)
    a = Image.fromarray(alpha, mode="L")
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


# ---------------------------------------------------------------------------
# Style / channel effects
# ---------------------------------------------------------------------------

def apply_pixelate(img: Image.Image, block: int = 12) -> Image.Image:
    """Mosaico: reduce con BOX y reescala con píxeles cuadrados."""
    w, h = img.size
    b = max(2, int(block))
    small = img.resize((max(1, w // b), max(1, h // b)), Image.BOX)
    return small.resize((w, h), Image.NEAREST)


def apply_mirror(img: Image.Image, axis: str = "horizontal") -> Image.Image:
    if axis == "vertical":
        return ImageOps.flip(img)
    return ImageOps.mirror(img)


def apply_noise(img: Image.Image, amount: float = 25.0,
                seed: int = 0) -> Image.Image:
    """Ruido aditivo reproducible (seed fija ⇒ resultado determinista)."""
    rng = np.random.default_rng(int(seed))
    arr = np.array(img).astype(np.int16)
    n = rng.normal(0, float(amount), arr.shape[:2]).astype(np.int16)[..., None]
    rgb = np.clip(arr[..., :3] + n, 0, 255)
    out = np.concatenate([rgb, arr[..., 3:4]], axis=2).astype(np.uint8)
    return Image.fromarray(out)


def apply_rgb_split(img: Image.Image, offset: int = 6) -> Image.Image:
    """Aberración cromática: R desplazado a la izquierda, B a la derecha."""
    arr = np.array(img)
    o = int(offset)
    out = arr.copy()
    if o != 0:
        out[..., 0] = np.roll(arr[..., 0], -o, axis=1)
        out[..., 2] = np.roll(arr[..., 2], o, axis=1)
    return Image.fromarray(out)


def apply_invert(img: Image.Image) -> Image.Image:
    rgb = ImageOps.invert(img.convert("RGB"))
    out = rgb.convert("RGBA")
    out.putalpha(img.split()[3])
    return out


def apply_grayscale(img: Image.Image) -> Image.Image:
    gray = img.convert("L").convert("RGBA")
    gray.putalpha(img.split()[3])
    return gray


def apply_sepia(img: Image.Image) -> Image.Image:
    gray = np.array(img.convert("L")).astype(np.float32)
    r = np.clip(gray * 1.07 + 12, 0, 255)
    g = np.clip(gray * 0.95 + 4, 0, 255)
    b = np.clip(gray * 0.74 - 8, 0, 255)
    out = np.stack([r, g, b, np.array(img)[..., 3].astype(np.float32)],
                   axis=2).astype(np.uint8)
    return Image.fromarray(out)


def apply_posterize(img: Image.Image, levels: int = 6) -> Image.Image:
    """Reduce cada canal a N niveles (efecto cartel/serigrafía)."""
    lv = max(2, int(levels))
    arr = np.array(img)
    step = 255 // (lv - 1)
    rgb = ((arr[..., :3].astype(np.int16) + step // 2) // step * step)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    out = np.concatenate([rgb, arr[..., 3:4]], axis=2)
    return Image.fromarray(out)


def apply_threshold(img: Image.Image, level: int = 128) -> Image.Image:
    """Blanco y negro puro por umbral de luminancia."""
    gray = np.array(img.convert("L"))
    bw = ((gray >= int(level)) * 255).astype(np.uint8)
    out = np.stack([bw, bw, bw, np.array(img)[..., 3]], axis=2)
    return Image.fromarray(out)


def apply_duotone(img: Image.Image, dark: str = "#1a1a4d",
                  light: str = "#ffd700") -> Image.Image:
    """Mapa de dos colores: sombras -> dark, luces -> light."""
    d = np.array(_hex_to_rgb(dark), dtype=np.float32)
    l = np.array(_hex_to_rgb(light), dtype=np.float32)
    t = np.array(img.convert("L")).astype(np.float32)[..., None] / 255.0
    rgb = d * (1 - t) + l * t
    out = np.concatenate(
        [rgb, np.array(img)[..., 3:4].astype(np.float32)], axis=2
    ).astype(np.uint8)
    return Image.fromarray(out)


def apply_hue(img: Image.Image, shift: float = 30.0) -> Image.Image:
    """Rota el tono (grados) en el espacio HSV."""
    hsv = np.array(img.convert("HSV"))
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + int(shift)) % 256
    out = Image.fromarray(hsv, mode="HSV").convert("RGBA")
    out.putalpha(img.split()[3])
    return out


def apply_solarize(img: Image.Image, threshold: int = 128) -> Image.Image:
    out = ImageOps.solarize(img.convert("RGB"), threshold=int(threshold))
    rgba = out.convert("RGBA")
    rgba.putalpha(img.split()[3])
    return rgba


def apply_sharpen(img: Image.Image, amount: int = 150,
                  radius: float = 2.0) -> Image.Image:
    return img.filter(ImageFilter.UnsharpMask(radius=radius,
                                              percent=int(amount),
                                              threshold=3))


def apply_emboss(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.EMBOSS)


def apply_edge(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.FIND_EDGES)


def apply_scanlines(img: Image.Image, spacing: int = 4,
                    opacity: float = 0.4) -> Image.Image:
    """Líneas de barrido estilo TV/CRT (oscurece cada `spacing` filas)."""
    arr = np.array(img).astype(np.float32)
    h = arr.shape[0]
    sp = max(2, int(spacing))
    rows = (np.arange(h) % sp == 0).astype(np.float32)[:, None]
    arr[..., :3] *= (1.0 - float(opacity) * rows)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def apply_zoom(img: Image.Image, factor: float = 1.5) -> Image.Image:
    """Zoom centrado (recorta y reescala al tamaño original)."""
    f = max(1.01, float(factor))
    w, h = img.size
    cw, ch = w / f, h / f
    box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
    return img.resize((w, h), Image.BICUBIC, box=box)


def apply_rotate(img: Image.Image, degrees: float = 0.0,
                 fill: tuple[int, int, int, int] = (0, 0, 0, 0)) \
        -> Image.Image:
    return img.rotate(float(degrees), resample=Image.BICUBIC,
                       fillcolor=fill)


def apply_roll(img: Image.Image, dx: int = 0, dy: int = 0) -> Image.Image:
    """Desplaza con envolvimiento (wrap), estilo glitch."""
    arr = np.roll(np.array(img), (int(dy), int(dx)), axis=(0, 1))
    return Image.fromarray(arr)


def apply_effect(img: Image.Image, effect: str, **params) -> Image.Image:
    """Aplica un efecto a una imagen (ver EFFECTS para el catálogo)."""
    if effect not in EFFECTS:
        raise ValueError(f"unknown effect: {effect}")
    fn, defaults = EFFECTS[effect]
    unknown = set(params) - set(defaults)
    if unknown:
        raise ValueError(
            f"unknown params for {effect}: {sorted(unknown)}; "
            f"allowed: {sorted(defaults)}")
    kwargs = {**defaults, **params}
    return fn(img, **kwargs)


#: nombre -> (función, params por defecto). Única fuente del catálogo.
EFFECTS: dict[str, tuple] = {
    # base
    "blur": (apply_blur, {"radius": 4.0}),
    "glow": (apply_glow, {"radius": 8.0, "intensity": 0.6}),
    "color": (apply_color, {"brightness": 1.0, "contrast": 1.0,
                            "saturation": 1.0}),
    "chroma_key": (apply_chroma_key, {"key_color": "#00ff00",
                                      "tolerance": 40.0, "softness": 10.0}),
    "vignette": (apply_vignette, {"amount": 0.5}),
    # distorsión
    "wave": (apply_distort_wave, {"amplitude": 12.0, "wavelength": 60.0,
                                  "phase": 0.0, "vertical": False}),
    "barrel": (apply_distort_barrel, {"strength": 0.3}),
    "swirl": (apply_distort_swirl, {"strength": 1.5}),
    # estilo / color
    "pixelate": (apply_pixelate, {"block": 12}),
    "mirror": (apply_mirror, {"axis": "horizontal"}),
    "noise": (apply_noise, {"amount": 25.0, "seed": 0}),
    "rgb_split": (apply_rgb_split, {"offset": 6}),
    "invert": (apply_invert, {}),
    "grayscale": (apply_grayscale, {}),
    "sepia": (apply_sepia, {}),
    "posterize": (apply_posterize, {"levels": 6}),
    "threshold": (apply_threshold, {"level": 128}),
    "duotone": (apply_duotone, {"dark": "#1a1a4d", "light": "#ffd700"}),
    "hue": (apply_hue, {"shift": 30.0}),
    "solarize": (apply_solarize, {"threshold": 128}),
    "sharpen": (apply_sharpen, {"amount": 150, "radius": 2.0}),
    "emboss": (apply_emboss, {}),
    "edge": (apply_edge, {}),
    "scanlines": (apply_scanlines, {"spacing": 4, "opacity": 0.4}),
    "zoom": (apply_zoom, {"factor": 1.5}),
    "rotate": (apply_rotate, {"degrees": 0.0}),
    "roll": (apply_roll, {"dx": 0, "dy": 0}),
}
