import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
BG, INK, ACCENT = "#0B1015", "#F0F0E7", "#FFD36F"
plt.rcParams.update({"font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans", "text.color": INK})


class Board:
    """A board image whose named elements become plan.json marks, read back from the drawing.

    Single board: Board("board01.png") -> 3840x2160. Panel page: Board("page01.png", grid=(2, 2))
    -> 5120x2880, four 16:9 panels. Every coordinate is relative to ONE panel (0..1, matplotlib
    style: x right, y UP), so drawing a panel is the same as drawing a single board.
    save() returns the marks dict for a single board, or {(col, row): marks} for a panel page,
    already panel-relative and top-left based, ready to paste into each scene's "marks".
    """
    def __init__(self, path, grid=(1, 1)):
        self.path, self.cols, self.rows, self.reg = path, grid[0], grid[1], []
        self.dpi = 240 if grid == (1, 1) else 160
        self.fig = plt.figure(figsize=(16 * self.cols, 9 * self.rows), dpi=self.dpi, facecolor=BG)

    def _fig(self, x, y, panel):                     # panel coords -> figure coords
        c, r = panel
        return (c + x) / self.cols, (self.rows - 1 - r + y) / self.rows

    def text(self, x, y, s, size=24, color=INK, name=None, panel=(0, 0), **kw):
        t = self.fig.text(*self._fig(x, y, panel), s, fontsize=size, color=color, va="center", **kw)
        if name: self.reg.append((name, "box", t, panel))
        return t

    def title(self, s, panel=(0, 0)):
        return self.text(.045, .905, s, 34, weight="bold", panel=panel)

    def axes(self, rect, panel=(0, 0)):              # rect = [left, bottom, width, height] in the panel
        x, y = self._fig(rect[0], rect[1], panel)
        ax = self.fig.add_axes([x, y, rect[2] / self.cols, rect[3] / self.rows]); ax.set_facecolor(BG)
        return ax

    def box(self, name, artist, panel=(0, 0)):       # any drawn thing: image, axes, patch, legend
        self.reg.append((name, "box", artist, panel))

    def ring(self, name, ax, x, y, r=.035, panel=(0, 0)):   # a point in the axes' DATA coordinates
        self.reg.append((name, "ring", (ax, x, y, r), panel))

    def save(self, pad=.008):
        self.fig.canvas.draw(); rr = self.fig.canvas.get_renderer()
        W, H = self.fig.canvas.get_width_height()     # real pixel size, whatever the grid
        pw, ph = W / self.cols, H / self.rows         # one panel in pixels
        px = lambda X, c: X / pw - c                  # pixel -> panel fraction (x)
        py = lambda Y, r: (H - Y) / ph - r            # pixel (bottom-up) -> panel fraction (y, top-down)
        padv = pad * pw / ph                          # same padding in pixels on every side
        out = {}
        for name, kind, o, (c, r) in self.reg:
            m = out.setdefault((c, r), {})
            if kind == "box":
                b = o.get_window_extent(rr)
                m[name] = {"box": [*(float(round(v, 4)) for v in (px(b.x0, c) - pad, py(b.y1, r) - padv,
                                                                px(b.x1, c) + pad, py(b.y0, r) + padv))]}
            else:
                ax, x, y, rad = o; X, Y = ax.transData.transform((x, y))
                m[name] = {"ring": [float(round(px(X, c), 4)), float(round(py(Y, r), 4))], "r": rad}
        self.fig.savefig(self.path, dpi=self.dpi, facecolor=BG); plt.close(self.fig)
        return out.get((0, 0), {}) if (self.cols, self.rows) == (1, 1) else out
