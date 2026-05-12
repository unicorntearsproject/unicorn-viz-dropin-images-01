"""Image Showcase drop-in effect.

Loads still images from one directory and presents them as a full-screen,
audio-reactive slideshow with slow Ken Burns motion, beat-aware crossfades,
and ten rotating presentation styles.

Directory selection policy:
- By default, images are loaded from `drop-ins/images-01/images/`.
- If `[effects.ImageShowcase].image_dir` is set, that path is used instead.
- The configured path is an override, not an additional search path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from random import shuffle
from typing import NamedTuple

import moderngl
from PIL import Image

from unicornviz.effects.base import BaseEffect, AudioData

log = logging.getLogger(__name__)


class _StylePreset(NamedTuple):
    name: str
    mix_shape: str
    zoom_a: float
    zoom_b: float
    drift_a: float
    drift_b: float
    color_mix: float
    palette_spin: float
    vignette: float
    grain: float


_STYLE_PRESETS: list[_StylePreset] = [
    _StylePreset('soft', 'smoothstep', 0.06, 0.06, 0.10, 1.40, 0.06, 0.05, 0.20, 0.00),
    _StylePreset('pulse', 'smoothstep', 0.08, 0.05, 0.20, 1.60, 0.10, 0.08, 0.24, 0.02),
    _StylePreset('drift', 'linear', 0.04, 0.08, 0.28, 1.05, 0.05, 0.03, 0.18, 0.01),
    _StylePreset('flash', 'hard', 0.05, 0.10, 0.40, 1.85, 0.12, 0.10, 0.22, 0.03),
    _StylePreset('cinema', 'smoothstep', 0.03, 0.04, 0.08, 1.10, 0.04, 0.02, 0.28, 0.04),
    _StylePreset('halo', 'smoothstep', 0.07, 0.07, 0.50, 1.30, 0.09, 0.12, 0.25, 0.05),
    _StylePreset('split', 'split', 0.06, 0.06, 0.65, 1.75, 0.08, 0.07, 0.21, 0.02),
    _StylePreset('glow', 'noise', 0.05, 0.05, 0.18, 1.95, 0.10, 0.09, 0.23, 0.06),
    _StylePreset('dream', 'smoothstep', 0.09, 0.09, 0.12, 1.25, 0.14, 0.14, 0.30, 0.05),
    _StylePreset('nervous', 'noise', 0.10, 0.11, 0.55, 2.20, 0.16, 0.11, 0.27, 0.08),
]

_VERT = """
#version 330
in vec2 in_vert;
out vec2 v_uv;
void main() {
    v_uv = in_vert * 0.5 + 0.5;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

_FRAG = """
#version 330
uniform sampler2D texA;
uniform sampler2D texB;
uniform vec2 texASize;
uniform vec2 texBSize;
uniform vec2 iResolution;
uniform float iTime;
uniform float iBass;
uniform float iMid;
uniform float iTreble;
uniform float iMix;
uniform int iStyle;
in vec2 v_uv;
out vec4 fragColor;

vec3 palette(float t) {
    vec3 a = vec3(0.5);
    vec3 b = vec3(0.5);
    vec3 c = vec3(1.0);
    vec3 d = vec3(0.18, 0.10, 0.24);
    return a + b * cos(6.28318 * (c * t + d));
}

vec2 coverUV(vec2 uv, vec2 texSize, vec2 outSize) {
    float inAspect = texSize.x / max(texSize.y, 1.0);
    float outAspect = outSize.x / max(outSize.y, 1.0);
    vec2 st = uv;
    if (inAspect > outAspect) {
        float s = outAspect / inAspect;
        st.x = (uv.x - 0.5) * s + 0.5;
    } else {
        float s = inAspect / outAspect;
        st.y = (uv.y - 0.5) * s + 0.5;
    }
    return st;
}

vec3 sampleSlide(sampler2D tex, vec2 uv, vec2 texSize, vec2 outSize, float t, float drift, float zoom) {
    vec2 cuv = coverUV(uv, texSize, outSize);
    cuv = (cuv - 0.5) / zoom + 0.5;
    cuv += vec2(sin(t * 0.23 + drift), cos(t * 0.19 + drift)) * 0.03;
    return texture(tex, clamp(cuv, 0.0, 1.0)).rgb;
}

float styleBlend(float mixValue, vec2 uv, float noiseSeed) {
    if (iStyle == 0) {
        return smoothstep(0.0, 1.0, mixValue);
    } else if (iStyle == 1) {
        return smoothstep(0.08, 0.92, mixValue + sin(uv.y * 10.0) * 0.04);
    } else if (iStyle == 2) {
        return clamp(mixValue, 0.0, 1.0);
    } else if (iStyle == 3) {
        return step(0.5, mixValue);
    } else if (iStyle == 4) {
        return smoothstep(0.0, 1.0, mixValue * mixValue);
    } else if (iStyle == 5) {
        return smoothstep(0.12, 0.88, mixValue + 0.06 * sin(uv.x * 18.0));
    } else if (iStyle == 6) {
        return smoothstep(0.0, 1.0, mixValue + (noiseSeed - 0.5) * 0.06);
    } else if (iStyle == 7) {
        return smoothstep(0.0, 1.0, mixValue + 0.08 * sin(uv.x * 6.0 + uv.y * 4.0));
    } else if (iStyle == 8) {
        return smoothstep(0.0, 1.0, mixValue * 0.85 + 0.08 * sin(uv.y * 8.0));
    }
    return smoothstep(0.0, 1.0, mixValue + (noiseSeed - 0.5) * 0.12);
}

void main() {
    vec2 uv = v_uv;
    float t = iTime;
    float stylePhase = float(iStyle) / 10.0;

    float zoomA = 1.0 + 0.04 * sin(t * (0.21 + stylePhase * 0.03)) + iBass * 0.04;
    float zoomB = 1.0 + 0.04 * cos(t * (0.17 + stylePhase * 0.02)) + iTreble * 0.04;

    vec3 a = sampleSlide(texA, uv, texASize, iResolution, t, 0.1, zoomA);
    vec3 b = sampleSlide(texB, uv, texBSize, iResolution, t, 1.4, zoomB);

    float wipe = smoothstep(0.0, 1.0, iMix);
    float noise = fract(sin(dot(uv * 200.0, vec2(12.9898, 78.233))) * 43758.5453);
    float blend = styleBlend(wipe, uv, noise);

    vec3 col = mix(a, b, blend);

    col = mix(col, col * palette(t * (0.05 + stylePhase * 0.03) + uv.y * 0.25), 0.06 + iMid * 0.07);

    vec2 p = uv * 2.0 - 1.0;
    float vig = 1.0 - dot(p, p) * (0.16 + stylePhase * 0.08);
    col *= vig;

    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
"""


class ImageShowcase(BaseEffect):
    """Audio-reactive still-image slideshow using a single resolved image directory."""

    NAME = 'Image Showcase'
    AUTHOR = 'unicorn-viz drop-in'
    TAGS = ['images', 'audio', 'slideshow', 'drop-in']

    def _init(self) -> None:
        self.parameters = {
            'speed': 1.0,
            'mix_time': 10.0,
        }

        self._prog = self._make_program(_VERT, _FRAG)
        self._vao, self._vbo = self._fullscreen_quad(self._prog)

        self._textures: list[moderngl.Texture] = []
        self._sizes: list[tuple[int, int]] = []
        self._current = 0
        self._next = 0
        self._timer = 0.0
        self._mix = 0.0
        self._bass = 0.0
        self._mid = 0.0
        self._treble = 0.0
        self._style_index = 0
        self._style_order: list[int] = list(range(len(_STYLE_PRESETS)))

        self._load_images()

    def _image_dir(self) -> Path:
        override = str(self.config.get('image_dir', '')).strip()
        if override:
            return Path(override).expanduser()
        return Path(__file__).resolve().parent / 'images'

    def _load_images(self) -> None:
        image_dir = self._image_dir()
        exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tga'}
        files: list[Path] = []
        if image_dir.exists():
            files = sorted(
                path for path in image_dir.rglob('*')
                if path.is_file() and path.suffix.lower() in exts
            )

        if not files:
            log.warning('ImageShowcase: no images found in %s', image_dir)
            tex = self.ctx.texture((1, 1), 3, bytes([255, 0, 255]))
            tex.filter = moderngl.LINEAR, moderngl.LINEAR
            self._textures = [tex]
            self._sizes = [(1, 1)]
            self._current = 0
            self._next = 0
            return

        shuffle(files)

        for path in files:
            try:
                img = Image.open(path).convert('RGB').transpose(Image.FLIP_TOP_BOTTOM)
                tex = self.ctx.texture(img.size, 3, img.tobytes())
                tex.filter = moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR
                tex.build_mipmaps()
                self._textures.append(tex)
                self._sizes.append(img.size)
            except Exception as exc:
                log.warning('ImageShowcase: failed to load %s: %s', path, exc)

        if not self._textures:
            tex = self.ctx.texture((1, 1), 3, bytes([255, 0, 255]))
            tex.filter = moderngl.LINEAR, moderngl.LINEAR
            self._textures = [tex]
            self._sizes = [(1, 1)]
        self._current = 0
        self._next = 1 if len(self._textures) > 1 else 0
        self._style_index = 0
        self._style_order = list(range(len(_STYLE_PRESETS)))
        shuffle(self._style_order)
        log.info('ImageShowcase: loaded %d images from %s', len(self._textures), image_dir)

    def update(self, dt: float, audio: AudioData) -> None:
        super().update(dt, audio)
        self._bass = audio.bass
        self._mid = audio.mid
        self._treble = audio.treble

        self._timer += dt * max(0.1, self.parameters['speed'])
        mix_time = max(1.0, self.parameters['mix_time'])
        phase = self._timer / mix_time

        # Beats can encourage slightly faster transitions without hard-cuts.
        if audio.beat:
            phase = min(1.0, phase + 0.12)

        if phase >= 1.0:
            self._timer = 0.0
            self._current = self._next
            self._next = (self._next + 1) % len(self._textures)
            self._style_index = (self._style_index + 1) % len(self._style_order)
            if self._style_index == 0:
                shuffle(self._style_order)
            self._mix = 0.0
        else:
            self._mix = phase

    def render(self) -> None:
        tex_a = self._textures[self._current]
        tex_b = self._textures[self._next]
        tex_a.use(location=0)
        tex_b.use(location=1)

        def set_uniform(name: str, value) -> None:
            try:
                self._prog[name].value = value
            except KeyError:
                pass

        style = _STYLE_PRESETS[self._style_order[self._style_index]]

        set_uniform('texA', 0)
        set_uniform('texB', 1)
        set_uniform('texASize', tuple(float(v) for v in self._sizes[self._current]))
        set_uniform('texBSize', tuple(float(v) for v in self._sizes[self._next]))
        set_uniform('iResolution', (float(self.width), float(self.height)))
        set_uniform('iTime', self.time)
        set_uniform('iBass', self._bass)
        set_uniform('iMid', self._mid)
        set_uniform('iTreble', self._treble)
        set_uniform('iMix', self._mix)
        set_uniform('iStyle', int(self._style_order[self._style_index]))

        self._vao.render(moderngl.TRIANGLE_STRIP)

    def destroy(self) -> None:
        for tex in self._textures:
            tex.release()
        self._vao.release()
        self._vbo.release()
        self._prog.release()
