#!/usr/bin/env python3
"""Motion comic: painted panels + multi-voice narration -> MP4 with moving shots, effects, music.

  python motion_comic.py plan.json --check            # lint (run before narrating)
  python motion_comic.py plan.json --contact-sheet    # every shot's start/end framing
  python motion_comic.py plan.json --clip 60 75       # quick check with real audio
  python motion_comic.py plan.json                    # final.mp4 (+ .srt, chapters)

Everything is anchored to LINES and WORDS, never to clock times, so new narration (another
voice, a retake, a rewritten line) re-times every cut, effect and music cue automatically.

plan.json (the narration fields are the same as render_video.py / narrate.py):
{
  "title": "...", "width": 1280, "fps": 24,
  "audio": "narration_fx.wav", "timestamps": "labels.txt", "words": "words.json",
  "cast": {"narrator": "af_heart", "hero": "am_puck"},            # narrate.py voices
  "voice_fx": {"dragon": {"pitch": -5, "echo": true}},             # voice_fx.py
  "images": {"B": "art/sheetB_x4.png"},                            # short names for images
  "music": {"bpm": 112, "volume": 0.84},                           # procedural jingle; or {"file": "bed.mp3"}; omit = none
  "bug": "ZORBLOOK TV",                                            # optional corner logo
  "scenes": [{"title": "Chapter title", "sting": true, "lines": [
     {"text": "Then call Zorblook's today!", "display": "THEN CALL ZORBLOOK'S TODAY!", "speaker": "hero",
      "shot": {"image": "B", "box": [0.1, 0.2, 0.5, 0.6], "from": [0.5, 0.5, 1.0], "to": [0.4, 0.4, 1.3], "tr": "x"},
      "shots": [{"at": "today", "image": "B", "box": [...], "from": [...], "to": [...], "tr": "cut"}],
      "fx":  [{"type": "shake", "at": "call", "dur": 0.5, "amp": 9}],
      "sfx": [{"type": "thud", "at": "today"}],
      "lower_third": ["BARNABY BLINT", "Spokesperson"]}]}]
}
- "text" is spoken (write it for the voice: normal case, words not digits); "display" (optional)
  is what the subtitles show, e.g. the shouted ALL-CAPS version.
- shot: starts at its line (just before the speech) or at "at": a word of that line ("burst",
  "burst#2" = second one, "+0.4" offsets allowed: "burst+0.4"). It runs until the next shot.
  box = the clean picture area on the image, fractions 0..1 (x0, y0, x1, y1). from/to = camera
  at the start/end as (cx, cy, zoom): cx, cy 0..1 slide the view across the box's spare room,
  zoom 1 = the largest 16:9 view that fits the box. "fit": "contain" shows the whole box over a
  blurred copy (for title cards that are not 16:9). "card": {"title", "subtitle", "footer"}
  instead of an image draws a TV test card. tr: "x" cross-fade (default), "cut", "static",
  "flash", "cont" (same as cut; for continuing a move on the same panel).
- fx types: shake (dur, amp px, freq, repeat, every), flash (dur), static (dur), debris (dur, n),
  drop (a crumb/biscuit falls; size). sfx types: thud, crash, static, tink, rumble, sting,
  whoosh, crunch, bell (vol, repeat, every). "at" omitted = when the line's speech starts.
- Scene "sting": true plays a short brass sting as the scene starts. Scene titles -> chapters.
Needs ffmpeg/ffprobe, Pillow, numpy. Mix is normalised to about -14 LUFS (online standard).
"""
import argparse, difflib, json, math, re, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

XF, STATIC_LEN, LEAD, SCENE_LEAD = 0.30, 0.45, 0.35, 0.60
SR = 48000
TR = {'x', 'cut', 'static', 'flash', 'cont'}
FX = {'shake', 'flash', 'static', 'debris', 'drop'}
SFX = {'thud', 'crash', 'static', 'tink', 'rumble', 'sting', 'whoosh', 'crunch', 'bell'}


def font(size, bold=True):
    for p in (['/usr/share/fonts/opentype/inter/InterDisplay-Black.otf', '/usr/share/fonts/opentype/inter/Inter-Black.otf']
              if bold else []) + ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                                  'C:/Windows/Fonts/arialbd.ttf']:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def norm(s): return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
