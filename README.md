# motion-mcp

MCP server de motion graphics al estilo After Effects: composición por capas,
keyframes, catálogo de **27 efectos** (base, distorsión, estilo, color/valor),
máscaras alpha, texto animado, cámara lenta (retime) y render de frames a
video con ffmpeg.

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
| `motion_list_effects` | Catálogo de los 27 efectos con parámetros y defaults |
| `motion_apply_effect` | Aplica un efecto (ver catálogo abajo) |
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

## Catálogo de efectos (27)

| Grupo | Efecto | Params (default) |
| --- | --- | --- |
| base | `blur` | `radius` (4.0) |
| base | `glow` | `radius` (8.0), `intensity` (0.6) |
| base | `color` | `brightness`, `contrast`, `saturation` (1.0) |
| base | `chroma_key` | `key_color` (#00ff00), `tolerance` (40), `softness` (10) |
| base | `vignette` | `amount` (0.5) |
| distorsión | `wave` | `amplitude` (12), `wavelength` (60), `phase` (0), `vertical` |
| distorsión | `barrel` | `strength` (0.3) |
| distorsión | `swirl` | `strength` (1.5) |
| estilo | `pixelate` | `block` (12) |
| estilo | `mirror` | `axis` (horizontal) |
| estilo | `noise` | `amount` (25), `seed` (0) |
| estilo | `rgb_split` | `offset` (6) |
| estilo | `scanlines` | `spacing` (4), `opacity` (0.4) |
| estilo | `zoom` | `factor` (1.5) |
| estilo | `rotate` | `degrees` (0) |
| estilo | `roll` | `dx` (0), `dy` (0) — wrap/glitch |
| color | `invert` | — |
| color | `grayscale` | — |
| color | `sepia` | — |
| color | `posterize` | `levels` (6) |
| color | `threshold` | `level` (128) |
| color | `duotone` | `dark` (#1a1a4d), `light` (#ffd700) |
| color | `hue` | `shift` (30°) |
| color | `solarize` | `threshold` (128) |
| filtro | `sharpen` | `amount` (150), `radius` (2.0) |
| filtro | `emboss` | — |
| filtro | `edge` | — |

`noise` es reproducible (mismo `seed` ⇒ mismos píxeles). Parámetro desconocido
→ error con la lista de permitidos.

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
