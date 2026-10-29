#!/usr/bin/env python3
"""Why the sky is blue but sunsets are red: boards + plan.json, all from code.

Every element a sentence can point at is registered while drawing, and its on-board box
(or ring position) is read back from matplotlib after layout, so marks match the ink exactly.
"""
import json, math
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch, Wedge, Rectangle
import physics as P

OUT = Path(__file__).resolve().parent
BG, PANEL, INK, MUTED = '#0B1015', '#121C24', '#F0F0E7', '#9FB2BF'
SKY, SUN, RED, GREEN, VIOLET = '#68CAFF', '#FFD36F', '#FF8A6B', '#9AE7BC', '#C9A7FF'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'mathtext.fontset': 'dejavusans', 'text.color': INK})
W, H = 3840, 2160


def wl_rgb(nm):
    """Approximate color of a wavelength (Bruton), for drawing only."""
    if nm < 440: r, g, b = -(nm - 440) / 60, 0, 1
    elif nm < 490: r, g, b = 0, (nm - 440) / 50, 1
    elif nm < 510: r, g, b = 0, 1, -(nm - 510) / 20
    elif nm < 580: r, g, b = (nm - 510) / 70, 1, 0
    elif nm < 645: r, g, b = 1, -(nm - 645) / 65, 0
    else: r, g, b = 1, 0, 0
    f = .3 + .7 * (nm - 380) / 40 if nm < 420 else (.3 + .7 * (750 - nm) / 50 if nm > 700 else 1)
    return (r * f, g * f, b * f)


class Board:
    def __init__(self, n, title, sub):
        self.n = n; self.marks = {}; self.reg = []
        self.fig = plt.figure(figsize=(16, 9), dpi=240, facecolor=BG)
        self.text(.045, .905, title, 34, INK, 'bold')
        self.text(.046, .845, sub, 18, MUTED)
        self.fig.add_artist(plt.Line2D([.045, .955], [.815, .815], color='#2A3A47', lw=2.5))

    def text(self, x, y, s, size=22, color=INK, weight='normal', name=None, ha='left', **kw):
        t = self.fig.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va='center', **kw)
        if name: self.reg.append(('box', name, t))
        return t

    def row(self, i, s, color=INK, name=None, size=24, x=.555, y0=.70, dy=.105):
        return self.text(x, y0 - i * dy, s, size, color, name=name)

    def footer(self, s):
        self.fig.add_artist(FancyBboxPatch((.045, .055), .91, .085, boxstyle='round,pad=0,rounding_size=.012',
                            transform=self.fig.transFigure, facecolor='#16222C', edgecolor='#5E5536', lw=2))
        return self.text(.07, .0975, s, 24, SUN, 'bold', name='F')

    def ax(self, rect, **kw):
        a = self.fig.add_axes(rect); a.set_facecolor(BG); self.axes = a; return a

    def ring(self, name, ax, x, y, r=.035):
        self.reg.append(('ring', name, (ax, x, y, r)))

    def boxart(self, name, artist):
        self.reg.append(('artist', name, artist))

    def save(self):
        self.fig.canvas.draw(); rr = self.fig.canvas.get_renderer()
        pad = .008
        for kind, name, obj in self.reg:
            if kind in ('box', 'artist'):
                bb = obj.get_window_extent(rr)
                self.marks[name] = {'box': [round(bb.x0 / W - pad, 4), round(1 - bb.y1 / H - pad * 1.6, 4),
                                            round(bb.x1 / W + pad, 4), round(1 - bb.y0 / H + pad * 1.6, 4)]}
            else:
                ax, x, y, r = obj
                px, py = ax.transData.transform((x, y))
                self.marks[name] = {'ring': [round(px / W, 4), round(1 - py / H, 4)], 'r': r}
        self.fig.savefig(OUT / f'board{self.n:02d}.png', dpi=240, facecolor=BG)
        plt.close(self.fig)
        return self.marks


def gradient(ax, x0, y0, w, h, top, bottom):
    g = np.linspace(0, 1, 256)[:, None, None]
    img = np.array(top)[None, None, :] * (1 - g) + np.array(bottom)[None, None, :] * g
    return ax.imshow(img, extent=[x0, x0 + w, y0, y0 + h], aspect='auto', zorder=1)


