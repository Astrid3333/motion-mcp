import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from motion_mcp import keyframes, compose, effects, render, server


def _make_png(path, size=(200, 200), color=(255, 0, 0, 255)):
    Image.new("RGBA", size, color).save(path)


def _ffmpeg_ok() -> bool:
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        return False
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        return True
    except OSError:
        return False


FFMPEG_OK = _ffmpeg_ok()


def test_keyframes_number():
    kfs = [{"time": 0, "value": 0}, {"time": 1, "value": 100}]
    res = server.motion_keyframes(kfs, [0, 0.5, 1])
    assert res["ok"] is True
    assert res["values"] == [0, 50, 100]


def test_keyframes_tuple():
    kfs = [{"time": 0, "value": [0, 0]}, {"time": 1, "value": [100, 200]}]
    res = server.motion_keyframes(kfs, [0.5])
    assert res["values"][0] == [50.0, 100.0]


def test_apply_effect_blur(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _make_png(src)
    res = server.motion_apply_effect(str(src), "blur", str(out), radius=4)
    assert res["ok"] is True, res
    assert Path(out).is_file()


def test_add_mask_circle(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _make_png(src, color=(0, 255, 0, 255))
    res = server.motion_add_mask(str(src), "circle", str(out),
                                 center=[100, 100], radius=50)
    assert res["ok"] is True, res
    assert Path(out).is_file()
    img = Image.open(out).convert("RGBA")
    assert img.getpixel((100, 100))[3] == 255
    assert img.getpixel((0, 0))[3] == 0


def test_add_text(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _make_png(src)
    res = server.motion_add_text(str(src), "Hola", str(out),
                                 position=[10, 10], font_size=20)
    assert res["ok"] is True, res
    assert Path(out).is_file()


def test_compose_layers(tmp_path):
    bg = tmp_path / "bg.png"
    fg = tmp_path / "fg.png"
    _make_png(bg, size=(400, 300), color=(0, 0, 255, 255))
    _make_png(fg, size=(100, 100), color=(255, 255, 0, 255))
    out = tmp_path / "comp"
    spec = {
        "size": [400, 300],
        "fps": 10,
        "duration_seconds": 0.5,
        "background": "transparent",
        "layers": [
            {"source": str(bg), "position": [0, 0], "scale": 1, "opacity": 1},
            {"source": str(fg), "position": [150, 100], "scale": 1,
             "opacity": 1, "blend": "normal"},
        ],
    }
    res = compose.render_composition(spec, str(out))
    assert res["ok"] is True, res
    assert res["frame_count"] == 5
    assert Path(res["frames"][0]).is_file()


def test_compose_nested_keyframes(tmp_path):
    bg = tmp_path / "bg.png"
    _make_png(bg, size=(200, 200))
    out = tmp_path / "comp"
    spec = {
        "size": [200, 200], "fps": 4, "duration_seconds": 0.5,
        "background": "transparent",
        "layers": [
            {"source": str(bg), "position": [100, 100],
             "keyframes": {"opacity": [
                 {"time": 0, "value": 1.0}, {"time": 0.25, "value": 0.0}]}},
        ],
    }
    res = compose.render_composition(spec, str(out))
    assert res["ok"] is True, res
    assert res["frame_count"] == 2
    # primer frame opaco (fondo azul), último casi transparente (negro RGB)
    first = Image.open(res["frames"][0]).convert("RGB")
    last = Image.open(res["frames"][1]).convert("RGB")
    assert first.getpixel((100, 100)) == (255, 0, 0)
    assert last.getpixel((100, 100)) == (0, 0, 0)


def test_render_sequence(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(3):
        _make_png(frames / f"frame_{i+1:05d}.png", color=(i * 80, 0, 0, 255))
    out = tmp_path / "out.mp4"
    res = render.render_sequence(str(frames), str(out), fps=10)
    if not FFMPEG_OK:
        # entorno sin ffmpeg funcional: la tool debe responder con error claro
        assert res["ok"] is False, res
        assert "error" in res, res
        return
    assert res["ok"] is True, res
    assert Path(out).is_file()


def test_extract_frames(tmp_path):
    video = tmp_path / "in.mp4"
    frames_dir = tmp_path / "frames"
    # crear video de 1s a 10fps con frames de color
    frames_tmp = tmp_path / "src_frames"
    frames_tmp.mkdir()
    for i in range(10):
        _make_png(frames_tmp / f"frame_{i+1:05d}.png", color=(i * 20, 0, 0, 255))
    r = render.render_sequence(str(frames_tmp), str(video), fps=10)
    if not FFMPEG_OK:
        assert r["ok"] is False, r
        assert "error" in r, r
        res = render.extract_frames(str(video), str(frames_dir), fps=10)
        assert res["ok"] is False, res
        assert "error" in res, res
        return
    assert r["ok"] is True
    res = render.extract_frames(str(video), str(frames_dir), fps=10)
    assert res["ok"] is True, res
    assert res["frame_count"] == 10


def _half_half_png(path, size=(200, 200)):
    """Mitad izquierda roja, derecha azul (para detectar desplazamiento)."""
    img = Image.new("RGBA", size, (0, 0, 255, 255))
    for x in range(size[0] // 2):
        for y in range(size[1]):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(path)


def test_distort_wave(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _half_half_png(src)
    res = server.motion_apply_effect(str(src), "wave", str(out),
                                     amplitude=15, wavelength=50,
                                     vertical=True)
    assert res["ok"] is True, res
    orig = Image.open(src).convert("RGB")
    got = Image.open(out).convert("RGB")
    # vertical=True desplaza en x: filas con seno alto cruzan la frontera
    assert any(got.getpixel((x, y)) != orig.getpixel((x, y))
               for x in (95, 100, 105) for y in range(0, 200, 7))
    assert got.size == orig.size


def test_distort_barrel(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    # cuadrado blanco centrado sobre negro: el barril desplaza sus bordes
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    for x in range(60, 140):
        for y in range(60, 140):
            img.putpixel((x, y), (255, 255, 255, 255))
    img.save(src)
    res = server.motion_apply_effect(str(src), "barrel", str(out),
                                     strength=0.5)
    assert res["ok"] is True, res
    orig = Image.open(src).convert("RGB")
    got = Image.open(out).convert("RGB")
    # el borde del cuadrado se curva: algún píxel del borde cambia
    assert any(got.getpixel((x, y)) != orig.getpixel((x, y))
               for x in (61, 63, 137, 139) for y in range(70, 130, 5))
    assert got.size == orig.size


def test_distort_swirl(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _half_half_png(src)
    res = server.motion_apply_effect(str(src), "swirl", str(out),
                                     strength=2.0)
    assert res["ok"] is True, res
    orig = Image.open(src).convert("RGB")
    got = Image.open(out).convert("RGB")
    # el remolino rota la región central
    assert any(got.getpixel((x, y)) != orig.getpixel((x, y))
               for x in range(70, 130, 5) for y in range(70, 130, 5))
    assert got.size == orig.size


def test_unknown_effect(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    _make_png(src)
    res = server.motion_apply_effect(str(src), "nope", str(out))
    assert res["ok"] is False, res
    assert "unknown effect" in res["error"]


def test_retime_blend_slowmo(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(4):
        _make_png(frames / f"frame_{i+1:05d}.png",
                  color=(i * 60, 0, 0, 255))
    out = tmp_path / "slow"
    res = server.motion_retime(str(frames), str(out), speed=0.5,
                               mode="blend")
    assert res["ok"] is True, res
    assert res["input_frames"] == 4
    assert res["frame_count"] == 7  # (4-1)//0.5 + 1
    assert res["duration_multiplier"] == 2.0
    # frame intermedio i=1 → t=0.5: blend 50/50 entre colores 0 y 60
    mid = Image.open(Path(out) / "frame_00001.png").convert("RGB")
    assert mid.getpixel((5, 5)) == (30, 0, 0)
    # el primer frame es idéntico al original
    first = Image.open(Path(out) / "frame_00000.png").convert("RGB")
    assert first.getpixel((5, 5)) == (0, 0, 0)


def test_retime_duplicate_and_errors(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(4):
        _make_png(frames / f"frame_{i+1:05d}.png",
                  color=(i * 60, 0, 0, 255))
    out = tmp_path / "slow2"
    res = server.motion_retime(str(frames), str(out), speed=0.5,
                               mode="duplicate")
    assert res["ok"] is True, res
    assert res["frame_count"] == 7
    mid = Image.open(Path(out) / "frame_00001.png").convert("RGB")
    assert mid.getpixel((5, 5)) == (0, 0, 0)  # t=0.5 → frame 0 exacto

    bad = server.motion_retime(str(frames), str(tmp_path / "x"), speed=0)
    assert bad["ok"] is False and "speed" in bad["error"]
    bad2 = server.motion_retime(str(frames), str(tmp_path / "y"),
                                mode="nope")
    assert bad2["ok"] is False and "mode" in bad2["error"]
    empty = server.motion_retime(str(tmp_path / "missing"),
                                 str(tmp_path / "z"))
    assert empty["ok"] is False and "frames" in empty["error"]


def test_list_effects_catalog():
    res = server.motion_list_effects()
    assert res["ok"] is True
    assert res["count"] == 27
    for name in ("blur", "wave", "pixelate", "duotone", "roll"):
        assert name in res["effects"]
    # cada entrada tiene sus defaults
    assert res["effects"]["pixelate"] == {"block": 12}


def test_all_effects_apply(tmp_path):
    """Los 27 efectos corren con defaults y preservan el tamaño."""
    import pytest
    src = tmp_path / "in.png"
    _make_png(src, color=(180, 90, 40, 255))
    names = sorted(effects.EFFECTS)
    assert len(names) == 27
    for name in names:
        out = tmp_path / f"out_{name}.png"
        res = server.motion_apply_effect(str(src), name, str(out))
        assert res["ok"] is True, (name, res)
        assert out.is_file(), name
        assert Image.open(out).size == (200, 200), name


def test_effect_semantics(tmp_path):
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    # invert: rojo -> cian
    _make_png(src, color=(255, 0, 0, 255))
    server.motion_apply_effect(str(src), "invert", str(out))
    assert Image.open(out).convert("RGB").getpixel((10, 10)) == (0, 255, 255)
    # grayscale: rojo -> gris 76 (0.299*255)
    server.motion_apply_effect(str(src), "grayscale", str(out))
    g = Image.open(out).convert("RGB").getpixel((10, 10))
    assert g[0] == g[1] == g[2] and abs(g[0] - 76) <= 1
    # mirror horizontal: mitad izq. roja vuelve a la derecha
    img = Image.new("RGBA", (200, 200), (0, 0, 255, 255))
    for x in range(100):
        for y in range(200):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(src)
    server.motion_apply_effect(str(src), "mirror", str(out))
    got = Image.open(out).convert("RGB")
    assert got.getpixel((10, 10)) == (0, 0, 255)
    assert got.getpixel((190, 10)) == (255, 0, 0)
    # noise determinista con el mismo seed
    _make_png(src, color=(100, 100, 100, 255))
    server.motion_apply_effect(str(src), "noise", str(out), seed=42,
                               amount=40)
    a = Path(out).read_bytes()
    server.motion_apply_effect(str(src), "noise", str(out), seed=42,
                               amount=40)
    assert Path(out).read_bytes() == a
    # threshold: negro/blanco puros
    _make_png(src, color=(200, 200, 200, 255))
    server.motion_apply_effect(str(src), "threshold", str(out))
    px = Image.open(out).convert("RGB").getpixel((10, 10))
    assert px == (255, 255, 255)


def test_effect_unknown_param(tmp_path):
    src = tmp_path / "in.png"
    _make_png(src)
    res = server.motion_apply_effect(str(src), "blur", str(tmp_path / "o.png"),
                                     bogus=1)
    assert res["ok"] is False
    assert "unknown params" in res["error"]
    assert "allowed" in res["error"]


def test_chroma_key_semantics(tmp_path):
    """Fondo verde transparente, sujeto azul opaco (y sin overflow NaN)."""
    img = Image.new("RGBA", (200, 200), (0, 255, 0, 255))
    for x in range(60, 140):
        for y in range(60, 140):
            img.putpixel((x, y), (0, 0, 255, 255))
    src = tmp_path / "in.png"
    out = tmp_path / "out.png"
    img.save(src)
    res = server.motion_apply_effect(str(src), "chroma_key", str(out))
    assert res["ok"] is True, res
    got = Image.open(out)
    assert got.getpixel((5, 5))[3] == 0        # fondo verde -> transparente
    assert got.getpixel((100, 100))[3] == 255  # sujeto azul -> opaco
    assert got.getpixel((100, 100))[:3] == (0, 0, 255)
