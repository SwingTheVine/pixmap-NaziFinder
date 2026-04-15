#!/usr/bin/env python3
"""
Heatmap overlay generator.

Usage:
    python heatmap.py <coords_file> <input_image> <output_image>

The coords file should have lines like:
    (1234, 0345, 023, 304) -- Wildcard
    (0, 0, 0, 0)
    etc.

Only the first two coordinates (x, y) are used, in range [0..2047].
The input image must be 2048x2048.
The heatmap is red-hot, with per-pixel opacity proportional to
occurrence count / max occurrence count across all pixels.
"""

import sys
import re
from pathlib import Path
from PIL import Image
import numpy as np


def parse_coords(filepath: str) -> dict[tuple[int, int], int]:
    """Parse the coordinate file and return a dict of (x, y) -> count."""
    counts: dict[tuple[int, int], int] = {}
    pattern = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*,")

    with open(filepath, "r") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            m = pattern.search(line)
            if not m:
                print(f"  [warn] line {lineno} skipped (no match): {line!r}")
                continue
            x, y = int(m.group(1)), int(m.group(2))
            if not (0 <= x <= 2047 and 0 <= y <= 2047):
                print(f"  [warn] line {lineno} out of range: ({x}, {y})")
                continue
            counts[(x, y)] = counts.get((x, y), 0) + 1

    return counts


def build_heatmap_array(counts: dict[tuple[int, int], int], size: int = 2048) -> np.ndarray:
    """
    Build a float32 array [size x size] with values in [0.0, 1.0].
    Values are normalised to the maximum occurrence count.
    """
    grid = np.zeros((size, size), dtype=np.float32)

    for (x, y), count in counts.items():
        grid[y, x] = count  # row = y, col = x

    max_val = grid.max()
    if max_val > 0:
        grid /= max_val

    return grid

def red_hot_rgba(intensity: np.ndarray) -> np.ndarray:
  """
  Test substitute: any pixel with a non-zero intensity becomes
  fully opaque black. Zero-intensity pixels remain transparent.
  """
  h, w = intensity.shape
  rgba = np.zeros((h, w, 4), dtype=np.uint8)

  hit = intensity > 0
  rgba[hit, 3] = 255  # alpha = fully opaque where any match exists

  # RGB stays 0 (black)

  return rgba

# def red_hot_rgba(intensity: np.ndarray) -> np.ndarray:
#     """
#     Map intensity [0..1] to a red-hot RGBA colour.

#     Red-hot palette:
#         0.00 -> black  (0,   0,   0)
#         0.33 -> red    (255, 0,   0)
#         0.66 -> orange (255, 165, 0)
#         1.00 -> white  (255, 255, 255)

#     Alpha equals intensity (so zero-count pixels are fully transparent).
#     """
#     h, w = intensity.shape
#     rgba = np.zeros((h, w, 4), dtype=np.uint8)

#     i = intensity  # shorthand

#     # --- Red channel ---
#     # black->red in [0, 0.33], red->orange in [0.33, 0.66], orange->white in [0.66, 1.0]
#     r = np.where(i <= 0.33, i / 0.33,
#         np.where(i <= 0.66, 1.0,
#                              1.0))
#     rgba[:, :, 0] = (r * 255).astype(np.uint8)

#     # --- Green channel ---
#     # 0 until 0.66, then ramps to 255 by 1.0
#     g = np.where(i <= 0.66, 0.0,
#                               (i - 0.66) / 0.34)
#     rgba[:, :, 1] = (g * 255).astype(np.uint8)

#     # --- Blue channel ---
#     # stays 0 until 0.85, then ramps to 255 (gives the "white-hot" tip)
#     b = np.where(i <= 0.85, 0.0,
#                               (i - 0.85) / 0.15)
#     rgba[:, :, 2] = (b * 255).astype(np.uint8)

#     # --- Alpha channel --- proportional to intensity
#     rgba[:, :, 3] = (i * 255).astype(np.uint8)

#     return rgba


# def composite(base: Image.Image, heatmap_rgba: np.ndarray) -> Image.Image:
#     """Alpha-composite the heatmap over the base image."""
#     base_rgba = base.convert("RGBA")
#     heat_img = Image.fromarray(heatmap_rgba, mode="RGBA")
#     result = Image.alpha_composite(base_rgba, heat_img)
#     return result

def composite(base: Image.Image, heatmap_rgba: np.ndarray) -> Image.Image:
    """Alpha-composite the heatmap over the base image."""
    base_rgba = base.convert("RGBA")
    heat_img = Image.fromarray(heatmap_rgba, mode="RGBA")
    # Split off the alpha channel to use as a paste mask
    r, g, b, a = heat_img.split()
    base_rgba.paste(heat_img, mask=a)
    return base_rgba


def main():
    print("Starting...")

    if len(sys.argv) != 4:
        print("Usage: python heatmap.py <coords_file> <input_image> <output_image>")
        sys.exit(1)

    coords_file, input_image, output_image = sys.argv[1], sys.argv[2], sys.argv[3]

    # --- Validate inputs ---
    if not Path(coords_file).exists():
        print(f"Error: coords file not found: {coords_file}")
        sys.exit(1)
    if not Path(input_image).exists():
        print(f"Error: input image not found: {input_image}")
        sys.exit(1)

    base = Image.open(input_image)
    if base.size != (2048, 2048):
        print(f"Error: input image must be 2048x2048, got {base.size}")
        sys.exit(1)

    # --- Parse ---
    print(f"Parsing {coords_file} ...")
    counts = parse_coords(coords_file)
    total = sum(counts.values())
    unique = len(counts)
    max_count = max(counts.values()) if counts else 0
    print(f"  {total} total coordinates, {unique} unique (x,y) positions, max count = {max_count}")

    if not counts:
        print("No valid coordinates found. Saving input image unchanged.")
        base.save(output_image)
        return

    # --- Build heatmap ---
    print("Building heatmap...")
    grid = build_heatmap_array(counts)
    heatmap_rgba = red_hot_rgba(grid)

    # --- Composite ---
    print("Compositing...")
    result = composite(base, heatmap_rgba)

    # --- Save ---
    result.save(output_image)
    print(f"Saved: {output_image}")


if __name__ == "__main__":
    main()