boards, scenes = {}, []

# ---------- 1. Two skies, one sun ----------
b = Board(1, 'Two skies, one sun', 'Why is the sky blue at noon but red at sunset?')
a = b.ax([.045, .17, .46, .62]); a.set_xlim(0, 1); a.set_ylim(0, 1); a.axis('off')
noon = gradient(a, 0, .53, 1, .45, (0.16, .45, .86), (.55, .80, .98))
a.add_patch(Circle((.86, .86), .055, color='#FFF6D8', zorder=3))
a.text(.03, .58, 'Noon', fontsize=24, color='white', weight='bold', zorder=4)
dusk = gradient(a, 0, .02, 1, .45, (.24, .18, .42), (1.0, .45, .18))
a.add_patch(Circle((.5, .02), .09, color='#FFB347', zorder=3))
a.add_patch(Rectangle((0, 0), 1, .025, color='#0B1015', zorder=4))
a.text(.03, .07, 'Sunset', fontsize=24, color='white', weight='bold', zorder=5)
b.boxart('noon', noon); b.boxart('sunset', dusk)
b.row(0, 'Same sun', name='E1', size=30); b.row(1, 'Same air', name='E2', size=30)
b.row(2, 'Different colors?', SKY, name='E3', size=30)
b.footer('The difference is the path the light travels through the air.')
boards[1] = b.save()
scenes.append(('Two skies, one sun', 1, [
    ('Look up at noon on a clear day, and the sky is a deep, clean blue.', 'noon'),
    ('Look again at sunset, and the same sky glows orange and red.', 'sunset'),
    ('The sun is the same star, sending out the same light.', 'E1'),
    ('The air is the same mix of nitrogen and oxygen.', 'E2'),
    ('So why do we see such different colors?', 'E3'),
    ('The answer is the path the light takes through the air, and we will build it one step at a time.', 'F')]))

# ---------- 2. Sunlight holds every color ----------
b = Board(2, 'Sunlight holds every color', 'Color is wavelength')
a = b.ax([.06, .36, .44, .30])
nm = np.linspace(380, 750, 600)
spec = a.imshow(np.array([[wl_rgb(v) for v in nm]]), extent=[380, 750, 0, 1], aspect='auto')
a.set_yticks([]); a.set_xticks([400, 450, 500, 550, 600, 650, 700, 750])
a.tick_params(colors=MUTED, labelsize=15, length=6); [s.set_visible(False) for s in a.spines.values()]
a.set_xlabel('wavelength (nanometres)', color=MUTED, fontsize=16)
b.boxart('spectrum', spec)
b.ring('G:450', a, 450, .5, .05); b.ring('G:700', a, 700, .5, .05)
b.text(.065, .73, 'violet', 18, VIOLET); b.text(.43, .73, 'red', 18, RED)
b.row(0, 'White light = all colors mixed', name='N1')
b.row(1, 'Visible light: 380 to 750 nm', name='E1')
b.row(2, 'Blue: about 450 nm', SKY, name='E2')
b.row(3, 'Red: about 700 nm', RED, name='E3')
b.footer('Short waves look blue. Long waves look red.')
boards[2] = b.save()
scenes.append(('Sunlight holds every color', 2, [
    ('Sunlight looks white, but it is really every color of the rainbow mixed together.', 'N1'),
    ('Each color is light with a different wavelength, the distance from one wave crest to the next.', 'spectrum'),
    ('We measure these waves in nanometers, which are billionths of a meter.', 'spectrum'),
    ('The light our eyes can see runs from about three hundred eighty to seven hundred fifty nanometers.', 'E1'),
    ('Blue light has short waves, around four hundred fifty nanometers.', ['E2', 'G:450']),
    ('Red light has long waves, around seven hundred nanometers.', ['E3', 'G:700']),
    ('Short waves look blue, long waves look red, and the whole story depends on that difference.', 'F')]))

