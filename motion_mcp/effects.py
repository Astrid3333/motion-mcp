"""Image effects: blur, glow, color grading, chroma key, vignette."""

from __future__ import annotations

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
    import numpy as np
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
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2, w / 2
    d = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    v = np.clip(1 - d * amount, 0, 1)
    mask = Image.fromarray((v * 255).astype(np.uint8), mode="L")
    darkened = ImageEnhance.Brightness(img).enhance(1 - amount * 0.6)
    out = Image.composite(darkened, img, mask)
    return out


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
    raise ValueError(f"unknown effect: {effect}")
