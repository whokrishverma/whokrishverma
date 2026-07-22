#!/usr/bin/env python3
"""
Illustration-mode ASCII portrait generator, v4.
Uses GrabCut (a rough bounding box around the subject + iterative
refinement) for foreground extraction -- far more reliable on a single
stylized image than automatic full-frame background detection.
"""
import sys
import numpy as np
import cv2
from PIL import Image

RAMP = " .`:-=+*cs#%@"
COLS = 130
GAMMA = 1.0

# GrabCut: rough box around the subject as (x, y, width, height) in pixels.
# Doesn't need to be precise -- just needs to contain the subject with a
# bit of margin, and exclude other objects (like a prop) if possible.
# Set to None to auto-use the full image (less reliable).
SUBJECT_BOX = (25, 25, 420, 400)  # (x, y, width, height) -- see instructions for how to set this
GRABCUT_ITERS = 8

# Edge detection (linework)
EDGE_LOW = 40
EDGE_HIGH = 120
LINE_WEIGHT = 1

POSTER_LEVELS = 6

CROP_BOTTOM = 0.0
FG_LIGHT = "#6e7681"
FG_DARK = "#c9d1d9"
CHAR_W = 7.74
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.09

def segment_subject_mask(img_rgb, box=None):
    arr = np.array(img_rgb)
    h, w, _ = arr.shape
    if box is None:
        box = (int(w * 0.03), int(h * 0.03), int(w * 0.94), int(h * 0.94))

    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    cv2.grabCut(arr, mask, box, bgd_model, fgd_model, GRABCUT_ITERS, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    kernel = np.ones((5, 5), np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)

    num_labels, comp_labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if num_labels > 1:
        largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        fg = (comp_labels == largest).astype(np.uint8) * 255

    return fg > 0

def prep(path):
    src = Image.open(path).convert("RGB")
    arr = np.array(src)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    subject_mask = segment_subject_mask(src, SUBJECT_BOX)

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, EDGE_LOW, EDGE_HIGH)
    if LINE_WEIGHT > 0:
        kernel = np.ones((LINE_WEIGHT, LINE_WEIGHT), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
    edges[~subject_mask] = 0

    smoothed = cv2.bilateralFilter(gray, 9, 60, 60)
    band_width = 255 / POSTER_LEVELS
    banded = np.clip((smoothed // band_width).astype(np.uint8), 0, POSTER_LEVELS - 1)
    levels = np.linspace(20, 245, POSTER_LEVELS)
    poster = levels[banded]

    out = np.full_like(gray, 255)
    out[subject_mask] = poster[subject_mask]
    out[edges > 0] = 0

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