# ---------- 3. Small molecules pick on short waves ----------
b = Board(3, 'Tiny molecules scatter short waves', 'Rayleigh scattering')
a = b.ax([.07, .23, .41, .50])
wls = np.arange(400, 701, 50)
rel = P.rayleigh_relative(wls)
bars = a.bar(wls, rel, width=36, color=[wl_rgb(v) for v in wls])
a.set_xticks(wls); a.set_ylim(0, 10.5); a.set_xlim(370, 730)
a.tick_params(colors=MUTED, labelsize=14); [s.set_color('#2A3A47') for s in a.spines.values()]
a.set_xlabel('wavelength (nm)', color=MUTED, fontsize=16); a.set_ylabel('scattering (red = 1)', color=MUTED, fontsize=16)
b.boxart('chart', a)
b.ring('G:b450', a, 450, rel[1], .04); b.ring('G:r700', a, 700, rel[-1], .04)
b.row(0, r'Scattering $\propto\ 1\,/\,\lambda^{4}$', SUN, name='E1', size=34, y0=.69)
b.row(1, r'$(700\,/\,450)^{4}\ \approx\ 5.9$', SKY, name='E2', size=30, y0=.69, dy=.13)
b.row(3, 'Air molecules: about 0.3 nm', name='N1', y0=.69, dy=.115)
b.row(4, 'Light waves: 380 to 750 nm', name='N2', y0=.69, dy=.115)
b.footer('Shorter waves scatter far more: blue about six times more than red.')
boards[3] = b.save()
scenes.append(('Tiny molecules scatter short waves', 3, [
    ('Air is made of tiny molecules, mostly nitrogen and oxygen.', None),
    ('Each molecule is about a third of a nanometer across, far smaller than any light wave.', ['N1', 'N2']),
    ('When light hits particles that small, a little of it is scattered off in every direction.', None),
    ('This is called Rayleigh scattering, and it strongly favors short waves.', 'E1'),
    ('The amount scattered grows as one over the wavelength to the fourth power.', 'E1'),
    ('Divide seven hundred by four hundred fifty, and raise the result to the fourth power.', 'E2'),
    ('You get almost six, so blue light is scattered nearly six times more than red.', ['G:b450', 'G:r700']),
    ('The chart shows the same thing: the bars grow taller with every step toward blue.', 'chart'),
    ('Shorter waves scatter far more, and that one rule explains both skies.', 'F')]))

# ---------- 4. Why the sky is blue ----------
b = Board(4, 'Why the daytime sky is blue', 'Scattered light reaches you from every direction')
a = b.ax([.045, .17, .46, .62]); a.set_xlim(0, 1.6); a.set_ylim(0, 1.15); a.axis('off')
a.add_patch(Rectangle((0, 0), 1.6, .14, color='#1C2A20'))
a.add_patch(Circle((1.42, 1.0), .085, color='#FFE9A8', zorder=3))
rng = np.random.default_rng(3)
for i in range(4):                                    # sunbeams
    a.annotate('', xy=(.15 + i * .1, .62 + i * .07), xytext=(1.33, .96 - i * .02),
               arrowprops=dict(arrowstyle='-|>', color='#FFF3C4', lw=2.5, alpha=.85))
mol = rng.uniform([.15, .45], [1.25, 1.05], (26, 2))
a.scatter(mol[:, 0], mol[:, 1], s=40, color='#D7E3EA', zorder=4)
ox, oy = .55, .2
for (mx, my) in mol[::3]:                             # scattered blue toward observer
    a.annotate('', xy=(ox + (mx - ox) * .18, oy + .08 + (my - oy) * .18), xytext=(mx, my),
               arrowprops=dict(arrowstyle='-|>', color=SKY, lw=2, alpha=.9))