def ease(u): u = min(1, max(0, u)); return 0.5 - 0.5 * math.cos(math.pi * u)


def read_labels(p):
    out = []
    for l in Path(p).read_text(encoding='utf-8-sig').splitlines():
        q = l.split('\t')
        if len(q) >= 2 and not l.startswith('\\'):
            out.append((float(q[0]), float(q[1]), q[2] if len(q) > 2 else ''))
    return out


def probe(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                                capture_output=True, text=True, check=True).stdout)


def flat_lines(plan):
    return [(si, li, sc, ln) for si, sc in enumerate(plan['scenes']) for li, ln in enumerate(sc['lines'])]


def all_shots(ln):
    return ([ln['shot']] if ln.get('shot') else []) + list(ln.get('shots', []))


def split_anchor(at):
    if at is None: return None, 1, 0.0
    m = re.match(r"^\s*([^#+\-]*?)\s*(?:#(\d+))?\s*([+-]\s*[\d.]+)?\s*$", str(at))
    if not m: return str(at), 1, 0.0
    return (m.group(1) or None), int(m.group(2) or 1), float((m.group(3) or '0').replace(' ', ''))


def lint(plan, base):
    out, imgs = [], plan.get('images', {})
    lines = flat_lines(plan)
    if not lines or not all_shots(lines[0][3]): out.append('the first line needs a "shot"')
    for si, li, sc, ln in lines:
        tag = f'S{si + 1}.{li + 1}'
        if re.search(r'[0-9%=^/\\$<>*_{}|#@&+]', ln.get('text', '')): out.append(f'{tag}: digits or symbols in spoken text')
        for sh in all_shots(ln):
            if sh.get('card'): continue
            im = imgs.get(sh.get('image'), sh.get('image'))
            if not im or not (base / im).is_file(): out.append(f'{tag}: image not found: {sh.get("image")}')
            b = sh.get('box', [0, 0, 1, 1])
            if len(b) != 4 or not (0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1): out.append(f'{tag}: box {b} must be x0<x1, y0<y1 in 0..1')
            for k in ('from', 'to'):
                c = sh.get(k, [.5, .5, 1])
                if len(c) != 3 or not (0 <= c[0] <= 1 and 0 <= c[1] <= 1 and c[2] >= 1): out.append(f'{tag}: {k} {c} needs cx,cy in 0..1, zoom >= 1')
            if sh.get('tr', 'x') not in TR: out.append(f'{tag}: unknown transition {sh.get("tr")}')
        for kind, ok in (('fx', FX), ('sfx', SFX)):
            for e in ln.get(kind, []):
                if e.get('type') not in ok: out.append(f'{tag}: unknown {kind} type {e.get("type")}')
        for e in all_shots(ln)[1 if ln.get('shot') else 0:] + ln.get('fx', []) + ln.get('sfx', []):
            w, n, _ = split_anchor(e.get('at'))
            if w and sum(1 for t in norm(ln['text']).split() if t == norm(w)) < n:
                out.append(f'{tag}: anchor word "{e.get("at")}" is not in the spoken text')
        spk = ln.get('speaker', sc.get('speaker'))
        if spk and spk not in plan.get('cast', {}): out.append(f'{tag}: speaker "{spk}" not in "cast"')
    return out


