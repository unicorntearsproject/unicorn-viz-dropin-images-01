# images-01 — Image Showcase

A drop-in effect for [unicorn-viz](https://github.com/iDoMeteor/unicorn-viz).

## Description

Loads still images from one directory and presents them as a full-screen,
audio-reactive slideshow with Ken Burns motion, beat-aware crossfades, and
subtle colour grading.

By default, it reads bundled images from `drop-ins/images-01/images/`.
If `[effects.ImageShowcase].image_dir` is set, that path is used instead.
The configured path is an override, not an additional search path.

## Visual Features

- Slow pan/zoom movement on each image
- Soft beat-aware crossfades between slides
- Mild audio-reactive colour grade and vignette
- Recursive loading from one image directory

## Audio Reactivity

| Signal  | Effect |
|---------|--------|
| `bass`  | Zoom pulse |
| `mid`   | Colour grade intensity |
| `beat`  | Slightly accelerates transition phase |

## Config

```toml
[effects.ImageShowcase]
image_dir = ""    # override path; empty = bundled images folder
speed = 1.0
mix_time = 8.0
```

## Adding Images

Put your images in `drop-ins/images-01/images/` to use the bundled folder,
or point `image_dir` at your own folder.

Supported formats: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tga`

## Hotkeys

No dedicated hotkeys. Standard `+` / `-` adjust `speed`.

## Tags

`images` · `audio` · `slideshow` · `drop-in`