a.plot([ox, ox], [.14, .26], color=INK, lw=4); a.add_patch(Circle((ox, .3), .035, color=INK))
b.ring('G:sun', a, 1.42, 1.0, .07); b.ring('G:you', a, ox, .24, .07)
b.text(.3, .2, 'you', 18, MUTED)
b.row(0, 'Blue is scattered all across the sky', SKY, name='N1')
b.row(1, 'Sunlight has less violet than blue', VIOLET, name='N2')
b.row(2, 'Our eyes respond more to blue', name='N3')
b.row(3, 'than to violet', name='N3b', y0=.75)
b.footer('So every part of the sky glows blue.')
m = b.save(); m['N3'] = {'box': [m['N3']['box'][0], m['N3']['box'][1], max(m['N3']['box'][2], m['N3b']['box'][2]), m['N3b']['box'][3]]}
boards[4] = m
scenes.append(('Why the daytime sky is blue', 4, [
    ('As sunlight crosses the sky, molecules scatter some of it in every direction.', 'G:sun'),
    ('Because blue scatters most, scattered blue light reaches your eyes from all over the sky.', ['N1', 'G:you']),
    ('Wherever you look away from the sun, you see that scattered blue.', 'N1'),
    ('But violet waves are even shorter, so why is the sky not violet?', None),
    ('First, sunlight contains less violet than blue to begin with.', 'N2'),
    ('Second, our eyes are much more sensitive to blue than to violet.', 'N3'),
    ('Mixed together, the scattered light looks sky blue.', 'F')]))

# ---------- 5. Sunset: the long way through the air ----------
b = Board(5, 'Sunset: the long way through the air', 'Same atmosphere, much longer path')
a = b.ax([.045, .15, .46, .65]); a.set_xlim(-1.25, 1.25); a.set_ylim(-.35, 1.45); a.set_aspect('equal'); a.axis('off')
R, T = 1.0, .32                                       # Earth radius and (exaggerated) air thickness
a.add_patch(Wedge((0, -0.0), R + T, 25, 155, width=T, color='#173049'))
a.add_patch(Wedge((0, 0), R, 0, 180, color='#1C2A20'))
oy = R
a.plot([0, 0], [oy, oy + .07], color=INK, lw=4); a.add_patch(Circle((0, oy + .1), .03, color=INK))
a.annotate('', xy=(0, oy + .16), xytext=(0, R + T + .12), arrowprops=dict(arrowstyle='-|>', color=SUN, lw=4))
L = math.sqrt((R + T) ** 2 - R ** 2)
a.annotate('', xy=(-.05, oy + .1), xytext=(-L - .1, oy + .1), arrowprops=dict(arrowstyle='-|>', color=RED, lw=4))
tn = a.text(.06, R + T + .05, 'noon: short path', fontsize=19, color=SUN)
ts = a.text(-1.2, oy + .2, 'sunset: long path', fontsize=19, color=RED)
b.boxart('noon', tn); b.boxart('sunset', ts)
b.row(0, 'Overhead: 1 air mass', SUN, name='E1')
b.row(1, 'Horizon: about 38 air masses', RED, name='E2')
b.row(2, 'Blue is scattered out on the way', SKY, name='N1')
b.text(.555, .27, 'drawing not to scale', 15, MUTED)
b.footer('Long path: most of the blue is gone before the light arrives.')
boards[5] = b.save()
scenes.append(('Sunset: the long way through the air', 5, [
    ('Now picture the sun at noon, high overhead.', 'noon'),
    ('Its light crosses the atmosphere by the shortest route, straight down.', 'E1'),
    ('Scientists call that thickness one air mass.', 'E1'),
    ('At sunset, the sun sits on the horizon, and its light skims sideways through the air.', 'sunset'),
    ('That slanted path is about thirty eight times longer than the path at noon.', 'E2'),
    ('Along that long path, the blue light is scattered out of the beam again and again.', 'N1'),
    ('By the time the light reaches you, most of the blue has been removed.', 'F')]))

