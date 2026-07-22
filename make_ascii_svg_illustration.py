#!/usr/bin/env python3
"""
Illustration-mode ASCII portrait generator.
For flat-shaded comic/illustration art instead of photos.
Uses edge detection + flat-color background removal instead of
rembg (ML photo segmentation) + CLAHE (photographic shadow contrast).
"""
import sys
import numpy as np
import cv2
from PIL import Image

RAMP = " .`:-=+*cs#%@"
COLS = 130
GAMMA = 1.0
BG_TOLERANCE = 40      # how close to corner color counts as "background". Raise if bg isn't fully removed, lower if it eats into the subject
EDGE_LOW = 40           # Canny low threshold. Lower = more faint lines detected
EDGE_HIGH = 120         # Canny high threshold
LINE_WEIGHT = 2         # how many px to dilate edges (thicker = bolder linework)
CROP_BOTTOM = 0.0
FG_LIGHT = "#6e7681"
FG_DARK = "#c9d1d9"
CHAR_W = 7.74
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.09

def remove_flat_background(img_rgb, tol=BG_TOLERANCE):
    """Removes a flat/uniform background by sampling the 4 corners."""
    arr = np.array(img_rgb).astype(float)
    h, w, _ = arr.shape
    corners = np.array([arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1]])
    bg_color = corners.mean(axis=0)
    dist = np.sqrt(((arr - bg_color) ** 2).sum(axis=2))
    mask_bg = dist < tol
    return mask_bg

def prep(path):
    src = Image.open(path).convert("RGB")
    arr = np.array(src)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Background removal (flat-color based, not ML)
    bg_mask = remove_flat_background(src)

    # Edge detection for linework
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, EDGE_LOW, EDGE_HIGH)
    if LINE_WEIGHT > 0:
        kernel = np.ones((LINE_WEIGHT, LINE_WEIGHT), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

    # Build final tone map:
    # - background -> white (255, blank)
    # - edges -> black (0, darkest char)
    # - flat fill areas -> light-mid grey, so shapes still read as filled, not just outlines
    out = np.full_like(gray, 235)          # default: light fill tone
    out[edges > 0] = 0                      # edges: darkest
    out[bg_mask] = 255                      # background: blank

    return Image.fromarray(out)

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