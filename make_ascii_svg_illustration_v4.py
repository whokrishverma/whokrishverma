#!/usr/bin/env python3
"""
Illustration-mode ASCII portrait generator, v2.
Neural (rembg) background removal -- handles textured/patterned backgrounds
that color-similarity flood fill can't chain through -- + posterized tone
levels for depth (uses the comic's actual flat color blocks as shading,
instead of a single flat fill tone).
"""
import sys
import numpy as np
import cv2
from PIL import Image
from rembg import remove as rembg_remove

RAMP = " .`:-=+*cs#%@"
COLS = 130
GAMMA = 1.0

# Background removal (neural segmentation via rembg, handles textured/patterned
# backgrounds that color-similarity flood fill can't chain through)
ALPHA_THRESHOLD = 128    # rembg alpha cutoff: below this = background

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

# --- terminal window chrome ---
PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"
TITLE_BAR_TEXT = "lorem ipsum"
WHOAMI_NAME = "gugu gaga"

def remove_background_rembg(img_rgb, threshold=ALPHA_THRESHOLD):
    """Neural background removal via rembg (u2net). Segments the actual
    subject regardless of how busy/textured the background is -- unlike
    flood fill, it doesn't depend on background color uniformity or being
    walled in by ink outlines, since it's a trained saliency model rather
    than a connectivity/color heuristic."""
    rgba = rembg_remove(img_rgb)
    alpha = np.array(rgba)[:, :, 3]
    bg_mask = alpha < threshold
    return bg_mask

def prep(path):
    src = Image.open(path).convert("RGB")
    arr = np.array(src)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    bg_mask = remove_background_rembg(src)

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
        out.append(line)  # keep full width (padded with spaces) for uniform terminal-grid alignment
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out

def build_svg(lines, out_path, cols=COLS, static=False):
    art_w = cols * CHAR_W
    art_h = len(lines) * LINE_H
    canvas_w = int(art_w + PAD * 2)
    canvas_h = int(TITLEBAR_H + art_h + STATUS_H + PAD)

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">'
    ]
    p.append(
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        '</linearGradient></defs>'
    )
    p.append(f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#bg)"/>')
    p.append(f'<rect x="0.5" y="0.5" width="{canvas_w-1}" height="{canvas_h-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

    # title bar: traffic-light dots + centered command text
    p.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    safe_title = TITLE_BAR_TEXT.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p.append(f'<text x="{canvas_w/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">{safe_title}</text>')

    art_top = TITLEBAR_H + PAD * 0.35
    for i, line in enumerate(lines):
        y = art_top + i * LINE_H
        begin = f"{i * ROW_DELAY:.2f}s"
        end = f"{(i + 1) * ROW_DELAY:.2f}s"
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = (f'<text xml:space="preserve" x="{PAD}" y="{y + 11.2:.1f}" fill="{INK}" '
                f'font-size="{FONT_SIZE}" textLength="{art_w:.1f}" lengthAdjust="spacing">{safe}</text>')

        if static:
            p.append(text)
            continue

        p.append(
            f'<clipPath id="c{i}"><rect x="{PAD}" y="{y}" height="{LINE_H}" width="0">'
            f'<animate attributeName="width" from="0" to="{art_w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/></rect></clipPath>'
        )
        p.append(f'<g clip-path="url(#c{i})">{text}</g>')
        p.append(
            f'<rect y="{y + 1}" width="6" height="{LINE_H-2}" fill="{INK}" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + art_w:.1f}" '
            f'begin="{begin}" dur="{ROW_DELAY}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{begin}"/>'
            f'<set attributeName="opacity" to="0" begin="{end}"/></rect>'
        )

    # status bar: "whoami" line + steady blinking cursor
    status_line_y = TITLEBAR_H + art_h + PAD * 0.35
    status_y = status_line_y + 19
    safe_name = WHOAMI_NAME.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{canvas_w}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
    p.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'whoami <tspan fill="{INK}">{safe_name}</tspan></text>')
    if not static:
        p.append(f'<rect x="{PAD+56}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
                  f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
                  f'dur="1s" repeatCount="indefinite"/></rect>')

    p.append("</svg>")
    open(out_path, "w").write("".join(p))
    return out_path

if __name__ == "__main__":
    import os
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else "ascii.svg"
    static = bool(os.environ.get("STATIC"))
    lines = to_lines(prep(src))
    print("\n".join(lines))
    build_svg(lines, dst, static=static)
    print(f"\nwrote {dst}  ({len(lines)} rows){' [STATIC preview]' if static else ''}")