class Timeline:
    def __init__(self, plan, base, total=None):
        self.lines = flat_lines(plan)
        labels = read_labels(base / plan['timestamps'])
        idx, j = [], 0
        for k, (*_, ln) in enumerate(self.lines):
            best, br = None, 0
            for c in range(j, min(len(labels), j + 20)):
                r = difflib.SequenceMatcher(None, norm(ln['text']), norm(labels[c][2])).ratio()
                if r > br: best, br = c, r
            if best is None or br < 0.6: sys.exit(f'line {k + 1} not found in timestamps: "{ln["text"][:60]}"')
            idx.append(best); j = best + 1
        self.sp = [(labels[i][0], labels[i][1]) for i in idx]
        self.total = total or probe(base / plan['audio'])
        self.start = []
        for k, (si, li, *_) in enumerate(self.lines):
            if k == 0: self.start.append(0.0); continue
            prev_end = self.sp[k - 1][1]; s = self.sp[k][0]
            self.start.append(max(prev_end, s - (SCENE_LEAD if li == 0 else LEAD)))
        self.words = None
        if plan.get('words') and (base / plan['words']).exists():
            wl = json.loads((base / plan['words']).read_text())['lines']
            self.words = [wl[i]['words'] if i < len(wl) else [] for i in idx]
        self.warn = []

    def word(self, k, at):
        """Time a word of line k is spoken (recognised word, else position-in-sentence estimate)."""
        w, n, off = split_anchor(at)
        s0, s1 = self.sp[k]
        if not w: return s0 + off
        target = norm(w)
        if self.words and self.words[k]:
            hits = [t0 for ww, t0, _ in self.words[k] if difflib.SequenceMatcher(None, norm(ww), target).ratio() >= 0.75]
            if len(hits) >= n: return hits[n - 1] + off
        toks = norm(self.lines[k][3]['text']).split(); pos = [i for i, t in enumerate(toks) if t == target]
        if len(pos) < n: sys.exit(f'anchor "{at}" not in line {k + 1}')
        chars = [len(t) + 1 for t in toks]; frac = sum(chars[:pos[n - 1]]) / max(1, sum(chars))
        self.warn.append(f'estimated time for "{at}" in line {k + 1} (recognizer did not hear it)')
        return s0 + frac * (s1 - s0) + off


def build(plan, base, tl):
    imgs = plan.get('images', {})
    shots, fx, sfx, lts = [], [], [], []
    for k, (si, li, sc, ln) in enumerate(tl.lines):
        for j, sh in enumerate(all_shots(ln)):
            s = dict(sh)
            s['t0'] = tl.start[k] if (j == 0 and ln.get('shot') and not sh.get('at')) else max(tl.start[k], tl.word(k, sh.get('at')) - 0.08)
            if not s.get('card'): s['path'] = base / imgs.get(sh['image'], sh['image'])
            shots.append(s)
        for e in ln.get('fx', []):
            for r in range(int(e.get('repeat', 1))): fx.append(dict(e, t=tl.word(k, e.get('at')) + r * e.get('every', 0.2)))
        for e in ln.get('sfx', []):
            for r in range(int(e.get('repeat', 1))): sfx.append(dict(e, t=tl.word(k, e.get('at')) + r * e.get('every', 0.2)))
        if ln.get('lower_third'): lts.append(dict(t0=tl.sp[k][0] + .2, t1=tl.sp[k][0] + 3.8, name=ln['lower_third'][0], role=ln['lower_third'][1] if len(ln['lower_third']) > 1 else ''))
        if li == 0 and sc.get('sting'): sfx.append(dict(type='sting', t=tl.start[k] + .1))
    shots.sort(key=lambda s: s['t0'])
    for i, s in enumerate(shots): s['t1'] = shots[i + 1]['t0'] if i + 1 < len(shots) else tl.total
    for s in shots:
        if s.get('tr') == 'static': sfx.append(dict(type='static', t=s['t0'] - STATIC_LEN / 2, vol=.7))
        if s.get('tr') == 'flash': fx.append(dict(type='flash', t=s['t0'], dur=.55))
    return shots, fx, sfx, lts


