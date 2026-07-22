#!/usr/bin/env python3
"""
Illustration-mode ASCII portrait generator, v5.
Same flood-fill background removal + posterized tone pipeline as v4, but the
SVG is now wrapped in a macOS-style terminal window (title bar, traffic-light
dots, status bar with a "whoami" line + blinking cursor) instead of a bare
canvas -- same visual chrome as the Andrew6rant-style reference.
"""
import sys
import numpy as np
import cv2
from PIL import Image

RAMP = " .`:-'+*cs#%@"
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

# ---- terminal window chrome ------------------------------------------------
USERNAME = "you"                       # shown in title + status bar, e.g. "avi"
COMMAND = "./portrait.sh"              # shown in the title bar prompt
BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
FG_LIGHT = "#6e7681"
FG_DARK = "#c9d1d9"
INK = FG_DARK                          # single ascii ink color, matches reference

PAD = 20
TITLEBAR_H = 30
STATUS_H = 44

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

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, EDGE_LOW, EDGE_HIGH)
    if LINE_WEIGHT > 0:
        kernel = np.ones((LINE_WEIGHT, LINE_WEIGHT), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

    smoothed = cv2.bilateralFilter(gray, 9, 60, 60)
    levels = np.linspace(60, 235, POSTER_LEVELS)
    band_width = 255 / POSTER_LEVELS
    banded = (smoothed // band_width).astype(np.uint8)
    banded = np.clip(banded, 0, POSTER_LEVELS - 1)
    poster = levels[banded]

    out = poster.copy()
    out[edges > 0] = 0
    out[bg_mask] = 255

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
    art_w = int(cols * CHAR_W)
    art_h = len(lines) * LINE_H
    width = art_w + PAD * 2
    height = TITLEBAR_H + art_h + STATUS_H + int(PAD * 0.35)
    art_top = TITLEBAR_H + PAD * 0.35

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        f'<style>.a{{fill:{FG_LIGHT}}}'
        f'@media(prefers-color-scheme:dark){{.a{{fill:{FG_DARK}}}}}</style>',
        '<defs>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        f'</linearGradient></defs>',
    ]

    # window body + border
    p.append(f'<rect width="{width}" height="{height}" rx="12" fill="url(#bg)"/>')
    p.append(f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

    # title bar: traffic-light dots + centered command prompt
    p.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{width}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    p.append(f'<text x="{width/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">{USERNAME}@github: ~$ {COMMAND}</text>')

    # ascii art rows (unchanged row-wipe reveal, offset by title bar height)
    for i, line in enumerate(lines):
        y = art_top + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        w = max(len(line), 1) * CHAR_W
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append(
            f'<clipPath id="c{i}"><rect x="{PAD}" y="{y}" height="{LINE_H}" width="0">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/></rect></clipPath>'
        )
        p.append(
            f'<g clip-path="url(#c{i})"><text xml:space="preserve" x="{PAD}" '
            f'y="{y + 11.2:.1f}" class="a" font-size="{FONT_SIZE}">{safe}</text></g>'
        )
        p.append(
            f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.8" begin="{begin}"/>'
            f'<set attributeName="opacity" to="0" begin="{end}"/></rect>'
        )

    # status bar: "whoami" line + steady blinking cursor
    status_line_y = art_top + art_h + PAD * 0.35
    status_y = status_line_y + 19
    total_row_time = len(lines) * ROW_DELAY
    p.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{width}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
    p.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'{USERNAME}@github:~$ whoami <tspan class="a">{USERNAME}</tspan></text>')
    cursor_x = PAD + (len(f"{USERNAME}@github:~$ whoami {USERNAME}") + 1) * 7.2
    p.append(f'<rect x="{cursor_x:.1f}" y="{status_y-12:.1f}" width="8" height="14" class="a" opacity="0">'
             f'<set attributeName="opacity" to="1" begin="{total_row_time:.2f}s"/>'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" begin="{total_row_time:.2f}s" repeatCount="indefinite"/></rect>')

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