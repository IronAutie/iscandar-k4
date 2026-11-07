"""Render the three Beam(2) state maps as single joined 256x256 grids.

Geometry is copied from the matching buddy PNGs: same canvas size, same
frame rectangle, same ticks and axis labels, so a beam map overlays its
buddy counterpart cell for cell.  Cube 0 fills rows 0..127, cube 1 rows
128..255.  The cube wall is marked only at the frame edges: a tick at
mid-height on the left and right spines, and rotated cube labels in the
left margin.
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from pathlib import Path
HERE = str(Path(__file__).resolve().parent)
OUT = f'{HERE}/out'
CMAP = ListedColormap(['white', 'black'])
DPI = 115

# canvas (W,H) and frame rect (left, top, right, bottom) in pixels,
# measured from the buddy PNG each beam map pairs with.
GEOM = {
    'beam-1106000-map.png':      dict(W=977,  H=982, left=73,  top=57, right=967,  bottom=945),
    'beam-1133798-map.png':      dict(W=1118, H=982, left=113, top=57, right=1006, bottom=945),
    'beam-final-state-map.png':  dict(W=977,  H=982, left=73,  top=57, right=967,  bottom=945),
}


def load(path):
    return np.loadtxt(path, dtype=int)


def render(csv0, csv1, title, outname):
    g = GEOM[outname]
    grid = np.vstack([load(csv0).reshape(128, 256),
                      load(csv1).reshape(128, 256)])
    assert grid.shape == (256, 256)
    W, H = g['W'], g['H']
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    left = g['left'] / W
    width = (g['right'] - g['left'] + 1) / W
    height = (g['bottom'] - g['top'] + 1) / H
    bottom = 1 - (g['bottom'] + 1) / H
    ax = fig.add_axes([left, bottom, width, height])
    ax.imshow(grid, cmap=CMAP, vmin=0, vmax=1, interpolation='nearest',
              aspect='auto')
    ax.set_yticks([0, 64, 128, 192, 255])
    ax.set_xticks([])
    ax.set_ylabel('Row')
    ax.set_xlabel('Sector address increases left to right, row by row: '
                  '256 sectors per row, 256 rows')
    ax.set_title(title)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('black')
        spine.set_linewidth(1.6)
    # Cube wall: ticks at mid-height on both spines, nothing in the field.
    ymid = 1 - 127.5 / 256
    for x0, x1 in [(-0.020, 0.0), (1.0, 1.020)]:
        ax.plot([x0, x1], [ymid, ymid], color='black', lw=2.2,
                clip_on=False, transform=ax.transAxes)
    # Cube labels in the left margin, centred on each half.
    label_x = (g['left'] - 38) / W
    for frac, text in [(0.75, 'Cube 0'), (0.25, 'Cube 1')]:
        fig.text(label_x, bottom + frac * height, text, rotation=90,
                 ha='center', va='center', fontsize=10)
    fig.savefig(f'{OUT}/{outname}', dpi=DPI)
    plt.close(fig)
    print(outname, 'ones', int(grid.sum()))


import os
os.makedirs(OUT, exist_ok=True)
render(f'{HERE}/beam-crest-cube0.csv', f'{HERE}/beam-crest-cube1.csv',
       'Beam (2 cubes of 32,768 sectors, 4 KiB each) at event 1106000\n'
       'black occupied, white vacant; 51708 sectors live',
       'beam-1106000-map.png')
render(f'{HERE}/beam-bottom-cube0.csv', f'{HERE}/beam-bottom-cube1.csv',
       'Beam (2 cubes of 32,768 sectors, 4 KiB each) at event 1133798\n'
       'black occupied, white vacant; 40934 sectors live',
       'beam-1133798-map.png')
render(f'{HERE}/beam-final-cube0.csv', f'{HERE}/beam-final-cube1.csv',
       'Beam(2) at 4 KiB, final state: black occupied, white vacant\n'
       '65,536 sectors (256 MiB), 56,532 live at end of stream',
       'beam-final-state-map.png')
