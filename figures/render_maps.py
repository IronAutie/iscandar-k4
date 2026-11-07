"""Repo copy: paths are relative to this folder. Inputs are the
state dumps beside this script; output goes to ./out (or argv[1]).
"""
"""Render the six Paper 2 state maps with black borders on every panel.

Data: one 0/1 value per line CSVs (address order).  Titles and labels
copied from the original figures.  Output names match the Overleaf
project files.
"""
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from pathlib import Path
HERE = str(Path(__file__).resolve().parent)
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{HERE}/out'
CMAP = ListedColormap(['white', 'black'])
BORDER = 1.6
DPI = {'buddy-1106000-map.png': 115, 'buddy-1133798-map.png': 115,
       'buddy-final-state-map.png': 117, 'beam-1106000-map.png': 119,
       'beam-1133798-map.png': 119, 'beam-final-state-map.png': 122}


def load(path):
    return np.loadtxt(path, dtype=int)


def frame(ax):
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color('black')
        spine.set_linewidth(BORDER)


def buddy(csv, rows, cols, title, xlabel, figsize, outname):
    grid = load(csv).reshape(rows, cols)
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(grid, cmap=CMAP, vmin=0, vmax=1, interpolation='nearest',
              aspect='auto')
    ax.set_yticks([0, 64, 128, 192, 255])
    ax.set_xticks([])
    ax.set_ylabel('Row')
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    frame(ax)
    fig.savefig(f'{OUT}/{outname}', dpi=DPI[outname], bbox_inches='tight')
    plt.close(fig)
    print(outname, 'ones', int(grid.sum()))


def beam(csv0, csv1, title, xlabel, figsize, outname):
    grids = [load(csv0).reshape(128, 256), load(csv1).reshape(128, 256)]
    fig, axes = plt.subplots(2, 1, figsize=figsize)
    for ax, grid, label in zip(axes, grids, ['Cube 0', 'Cube 1']):
        ax.imshow(grid, cmap=CMAP, vmin=0, vmax=1,
                  interpolation='nearest', aspect='auto')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_ylabel(label)
        frame(ax)
    if xlabel:
        axes[1].set_xlabel(xlabel)
    fig.suptitle(title)
    fig.savefig(f'{OUT}/{outname}', dpi=DPI[outname], bbox_inches='tight')
    plt.close(fig)
    print(outname, 'ones', int(grids[0].sum() + grids[1].sum()))


buddy(f'{HERE}/buddy-crest.csv', 256, 256,
      'Buddy system just before the fall: black occupied, white vacant\n'
      'event 1,106,000; 65,536 pages of 4 KiB (256 MiB); 51767 granted',
      'Page address increases left to right, row by row: '
      '256 pages per row, 256 rows',
      (10, 10), 'buddy-1106000-map.png')

buddy(f'{HERE}/buddy-bottom.csv', 256, 256,
      'Buddy system at the bottom of the fall (breakage peak): '
      'black occupied, white vacant\n'
      'event 1,133,798; 65,536 pages of 4 KiB (256 MiB); '
      '40993 granted, 10,953 vacant pages inside the occupied span',
      'Page address increases left to right, row by row: '
      '256 pages per row, 256 rows',
      (10, 10), 'buddy-1133798-map.png')

buddy(f'{HERE}/buddy-final512.csv', 256, 512,
      'Buddy system, final state: black occupied, white vacant\n'
      '131,072 pages of 4 KiB (512 MiB), 56,596 granted at end of stream',
      'Page address increases left to right, row by row: '
      '512 pages per row, 256 rows',
      (13.4, 7.4), 'buddy-final-state-map.png')

beam(f'{HERE}/beam-crest-cube0.csv', f'{HERE}/beam-crest-cube1.csv',
     'Beam (2 cubes of 32,768 sectors, 4 KiB each) at event 1106000\n'
     'black occupied, white vacant; 51708 sectors live',
     None, (10, 9.2), 'beam-1106000-map.png')

beam(f'{HERE}/beam-bottom-cube0.csv', f'{HERE}/beam-bottom-cube1.csv',
     'Beam (2 cubes of 32,768 sectors, 4 KiB each) at event 1133798\n'
     'black occupied, white vacant; 40934 sectors live',
     None, (10, 9.2), 'beam-1133798-map.png')

beam(f'{HERE}/beam-final-cube0.csv',
     f'{HERE}/beam-final-cube1.csv',
     'Beam(2) at 4 KiB, final state: black occupied, white vacant\n'
     '65,536 sectors (256 MiB), 56,532 live at end of stream',
     'Sector address increases left to right, row by row: '
     '256 sectors per row',
     (10.4, 9.9), 'beam-final-state-map.png')