# ---------- 6. What survives the trip ----------
b = Board(6, 'What survives the trip', 'Share of each color that gets straight through clean air')
a = b.ax([.075, .22, .42, .52])
nm = np.linspace(380, 750, 400)
noon_T = P.transmission(nm, P.air_mass(0)) * 100; dusk_T = P.transmission(nm, P.air_mass(90)) * 100
a.plot(nm, noon_T, color=SUN, lw=5, label='noon'); a.plot(nm, dusk_T, color=RED, lw=5, label='sunset')
a.set_ylim(0, 105); a.set_xlim(380, 750)
a.tick_params(colors=MUTED, labelsize=14); [s.set_color('#2A3A47') for s in a.spines.values()]
a.set_xlabel('wavelength (nm)', color=MUTED, fontsize=16); a.set_ylabel('gets through (%)', color=MUTED, fontsize=16)
lg = a.legend(fontsize=17, facecolor=PANEL, edgecolor='#2A3A47', labelcolor=INK, loc='center right')
b.boxart('graph', a)
b.ring('G:noon450', a, 450, P.transmission(450, P.air_mass(0)) * 100, .035)
b.ring('G:dusk450', a, 450, P.transmission(450, P.air_mass(90)) * 100, .035)
b.ring('G:dusk700', a, 700, P.transmission(700, P.air_mass(90)) * 100, .035)
nb, nr = P.transmission(450, P.air_mass(0)) * 100, P.transmission(700, P.air_mass(0)) * 100
db, dr = P.transmission(450, P.air_mass(90)) * 100, P.transmission(700, P.air_mass(90)) * 100
b.row(0, f'Noon: blue {nb:.0f}%, red {nr:.0f}%', SUN, name='E1')
b.row(1, f'Sunset: blue {db:.2f}%, red {dr:.0f}%', RED, name='E2')
b.row(2, 'Model: clean air, Rayleigh scattering only', MUTED, name='N1', size=20)
b.footer('Only reds and oranges survive the long path.')
boards[6] = b.save()
scenes.append(('What survives the trip', 6, [
    ('We can put numbers on this with the same scattering law.', None),
    ('This graph shows how much of each color gets straight through the air.', 'graph'),
    ('At noon, about eighty percent of the blue light and ninety six percent of the red light make it through.', ['E1', 'G:noon450']),
    ('So the sun itself still looks white at midday.', None),
    ('At sunset, only about two hundredths of a percent of the blue light survives.', ['E2', 'G:dusk450']),
    ('But about a quarter of the red light still gets through.', ['E2', 'G:dusk700']),
    ('That leftover light is mostly red and orange, so the sun and the clouds around it glow red.', 'F'),
    ('These numbers come from a clean air model, and real dust and haze often make sunsets even more vivid.', 'N1')]))

# ---------- 7. Putting it together (+ quiz question) ----------
b = Board(7, 'Putting it together', 'Four ideas, one answer')
for i, (s, c) in enumerate([('1. Sunlight carries every color', INK), ('2. Short waves scatter most: 1 / λ⁴', SUN),
                            ('3. Day: scattered blue fills the sky', SKY), ('4. Sunset: the long path strips the blue', RED)]):
    b.row(i, s, c, name=f'E{i+1}', x=.06, y0=.70, dy=.115, size=25)
b.fig.add_artist(FancyBboxPatch((.565, .25), .39, .5, boxstyle='round,pad=0,rounding_size=.02',
                 transform=b.fig.transFigure, facecolor='#13202A', edgecolor=SKY, lw=3))
b.text(.59, .68, 'TEST YOURSELF', 18, SKY, 'bold')
q1 = b.text(.59, .58, 'If tiny molecules make the', 26, INK, name='Q')
b.text(.59, .51, 'sky blue, why are clouds', 26, INK, name='Q2')
b.text(.59, .44, 'white instead of blue?', 26, INK, name='Q3')
b.text(.59, .33, 'Pause and think before the answer.', 17, MUTED)
b.footer('Same sunlight, same air: the path length decides the color.')
m = b.save()
m['Q'] = {'box': [min(m[k]['box'][0] for k in ('Q', 'Q2', 'Q3')), m['Q']['box'][1],
                  max(m[k]['box'][2] for k in ('Q', 'Q2', 'Q3')), m['Q3']['box'][3]]}
boards[7] = m
scenes.append(('Putting it together', 7, [
    ("Let's put the whole story together.", None),
    ('Sunlight carries every color.', 'E1'),
    ('Short blue waves scatter far more than long red waves, as one over the wavelength to the fourth.', 'E2'),
    ('During the day, that scattered blue fills the sky from every direction.', 'E3'),
    ('At sunset, the long path through the air strips the blue away, leaving reds and oranges.', 'E4'),
    ('Now a quick question to test yourself.', None),
    ('If tiny molecules make the sky blue, why are clouds white instead of blue?', 'Q', 5.0)]))

