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
