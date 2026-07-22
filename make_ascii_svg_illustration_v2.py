#!/usr/bin/env python3
"""
Illustration-mode ASCII portrait generator, v2.
Flood-fill background removal (handles textured/patterned backgrounds)
+ posterized tone levels for depth (uses the comic's actual flat color
blocks as shading, instead of a single flat fill tone).
"""
import sys
import numpy as np
import cv2
from PIL import Image

RAMP = " .`:-=+*cs#%@"
COLS = 130
GAMMA = 1.0

# Background removal (flood fill from corners)
FLOOD_TOLERANCE = 25    # color similarity tolerance for flood fill. Raise if bg isn't fully cleared, lower if it eats into the subject

# Edge detection (linework)
EDGE_LOW = 40
EDGE_HIGH = 120
LINE_WEIGHT = 2

# Depth / posterization
POSTER_LEVELS = 5       # number of distinct tone bands pulled from the flat color fills. 3-6 is the useful range

CROP_BOTTOM = 0.0
FG_LIGHT = "#6e7681"
FG_DARK = "#c9d1d9"
CHAR_W = 7.74
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.09

def remove_background_floodfill(img_rgb, tol=FLOOD_TOLERANCE):
    """Flood-fills from all 4 corners + edge midpoints so only background
    CONNECTED to the border gets cleared -- textured/patterned backgrounds
    included, without eating into the subject."""
    arr = np.array(img_rgb)
    h, w, _ = arr.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flood_mask = np.zeros((h, w), np.uint8)

    seeds = [
        (0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
        (w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1),
    ]
    work = arr.copy()
    combined = np.zeros((h, w), bool)
    for sx, sy in seeds:
        if combined[sy, sx]:
            continue
        temp_mask = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(
            work, temp_mask, (sx, sy), 0,
            loDiff=(tol, tol, tol), upDiff=(tol, tol, tol),
            flags=4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
        )
        combined |= temp_mask[1:-1, 1:-1] > 0
    return combined

def prep(path):
    src = Image.open(path).convert("RGB")
    arr = np.array(src)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    bg_mask = remove_background_floodfill(src)

    # Edges (linework)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, EDGE_LOW, EDGE_HIGH)
    if LINE_WEIGHT > 0:
        kernel = np.ones((LINE_WEIGHT, LINE_WEIGHT), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

    # Depth: posterize the actual luminance into N bands so flat color
    # blocks (jacket vs skin vs shirt) render as distinct tones
    smoothed = cv2.bilateralFilter(gray, 9, 60, 60)
    levels = np.linspace(60, 235, POSTER_LEVELS)  # keep off pure black/white, edges own black, bg owns white
    band_width = 255 / POSTER_LEVELS
    banded = (smoothed // band_width).astype(np.uint8)
    banded = np.clip(banded, 0, POSTER_LEVELS - 1)
    poster = levels[banded]

    out = poster.copy()
    out[edges > 0] = 0        # linework: darkest
    out[bg_mask] = 255        # background: blank

    return Image.fromarray(out.astype(np.uint8))

def to_lines(img, cols=COLS, gamma=GAMMA):
    w, h = img.size
    if CROP_BOTTOM:
        img = img.crop((0, 0, w, int(h * (1 - CROP_BOTTOM))))
        w, h = img.size
    rows = int(cols * (h / w) * 0.48)
    img = img.resize((cols, rows), Image.LANCZOS)
    px = list(img.getdata())
    n = len(RAMP)
    out = []
    for r in range(rows):
        line = "".join(
            RAMP[min(n - 1, int((1 - px[r * cols + c] / 255.0) ** gamma * n))]
            for c in range(cols)
        )
        out.append(line.rstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out

def build_svg(lines, out_path, cols=COLS):
    pad = 14
    width = int(cols * CHAR_W + pad * 2)
    height = len(lines) * LINE_H + pad * 2
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        f'<style>.a{{fill:{FG_LIGHT}}}'
        f'@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}</style>'
    ]
    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append(
            f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" height="{LINE_H}" width="0">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/></rect></clipPath>'
        )
        p.append(
            f'<g clip-path="url(#c{i})"><text xml:space="preserve" x="{pad}" '
            f'y="{y + 11.2:.1f}" class="a" font-size="{FONT_SIZE}">{safe}</text></g>'
        )
        p.append(
            f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">'
            f'<animate attributeName="x" from="{pad}" to="{pad + w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
            f'<set attributeName="opacity" to="0" begin="{end}"/></rect>'
        )
    p.append("</svg>")
    open(out_path, "w").write("".join(p))
    return out_path

if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else "ascii.svg"
    lines = to_lines(prep(src))
    print("\n".join(lines))
    build_svg(lines, dst)
    print(f"\nwrote {dst}  ({len(lines)} rows)")