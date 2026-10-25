# motion-mcp

MCP server de motion graphics al estilo After Effects: composición por capas,
keyframes, efectos (blur/glow/color/chroma-key/vignette + distorsión
wave/barrel/swirl), máscaras alpha, texto animado, cámara lenta (retime) y
render de frames a video con ffmpeg.

## Instalación

```bash
cd motion-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests -q
```

Requisitos del sistema: `ffmpeg`, `ffprobe` y `convert` (ImageMagick).
Dependencias Python: `Pillow`, `numpy`.

Registrado en `opencode.json` del workbench (sección `mcp`, `enabled: true`).

## Herramientas

| Tool | Descripción |
| --- | --- |
| `motion_compose_layers` | Composición por capas con posición, escala, rotación, opacidad, blend y keyframes; render a frames PNG |
| `motion_keyframes` | Interpola keyframes [{time, value}] en tiempos dados (números o tuplas) |
| `motion_apply_effect` | Efecto sobre imagen: blur, glow, color, chroma_key, vignette, **wave, barrel, swirl** (distorsión) |
| `motion_add_mask` | Máscara alpha: circle, rect o from_image (otra imagen como máscara) |
| `motion_add_text` | Texto sobre imagen (posición, tamaño, color, ancla) |
| `motion_retime` | **Cámara lenta/rápida**: re-muestrea la secuencia (speed 0.5 = 2x lento; modes duplicate/blend) |
| `motion_render_sequence` | Secuencia de frames PNG -> video MP4 (ffmpeg) |
| `motion_extract_frames` | Video -> frames PNG numerados (ffmpeg) |

## Uso típico

1. `motion_extract_frames(video, output_dir)` -> frames
2. `motion_compose_layers({size, fps, duration_seconds, layers}, output_dir)` -> frames compuestos
3. `motion_apply_effect(frame, "glow", out, radius=8, intensity=0.6)`
4. `motion_add_text(frame, "Título", out, position=[50, 50], font_size=40)`
5. `motion_render_sequence(frames_dir, output.mp4, fps=30)`

Cámara lenta (distorsión aplicada a cada frame + retime 2x):

```python
motion_apply_effect(frame, "wave", out, amplitude=10, wavelength=70, vertical=True)
motion_retime(frames_dir, slow_dir, speed=0.5, mode="blend")   # 1s -> 2s
motion_render_sequence(slow_dir, "slow.mp4", fps=30)            # mismo fps
```

Parámetros de distorsión:
- `wave`: `amplitude` (px), `wavelength` (px), `phase` (rad), `vertical` (bool)
- `barrel`: `strength` (>0 ojo de pez, <0 cojín), default 0.3
- `swirl`: `strength` (radianes máx. en el centro), default 1.5

Ejemplo de capa con keyframes:

```json
{
  "size": [1920, 1080],
  "fps": 30,
  "duration_seconds": 3,
  "background": "#000000",
  "layers": [
    {
      "source": "logo.png",
      "position": [{"time": 0, "value": [100, 100]},
                   {"time": 2, "value": [900, 500]}],
      "scale": [{"time": 0, "value": 0.5}, {"time": 2, "value": 1.2}],
      "opacity": 1,
      "blend": "normal"
    }
  ]
}
```