# ------------------------------------------------------------------ pictures
class Pictures:
    def __init__(self, W, H):
        self.W, self.H, self.cache, self.bg = W, H, {}, {}
        self.rng = np.random.default_rng(7)

    def img(self, p):
        if p not in self.cache: self.cache[p] = Image.open(p).convert('RGB')
        return self.cache[p]

    def view(self, s, cam):
        im = self.img(s['path']); x0, y0, x1, y1 = s.get('box', [0, 0, 1, 1])
        x0, x1, y0, y1 = x0 * im.width, x1 * im.width, y0 * im.height, y1 * im.height
        bw, bh = x1 - x0, y1 - y0; cx, cy, z = cam
        w = min(bw, bh * 16 / 9) / z; h = w * 9 / 16
        l = x0 + (bw - w) * cx; t = y0 + (bh - h) * cy
        return im, (l, t, l + w, t + h)

    def shot(self, s, t):
        if s.get('card'): return self.card(s['card'], t - s['t0'])
        u = (t - s['t0']) / max(.1, s['t1'] - s['t0'] + XF)
        a, b = s.get('from', [.5, .5, 1.0]), s.get('to', s.get('from', [.5, .5, 1.0]))
        cam = [a[i] + (b[i] - a[i]) * ease(u) for i in range(3)]
        if s.get('fit') == 'contain': return self.contain(s, cam[2])
        im, box = self.view(s, cam)
        return im.resize((self.W, self.H), Image.BICUBIC, box=box)

    def contain(self, s, z):
        im = self.img(s['path']); x0, y0, x1, y1 = s.get('box', [0, 0, 1, 1])
        src = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
        key = id(s)
        if key not in self.bg:
            bg = src.resize((self.W, self.H)).filter(ImageFilter.GaussianBlur(28))
            self.bg[key] = Image.blend(bg, Image.new('RGB', (self.W, self.H), (6, 10, 26)), .55)
        out = self.bg[key].copy()
        fh = int(self.H * .92 * z); fw = int(fh * src.width / src.height)
        if fw > self.W * .96: fw = int(self.W * .96 * z); fh = int(fw * src.height / src.width)
        out.paste(src.resize((fw, fh), Image.LANCZOS), ((self.W - fw) // 2, (self.H - fh) // 2)); return out

    def card(self, c, u):
        W, H = self.W, self.H; im = Image.new('RGB', (W, H), (12, 14, 24)); d = ImageDraw.Draw(im)
        bw = W / 7
        for k, col in enumerate(['#C0C0C0', '#C0C000', '#00C0C0', '#00C000', '#C000C0', '#C00000', '#0000C0']):
            d.rectangle((k * bw, 0, (k + 1) * bw, H * .62), fill=col)
        d.rectangle((0, H * .70, W, H), fill='#101018')
        d.rounded_rectangle((W * .13, H * .30, W * .87, H * .65), radius=26, fill='#162139', outline='#FFF4C9', width=8)
        d.text((W / 2, H * .42), c.get('title', ''), font=font(int(H * .095)), fill='#FBE35C', anchor='mm')
        d.text((W / 2, H * .535), c.get('subtitle', ''), font=font(int(H * .045), False), fill='#FFF4C9', anchor='mm')
        d.text((W / 2, H * .83), c.get('footer', ''), font=font(int(H * .035), False), fill='#FFF4C9', anchor='mm')
        a = np.asarray(im).astype(np.int16)
        if u < 1.2 or int(u * 3) % 7 == 0: a = np.roll(a, int(6 * math.sin(u * 37)), axis=1)
        a[::3] = (a[::3] * .82).astype(np.int16); a += self.rng.integers(-14, 15, (H, W, 1), dtype=np.int16)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def noise(self, t):
        g = self.rng.integers(0, 255, (self.H // 4, self.W // 4, 1), dtype=np.uint8)
        g = np.repeat(np.repeat(g, 4, 0), 4, 1).astype(np.int16)
        g += (np.sin(np.arange(self.H)[:, None, None] * .09 + t * 40) * 40).astype(np.int16)
        return np.clip(g, 0, 255).astype(np.uint8).repeat(3, 2)


def crumb(size):
    s = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(s); m = size // 14
    d.ellipse((m, m, size - m, size - m), fill='#D9A35B', outline='#5A3418', width=max(2, size // 18))
    for fx_, fy in [(.33, .33), (.6, .42), (.42, .64), (.66, .68), (.28, .53)]:
        r = size * .055; d.ellipse((fx_ * size - r, fy * size - r, fx_ * size + r, fy * size + r), fill='#6B3A1A')
    return s


def render_video(plan, shots, fx, lts, tl, pics, out, t0, t1, fps):
    W, H = pics.W, pics.H; rng = np.random.default_rng(3)
    debris = [dict(x=rng.uniform(0, W), y=rng.uniform(-400, -10), vy=rng.uniform(320, 720), vx=rng.uniform(-60, 60),
                   r=rng.uniform(3, 11) * W / 1280, c=tuple(int(v) for v in rng.choice([[214, 190, 150], [150, 120, 90], [235, 225, 205]])))
              for _ in range(120)]
    sprites = {}
    bug = plan.get('bug'); bug_on = shots[1]['t0'] if len(shots) > 1 else 0
    last_card = max([s['t0'] for s in shots if s.get('card')] + [tl.total])
    fb, fm = font(int(H * .047)), font(int(H * .031), False)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(int(round(t0 * fps)), int(round(t1 * fps))):
        t = n / fps
        k = max([i for i, s in enumerate(shots) if s['t0'] <= t + 1e-6] or [0]); s = shots[k]
        a = np.asarray(pics.shot(s, t)).astype(np.float32); since = t - s['t0']
        if k and s.get('tr', 'x') == 'x' and since < XF:
            m = ease(since / XF); a = a * m + np.asarray(pics.shot(shots[k - 1], t)).astype(np.float32) * (1 - m)
        img = Image.fromarray(a.astype(np.uint8))
        dx = dy = 0.0; flash = 0.0; stat = 0.0
        for e in fx:
            u = t - e['t']; d = e.get('dur', {'shake': .5, 'flash': .5, 'static': .45, 'debris': 3.0, 'drop': 1.6}[e['type']])
            if not 0 <= u < d: continue
            if e['type'] == 'shake':
                amp = e.get('amp', 9) * W / 1280 * (1 - u / d) ** 2; f = e.get('freq', 22)
                dx += amp * math.sin(2 * math.pi * f * u + 1.3); dy += amp * math.cos(2 * math.pi * f * .87 * u)
            elif e['type'] == 'flash': flash = max(flash, (1 - u / d) ** 1.5)
            elif e['type'] == 'static': stat = max(stat, min(1, (1 - abs(2 * u / d - 1)) * 1.6))
            elif e['type'] == 'debris':
                dr = ImageDraw.Draw(img)
                for q in debris[:int(e.get('n', 90))]:
                    y = q['y'] + q['vy'] * u + 260 * u * u; x = q['x'] + q['vx'] * u
                    if -20 < y < H + 20: dr.ellipse((x - q['r'], y - q['r'], x + q['r'], y + q['r']), fill=q['c'])
            elif e['type'] == 'drop':
                size = int(e.get('size', 90) * W / 1280)
                if size not in sprites: sprites[size] = crumb(size)
                sp = sprites[size].rotate(-400 * u, resample=Image.BICUBIC)
                y = int(-size + .5 * 1900 * H / 720 * u * u); x = int(W * e.get('x', .55) + 40 * u)
                if y < H: img.paste(sp, (x, y), sp)
        if dx or dy:
            z = img.resize((int(W * 1.04), int(H * 1.04)), Image.BILINEAR)
            ox, oy = (z.width - W) // 2 + int(dx), (z.height - H) // 2 + int(dy); img = z.crop((ox, oy, ox + W, oy + H))
        d = ImageDraw.Draw(img, 'RGBA')
        for lt in lts:
            u = t - lt['t0']; dur = lt['t1'] - lt['t0']
            if not 0 <= u < dur: continue
            sl = ease(min(u / .35, (dur - u) / .35, 1))
            bw = max(d.textbbox((0, 0), lt['name'], font=fb)[2], d.textbbox((0, 0), lt['role'], font=fm)[2]) + int(W * .047)
            x = int(-bw + (bw + W * .0375) * sl); y = int(H * .76); h1, h2 = int(H * .075), int(H * .125)
            d.rectangle((x, y, x + bw, y + h1), fill=(22, 33, 57, 235)); d.rectangle((x, y, x + int(W * .008), y + h2), fill=(251, 227, 92, 255))
            d.rectangle((x, y + h1, x + bw - int(W * .03), y + h2), fill=(244, 84, 93, 235))
            d.text((x + int(W * .022), y + int(h1 * .14)), lt['name'], font=fb, fill=(255, 244, 201))
            d.text((x + int(W * .022), y + h1 + int(H * .007)), lt['role'], font=fm, fill=(255, 255, 255))
        if bug and bug_on + .4 <= t < last_card and not s.get('card'):
            bx, by = int(W * .83), int(H * .92); fbug = font(int(H * .028))
            bw = d.textbbox((0, 0), bug, font=fbug)[2] + int(W * .045)
            d.rounded_rectangle((W - bw - int(W * .022), by, W - int(W * .022), by + int(H * .053)), radius=10, fill=(16, 24, 44, 150))
            on = int(t * 1.6) % 2 == 0; cx = W - bw - int(W * .022) + int(W * .012)
            d.ellipse((cx, by + int(H * .017), cx + int(H * .02), by + int(H * .037)), fill=(244, 84, 93, 255 if on else 90))
            d.text((cx + int(W * .02), by + int(H * .01)), bug, font=fbug, fill=(255, 244, 201, 220))
        o = np.asarray(img).astype(np.float32)
        if flash: o = o * (1 - flash) + 255 * flash
        for s2 in shots:
            if s2.get('tr') == 'static' and abs(t - s2['t0']) < STATIC_LEN / 2: stat = max(stat, min(1, (1 - abs(t - s2['t0']) / (STATIC_LEN / 2)) * 1.6))
        if stat: o = o * (1 - stat) + pics.noise(t) * stat
        if t < .25: o *= t / .25
        if t > tl.total - 1.6: o *= max(0, (tl.total - t) / 1.6)
        p.stdin.write(np.clip(o, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait(): sys.exit('ffmpeg failed')


# ------------------------------------------------------------------ sound
def tt(d): return np.arange(int(d * SR)) / SR


def synth(f, d, amp, kind):
    t = tt(d)
    if kind == 'brass': o = sum((1 / k) * np.sin(2 * np.pi * k * f * t + .17 * k * np.sin(2 * np.pi * 5 * t)) for k in range(1, 8)) / 2.7
    elif kind == 'bell': o = (np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * f * 2.04 * t) + .18 * np.sin(2 * np.pi * f * 4.11 * t)) / 1.5
    elif kind == 'bass': o = (np.sin(2 * np.pi * f * t) + .22 * np.sin(2 * np.pi * f * 2 * t)) / .95
    else: o = (np.sin(2 * np.pi * f * t) + .37 * np.sin(2 * np.pi * f * 1.004 * t) + .16 * np.sin(2 * np.pi * f * 2 * t)) / 1.6
    a, r = min(.06, d * .23), min(.16, d * .24)
    env = np.maximum(0, np.minimum(1, t / max(a, 1e-4)) * np.minimum(1, (d - t) / max(r, 1e-4)))
    if kind == 'bell': env *= np.exp(-t * 2.3 / max(d, .2))
    return (amp * o * env).astype(np.float32)


def put(buf, t, x):
    i = int(t * SR)
    if i < 0: x = x[-i:]; i = 0
    j = min(len(buf), i + len(x))
    if j > i: buf[i:j] += x[:j - i]


def midi(m): return 440 * 2 ** ((m - 69) / 12)


def sfx_sound(kind, rng):
    def noise(d): return rng.standard_normal(len(tt(d))).astype(np.float32)
    if kind == 'thud': t = tt(.5); return (.35 * np.sin(2 * np.pi * (70 - 30 * t / .5) * t) * np.exp(-t * 7)).astype(np.float32)
    if kind == 'crash':
        t = tt(1.0); q = np.convolve(noise(1.0), np.ones(120) / 120, 'same') * 8
        return ((.33 * q + .15 * np.sin(2 * np.pi * (125 - 55 * t) * t)) * np.exp(-t * 4)).astype(np.float32)
    if kind == 'static': t = tt(.45); return (.10 * np.convolve(noise(.45), [1., -.45], 'same') * np.exp(-t * 3)).astype(np.float32)
    if kind == 'tink': t = tt(.3); return (.12 * (np.sin(2 * np.pi * 1900 * t) + .6 * np.sin(2 * np.pi * 2550 * t)) * np.exp(-t * 18)).astype(np.float32)
    if kind == 'crunch': t = tt(.18); return (.10 * noise(.18) * (rng.random(len(t)) < .25) * np.exp(-t * 14)).astype(np.float32)
    if kind == 'rumble':
        t = tt(1.6); q = np.convolve(noise(1.6), np.ones(180) / 180, 'same') * 6
        return (.18 * q * np.minimum(1, t * 8) * np.exp(-t * 2.2)).astype(np.float32)
    if kind == 'whoosh':
        t = tt(.6); q = np.convolve(noise(.6), np.ones(30) / 30, 'same') * 3
        return (.12 * q * np.sin(np.pi * t / .6) ** 2).astype(np.float32)
    if kind == 'bell': return synth(midi(84), .5, .07, 'bell') + np.pad(synth(midi(88), .4, .05, 'bell'), (int(.12 * SR), 0))[:int(.5 * SR)]
    if kind == 'sting':
        out = np.zeros(int(1.0 * SR), np.float32)
        for dt, m in [(0, 72), (.15, 76), (.32, 79), (.48, 84)]: put(out, dt, synth(midi(m), .34, .11, 'brass'))
        return out
    raise ValueError(kind)


def music_bed(total, speech, bpm=112, rng=None):
    base = np.zeros(int((total + .1) * SR), np.float32); beat = 60 / bpm
    chords = [[48, 52, 55], [45, 48, 52], [53, 57, 60], [43, 47, 50]]
    for bar in range(int(total / (beat * 4)) + 1):
        t = bar * beat * 4; ch = chords[bar % 4]
        for k in ch: put(base, t, synth(midi(k), beat * 3.8, .012, 'pad'))
        for j in range(4):
            put(base, t + j * beat, synth(midi(ch[0] - 12), .20, .021, 'bass'))
            if j in (1, 3): x = tt(.07); put(base, t + j * beat, (rng.standard_normal(len(x)) * np.exp(-x * 65) * .014).astype(np.float32))
        if bar % 2 == 0:
            for off, m in [(.5, 67), (1.5, 72), (2.5, 76)]: put(base, t + beat * off, synth(midi(m), .15, .018, 'bell'))
    duck = np.full(len(base), .88, np.float32)
    for s0, s1 in speech: duck[max(0, int((s0 - .14) * SR)):int((s1 + .2) * SR)] = .40
    k = int(.085 * SR); duck = np.convolve(duck, np.ones(k) / k, 'same')
    base *= duck; base *= np.minimum(1, np.maximum(0, (total - np.arange(len(base)) / SR) / 1.6))
    return base


def mix_audio(plan, base, tl, sfx, tmp):
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(base / plan['audio']), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    voice = np.frombuffer(pcm, np.float32).copy()
    n = max(len(voice), int(tl.total * SR)); mix = np.zeros(n, np.float32); mix[:len(voice)] += voice
    rng = np.random.default_rng(1307); m = plan.get('music')
    if m:
        if m.get('file'):
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-stream_loop', '-1', '-i', str(base / m['file']), '-t', f'{tl.total:.3f}', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                                 capture_output=True, check=True).stdout
            bed = np.frombuffer(raw, np.float32).copy() * .12
        else:
            bed = music_bed(tl.total, tl.sp, m.get('bpm', 112), rng)
        mix[:min(n, len(bed))] += bed[:n] * m.get('volume', .84)
    for e in sfx: put(mix, e['t'], sfx_sound(e['type'], rng) * e.get('vol', 1.0))
    raw_path = Path(tmp) / 'mix_raw.wav'
    with wave.open(str(raw_path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix / max(1, np.abs(mix).max() / .95), -1, 1) * 32767).astype(np.int16).tobytes())
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw_path), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', meas)[-1])
    return raw_path, -14 - I


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan', type=Path); ap.add_argument('--out', type=Path)
    ap.add_argument('--check', action='store_true'); ap.add_argument('--contact-sheet', action='store_true')
    ap.add_argument('--clip', nargs=2, type=float)
    a = ap.parse_args()
    base = a.plan.resolve().parent; plan = json.loads(a.plan.read_text(encoding='utf-8'))
    probs = lint(plan, base)
    if a.check:
        for p in probs: print('PROBLEM:', p)
        print(f'plan check: {len(plan["scenes"])} scenes, {len(flat_lines(plan))} lines, '
              f'{sum(len(all_shots(l)) for *_, l in flat_lines(plan))} shots, {len(probs)} problems'); sys.exit(1 if probs else 0)
    if probs:
        for p in probs: print('PROBLEM:', p)
        sys.exit('fix the plan first (--check)')
    W = int(plan.get('width', 1280)); W -= W % 2; H = W * 9 // 16; H -= H % 2; fps = int(plan.get('fps', 24))
    out = a.out or base / 'final.mp4'; pics = Pictures(W, H)
    if a.contact_sheet:
        tl_shots = [sh for *_, ln in flat_lines(plan) for sh in all_shots(ln)]; tiles = []
        for i, sh in enumerate(tl_shots):
            if sh.get('card'): continue
            s = dict(sh, path=base / plan.get('images', {}).get(sh['image'], sh['image']))
            for key in ('from', 'to'):
                cam = s.get(key, s.get('from', [.5, .5, 1]))
                th = (pics.contain(s, cam[2]) if s.get('fit') == 'contain' else (lambda im_b: im_b[0].resize((W, H), Image.BICUBIC, box=im_b[1]))(pics.view(s, cam))).resize((320, 180))
                ImageDraw.Draw(th).text((4, 2), f'{i + 1} {key}', font=font(16), fill='yellow', stroke_width=2, stroke_fill='black'); tiles.append(th)
        cols = 6; sheet = Image.new('RGB', (cols * 320, math.ceil(len(tiles) / cols) * 180))
        for j, t in enumerate(tiles): sheet.paste(t, ((j % cols) * 320, (j // cols) * 180))
        p = out.with_name(out.stem + '_contact.png'); sheet.save(p); print('wrote', p); return
    tl = Timeline(plan, base); shots, fx, sfx, lts = build(plan, base, tl)
    t0, t1 = (a.clip[0], min(a.clip[1], tl.total)) if a.clip else (0.0, tl.total)
    for w in dict.fromkeys(tl.warn): print('  note:', w)
    with tempfile.TemporaryDirectory() as tmp:
        vid = Path(tmp) / 'video.mp4'
        render_video(plan, shots, fx, lts, tl, pics, vid, t0, t1, fps)
        raw, gain = mix_audio(plan, base, tl, sfx, tmp)
        def ts(x):
            ms = round(max(0, x) * 1000); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
            return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
        rows = [(max(tl.sp[k][0], t0) - t0, min(tl.sp[k][1], t1) - t0, ln.get('display', ln['text'])) for k, (*_, ln) in enumerate(tl.lines) if tl.sp[k][1] > t0 and tl.sp[k][0] < t1]
        srt = out.with_suffix('.srt'); srt.write_text('\n'.join(f'{i}\n{ts(s)} --> {ts(e)}\n{x}\n' for i, (s, e, x) in enumerate(rows, 1)), encoding='utf-8')
        meta = [';FFMETADATA1', f"title={plan.get('title', '')}"]; firsts = {}
        for k, (si, *_) in enumerate(tl.lines): firsts.setdefault(si, tl.start[k])
        for si, sc in enumerate(plan['scenes']):
            s, e = firsts[si], firsts.get(si + 1, tl.total)
            if e > t0 and s < t1:
                meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={round(max(0, s - t0) * 1000)}', f'END={round((min(e, t1) - t0) * 1000)}', f"title={si + 1:02d}. {sc.get('title', 'Scene')}"]
        mf = Path(tmp) / 'chapters.txt'; mf.write_text('\n'.join(meta) + '\n', encoding='utf-8')
        def mux(g):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(vid), '-ss', f'{t0:.3f}', '-t', f'{t1 - t0:.3f}', '-i', str(raw), '-i', str(srt), '-i', str(mf),
                            '-map', '0:v', '-map', '1:a', '-map', '2:s', '-map_metadata', '3', '-map_chapters', '3',
                            '-af', f'volume={g:.2f}dB,alimiter=limit=0.84:level=false', '-ac', '2', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                            '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-movflags', '+faststart', str(out)], check=True)
            m = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(out), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
            return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', m)[-1])
        got = mux(gain)
        if abs(got + 14) > 0.5: got = mux(gain - 14 - got)       # one correction pass
        print(f'loudness {got:.1f} LUFS')
    print(f'wrote {out} ({t1 - t0:.1f}s of {tl.total:.1f}s; {len(shots)} shots, {len(fx)} effects, {len(sfx)} sounds)')


if __name__ == '__main__':
    main()
