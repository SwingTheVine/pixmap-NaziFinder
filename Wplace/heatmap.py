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


def build_heatmap_array(counts: dict[tuple[int, int], int], size: int = 2048, mark_size: int = 1) -> np.ndarray:
    """
    Build a float32 array [size x size] with values in [0.0, 1.0].
    Values are normalised to the maximum occurrence count.

    mark_size: each coordinate is stamped onto a (mark_size x mark_size) square
               centered on that pixel. Must be a positive odd integer; even values
               are rounded up to the next odd number so centering is exact.
    """
    # Ensure mark_size is odd so the square centres cleanly on the pixel.
    if mark_size % 2 == 0:
        mark_size += 1

    grid = np.zeros((size, size), dtype=np.float32)
    half = mark_size // 2

    for (x, y), count in counts.items():
        r0 = max(0, y - half)
        r1 = min(size, y + half + 1)
        c0 = max(0, x - half)
        c1 = min(size, x + half + 1)
        # Use the max so overlapping marks don't artificially inflate counts.
        grid[r0:r1, c0:c1] = np.maximum(grid[r0:r1, c0:c1], count)

    max_val = grid.max()
    if max_val > 0:
        grid /= max_val

    return grid


def red_hot_rgba(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity [0..1] to black with alpha in [50%, 100%].

    Pixels with zero intensity remain fully transparent.
    Any hit maps to at least 50% opacity; the highest-count pixel
    reaches 100% opacity. RGB is always black (0, 0, 0).
    """
    h, w = intensity.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    hit = intensity > 0

    # Remap [0..1] -> [0.5..1.0], but only where there is a hit.
    alpha = np.where(hit, 0.5 + intensity * 0.5, 0.0)
    rgba[:, :, 3] = (alpha * 255).astype(np.uint8)

    # RGB stays 0 (black).

    return rgba


def composite(base: Image.Image, heatmap_rgba: np.ndarray) -> Image.Image:
    """Alpha-composite the heatmap over the base image."""
    base_rgba = base.convert("RGBA")
    heat_img = Image.fromarray(heatmap_rgba, mode="RGBA")
    result = Image.alpha_composite(base_rgba, heat_img)
    return result


def main():
    if len(sys.argv) not in (4, 5):
        print("Usage: python heatmap.py <coords_file> <input_image> <output_image> [mark_size]")
        print("  mark_size: odd integer, size of the square stamp per coordinate (default: 1)")
        sys.exit(1)

    coords_file, input_image, output_image = sys.argv[1], sys.argv[2], sys.argv[3]
    mark_size = int(sys.argv[4]) if len(sys.argv) == 5 else 1

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
    print(f"Building heatmap (mark_size={mark_size}) ...")
    grid = build_heatmap_array(counts, mark_size=mark_size)
    heatmap_rgba = red_hot_rgba(grid)

    # --- Composite ---
    print("Compositing ...")
    result = composite(base, heatmap_rgba)

    # --- Save ---
    result.save(output_image)
    print(f"Saved: {output_image}")


if __name__ == "__main__":
    main()