# ---------- 8. The answer, and a bonus ----------
b = Board(8, 'The answer, and a bonus', 'Why clouds are white')
a = b.ax([.05, .2, .45, .58]); a.set_xlim(0, 2); a.set_ylim(0, 1.3); a.set_aspect('equal'); a.axis('off')
a.add_patch(Circle((.45, .65), .03, color='#D7E3EA'))
a.text(.45, .25, 'air molecule', fontsize=18, color=MUTED, ha='center')
a.annotate('', xy=(.45 + .28, .65 + .28), xytext=(.45, .65), arrowprops=dict(arrowstyle='-|>', color=SKY, lw=3))
a.annotate('', xy=(.45 - .3, .65 + .2), xytext=(.45, .65), arrowprops=dict(arrowstyle='-|>', color=SKY, lw=3))
drop = Circle((1.45, .65), .3, color='#BFD7E6', alpha=.9); a.add_patch(drop)
for ang, col in zip(np.linspace(20, 160, 6), ['#FF6B6B', '#FFB347', '#FFE66D', '#8BE38B', SKY, VIOLET]):
    r = math.radians(ang)
    a.annotate('', xy=(1.45 + .55 * math.cos(r), .65 + .55 * math.sin(r)), xytext=(1.45 + .3 * math.cos(r), .65 + .3 * math.sin(r)),
               arrowprops=dict(arrowstyle='-|>', color=col, lw=3))
a.text(1.45, .2, 'cloud droplet', fontsize=18, color=MUTED, ha='center')
b.ring('G:drop', a, 1.45, .65, .17)
b.row(0, 'Cloud droplets: thousands of', name='E1'); b.row(1, 'times wider than molecules', name='E1b', y0=.73)
b.row(2, 'Big particles scatter all', name='E2'); b.row(3, 'colors about equally', name='E2b', y0=.73)
b.row(4, 'Bonus: on Mars, dust makes', RED, name='N1', size=21); b.row(5, 'sunsets look blue', RED, name='N1b', size=21, y0=.73)
b.footer('All colors scattered together look white.')
m = b.save()
for k in ('E1', 'E2', 'N1'):
    m[k] = {'box': [m[k]['box'][0], m[k]['box'][1], max(m[k]['box'][2], m[k + 'b']['box'][2]), m[k + 'b']['box'][3]]}
boards[8] = m
scenes.append(('The answer, and a bonus', 8, [
    ('Cloud droplets are huge compared with air molecules, thousands of times wider.', ['E1', 'G:drop']),
    ('Particles that big scatter all colors about equally.', 'E2'),
    ('And when every color is scattered together, the result looks white.', 'F'),
    ('Here is a bonus fact.', None),
    ('On Mars, fine dust in the air scatters light differently, and Martian sunsets actually look blue.', 'N1'),
    ('So the next time you watch a sunset, remember that you are seeing the light that survived the longest trip through the sky.', None)]))

# ---------- plan.json ----------
plan = {'title': 'Why the sky is blue but sunsets are red', 'width': 1920, 'fps': 24, 'captions': False,
        'audio': 'narration.wav', 'timestamps': 'labels.txt', 'scenes': []}
for title, n, lines in scenes:
    sc = {'title': title, 'image': f'board{n:02d}.png', 'marks': boards[n], 'lines': []}
    for item in lines:
        text, mark = item[0], item[1]
        ln = {'text': text}
        if mark: ln['mark'] = mark
        if len(item) > 2: ln['pause_after'] = item[2]
        for mm in ([mark] if isinstance(mark, str) else mark or []):
            assert mm in boards[n], (n, mm)
        sc['lines'].append(ln)
    plan['scenes'].append(sc)
(OUT / 'plan.json').write_text(json.dumps(plan, indent=1))
words = sum(len(l['text'].split()) for s in plan['scenes'] for l in s['lines'])
print('boards', len(boards), 'lines', sum(len(s['lines']) for s in plan['scenes']), 'words', words,
      f'(~{words / 155 + 0.6 * 57 / 60:.1f} min at Kokoro pace)')
