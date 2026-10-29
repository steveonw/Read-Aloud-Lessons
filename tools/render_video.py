#!/usr/bin/env python3
"""Narrated slideshow renderer: still boards + narration -> MP4.

  python render_video.py plan.json                    # final video
  python render_video.py plan.json --audio-dir audio  # per-scene files sceneNN.wav/.mp3/...
  python render_video.py plan.json --preview          # silent, estimated timing
  python render_video.py plan.json --clip 300 330     # render only 300-330 s (quick check)
  python render_video.py plan.json --contact-sheet    # one thumbnail per line's camera target
  python render_video.py plan.json --export-tts tts   # write tts/sceneNN.txt + narration_all.txt
  python render_video.py plan.json --check            # lint the plan before making any audio

plan.json:
{
  "title": "My video",
  "width": 1920, "fps": 24, "captions": false,       # optional (these are the defaults)
  "presets": {"graph": [0.28, 0.55, 1.7]},           # optional named cameras
  "audio": "narration.wav",                          # optional: ONE file for the whole video...
  "timestamps": "labels.txt",                        # ...with per-sentence times
  "audio_offset": 0.0,                               # optional seconds to skip (e.g. MP3 delay)
  "mark_color": "#FFD36F",                           # optional marker colour
  "scenes": [
    {"image": "board01.png",
     "panel": [0, 0, 0.5, 0.5],                      # optional [left, top, width, height]
     "audio": "audio/scene01.wav",                   # optional per-scene audio instead
     "marks": {"E1": {"box": [0.54, 0.25, 0.80, 0.33]},     # panel-relative shapes
               "max": {"ring": [0.21, 0.42], "r": 0.032},
               "key": {"underline": [0.05, 0.95, 0.60]}},
     "lines": [
       {"text": "Sentence spoken by the TTS."},
       {"text": "Next sentence.", "mark": "E1"},
       {"text": "Another.", "mark": ["E1", "max"], "seconds": 4.2},
       {"text": "Rare close-up.", "camera": [0.3, 0.4, 1.5]}
     ]}
  ]
}
Marks (the default way to point): a box, underline or ring drawn over the board for the
sentence that names it. It fades in when that sentence starts speaking and out when the
next sentence starts (so it stays up through a pause, e.g. a quiz question's think time),
and stays solid across consecutive sentences with the same mark. "marks" can be given per
scene or for the whole plan; a line's "mark" is a name, a list of names, or an inline shape.
Timing, best first: (1) one audio file + "timestamps" (Audacity labels, SRT, VTT or JSON
[{start,end,text}]); entries are matched to plan lines by text, and unmatched entries
(e.g. spoken scene titles) are absorbed into the next line. A new scene appears in the
pause before its first speech (at most 1.2 s early, so a quiz think pause keeps the old
board up), and its cross-fade or glide finishes before that speech starts.
(2) per-scene audio: scene length = file length, lines split by word count unless "seconds"
is given. (3) estimate (--preview), including each line's "pause_after".
A final render needs narration for every scene; use --preview for a silent draft.
Boards that are not 16:9 are letterboxed and their panels/marks are moved to match.
camera = [center_x, center_y, zoom] inside the scene's panel (or whole image): 0..1 from
top-left, zoom 1 = whole panel; or a preset name ("wide" = [0.5, 0.5, 1] is built in).
No camera (or "hold") = stay where the previous line was; a scene's first line defaults
to wide, so a plan with no cameras shows each whole panel, still. When a line does set a
camera it moves once at the start of the line, then holds, and never shows neighbouring
panels. Scenes sharing an image glide across it; a new image cross-fades in.
Scene "title" fields become chapter markers. Paths relative to plan.json.
Needs: ffmpeg/ffprobe, Pillow.  Writes <out>.mp4 (with chapters and a subtitle track viewers
can switch on), <out>.srt, <out>_timing.json.
"""
import argparse, difflib, json, math, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WPM = 150          # speaking-rate guess when there is no audio
LINE_PAD = 0.42    # pause per line in estimated timing
FADE = 0.6         # cross-fade seconds when the image changes
SCENE_LEAD = 1.2   # a new scene appears at most this long before its first speech
AUDIO_EXT = ('.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac')
QUIZ = re.compile(r'quiz|test yourself|question|your turn|pause|think|try it', re.I)
SPOKEN_BAD = re.compile(r'[0-9%=^/\\$<>*_{}|#@&+]')   # digits/symbols a TTS may misread


def words(s):
    return max(1, len(re.findall(r"[\w'-]+", s)))


def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'default=nw=1:nk=1', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def find_font(size):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/System/Library/Fonts/Supplemental/Arial.ttf', 'C:/Windows/Fonts/arial.ttf',
              '/usr/share/fonts/TTF/DejaVuSans.ttf']:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def read_timestamps(path):
    """Audacity labels / SRT / VTT / JSON -> [(start, end, text)]."""
    raw = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() == '.json':
        d = json.loads(raw)
        d = d.get('segments', d.get('sentences', d)) if isinstance(d, dict) else d
        return [(float(e['start']), float(e['end']), e.get('text', '')) for e in d]
    def sec(t):
        h, m, s = (['0'] + t.replace(',', '.').split(':'))[-3:]
        return int(h) * 3600 + int(m) * 60 + float(s)
    if '-->' in raw:                                           # SRT / VTT
        out = []
        for block in re.split(r'\n\s*\n', raw.strip()):
            ls = [l for l in block.splitlines() if l.strip()]
            for k, l in enumerate(ls):
                if '-->' in l:
                    a, b = [x.strip().split()[0] for x in l.split('-->')]
                    out.append((sec(a), sec(b), ' '.join(ls[k + 1:])))
                    break
        return out
    out = []                                                   # Audacity: start<TAB>end<TAB>text
    for l in raw.splitlines():
        p = l.split('\t')
        if len(p) >= 2 and not l.startswith('\\'):
            out.append((float(p[0]), float(p[1]), p[2] if len(p) > 2 else ''))
    return out


def match_lines(plan_lines, labels):
    """Match plan lines to timestamp entries in order. Returns entry index per line."""
    idx, j, report = [], 0, []
    for k, text in enumerate(plan_lines):
        best, best_r = None, 0.0
        for c in range(j, min(len(labels), j + 20)):
            r = difflib.SequenceMatcher(None, norm(text), norm(labels[c][2])).ratio()
            if r > best_r: best, best_r = c, r
        if best is None or best_r < 0.6:
            sys.exit(f'line {k + 1} not found in timestamps near entry {j + 1}: "{text[:70]}"')
        if best_r < 0.9: report.append(f'loose match ({best_r:.2f}): "{text[:50]}" ~ "{labels[best][2][:50]}"')
        report += [f'extra entry absorbed: "{labels[c][2][:60]}"' for c in range(j, best)]
        idx.append(best); j = best + 1
    report += [f'extra entry absorbed: "{labels[c][2][:60]}"' for c in range(j, len(labels))]
    return idx, report


def to_abs(cam, panel, presets):
    """Panel-relative camera (list or preset name) -> absolute [cx, cy, zoom] on the image."""
    if isinstance(cam, str):
        if cam not in presets:
            sys.exit(f'unknown camera preset: {cam}')
        cam = presets[cam]
    l, t, w, h = panel
    cx, cy, z = (float(v) for v in cam)
    z = max(1.0, z / max(w, h))
    hw = 0.5 / z                                       # keep the view inside the panel
    cx = l + w / 2 if 2 * hw >= w else min(max(l + cx * w, l + hw), l + w - hw)
    cy = t + h / 2 if 2 * hw >= h else min(max(t + cy * h, t + hw), t + h - hw)
    return [cx, cy, z]


def fit_panel(size, panel):
    """Panel on the original image -> panel on its 16:9 letterboxed canvas (see load_16x9)."""
    w0, h0 = size
    if abs(w0 / h0 - 16 / 9) <= 0.01:
        return list(panel)
    W = max(w0, round(h0 * 16 / 9)); H = round(W * 9 / 16)
    ox, oy, sx, sy = (W - w0) // 2 / W, (H - h0) // 2 / H, w0 / W, h0 / H
    l, t, w, h = panel
    return [ox + l * sx, oy + t * sy, w * sx, h * sy]


def lint(plan, base):
    """Problems in plan.json that would waste a narration or a render."""
    out, cast = [], plan.get('cast', {})
    for si, sc in enumerate(plan['scenes']):
        tag = f"S{si + 1}"
        if not (base / sc.get('image', '')).is_file():
            out.append(f"{tag}: image not found: {sc.get('image')}")
        p = sc.get('panel', [0, 0, 1, 1])
        if len(p) != 4 or min(p) < 0 or p[0] + p[2] > 1.001 or p[1] + p[3] > 1.001:
            out.append(f'{tag}: panel {p} is not inside the image')
        named = {**plan.get('marks', {}), **sc.get('marks', {})}
        for name, m in named.items():
            vals = m.get('box') or m.get('underline') or m.get('ring')
            if not vals or any(not 0 <= v <= 1 for v in vals[:4]):
                out.append(f'{tag}: mark "{name}" needs box/underline/ring with values in 0..1')
        prev = ''
        for li, ln in enumerate(sc.get('lines', [])):
            t, where = ln.get('text', ''), f'{tag}.{li + 1}'
            if not t.strip(): out.append(f'{where}: empty text')
            if SPOKEN_BAD.search(t): out.append(f'{where}: digits or symbols in spoken text: "{t[:50]}"')
            for m in (ln.get('mark') or []) if isinstance(ln.get('mark'), list) else [ln.get('mark')]:
                if isinstance(m, str) and m not in named: out.append(f'{where}: unknown mark "{m}"')
            spk = ln.get('speaker', sc.get('speaker'))
            if spk is not None and spk not in cast: out.append(f'{where}: speaker "{spk}" not in "cast"')
            if t.rstrip().endswith('?') and (QUIZ.search(t) or QUIZ.search(prev)) \
                    and ln.get('pause_after', 0) < 4:
                out.append(f'{where}: quiz question needs "pause_after": 4 or more')
            prev = t
    return out


def scene_audio(sc, idx, base, audio_dir):
    if sc.get('audio'):
        return base / sc['audio']
    if audio_dir:
        for ext in AUDIO_EXT:
            p = audio_dir / f'scene{idx + 1:02d}{ext}'
            if p.exists():
                return p
    return None


def timeline(plan, base, use_audio, audio_dir):
    """-> rows (one per line, absolute start/end), audio [(path|None, seconds, offset)], total, notes."""
    presets = {'wide': [0.5, 0.5, 1.0], **plan.get('presets', {})}
    flat = [(si, li, sc, ln) for si, sc in enumerate(plan['scenes']) for li, ln in enumerate(sc['lines'])]
    times, audio, notes = None, [], []
    if use_audio and plan.get('audio') and not plan.get('timestamps'):
        sys.exit('plan has "audio" but no "timestamps"; add the timestamp file or use per-scene audio')
    if use_audio and plan.get('audio') and plan.get('timestamps'):      # one file + timestamps
        a = base / plan['audio']; off = float(plan.get('audio_offset', 0))
        if not a.exists(): sys.exit(f'missing audio: {a}')
        labels = read_timestamps(base / plan['timestamps'])
        idx, notes = match_lines([ln['text'] for *_, ln in flat], labels)
        total = probe(a) - off
        # a line starts with the entry after the previous line (spoken titles fold in); a new
        # scene starts inside the pause before it, at most SCENE_LEAD s early, so the move
        # happens in silence but a long pause (quiz think time) keeps the old board up
        starts = [0.0 if k == 0 else
                  max(labels[idx[k - 1]][1], labels[idx[k - 1] + 1][0] - SCENE_LEAD) if flat[k][1] == 0
                  else labels[idx[k - 1] + 1][0] for k in range(len(idx))]
        times = [(starts[k], starts[k + 1] if k + 1 < len(starts) else total) for k in range(len(starts))]
        speech = [labels[i][0] for i in idx]           # when this sentence itself begins
        audio = [(a, total, off)]
    else:                                                               # per-scene or estimated
        times, t = [], 0.0
        for si, sc in enumerate(plan['scenes']):
            lines = sc['lines']
            est = [ln.get('seconds', LINE_PAD + words(ln['text']) * 60 / WPM + ln.get('pause_after', 0))
                   for ln in lines]
            a = scene_audio(sc, si, base, audio_dir) if use_audio else None
            if a is not None and not a.exists():
                sys.exit(f'missing audio: {a}')
            if a is not None:
                dur = probe(a)
                fixed = sum(ln['seconds'] for ln in lines if 'seconds' in ln)
                free = sum(words(ln['text']) for ln in lines if 'seconds' not in ln)
                rest = max(0.0, dur - fixed)
                per = ([ln['seconds'] if 'seconds' in ln else rest * words(ln['text']) / free
                        for ln in lines] if free else [d * dur / sum(est) for d in est])
            else:
                per, dur = est, sum(est)
            audio.append((a, dur, 0.0))
            for d in per:
                times.append((t, t + d)); t += d
        total = t
        speech = [s for s, _ in times]
    rows, sizes = [], {}
    for (si, li, sc, ln), (s, e), sp in zip(flat, times, speech):
        if sc['image'] not in sizes:
            with Image.open(base / sc['image']) as im: sizes[sc['image']] = im.size
        panel = fit_panel(sizes[sc['image']], sc.get('panel', [0, 0, 1, 1]))
        named = {**presets, **sc.get('presets', {})}   # scene presets override plan presets
        wide = to_abs('wide', panel, named)
        cam = ln.get('camera', 'hold')                 # no camera = stay where we are
        if cam == 'hold':
            cam_abs = rows[-1]['cam'] if li else wide
        else:
            cam_abs = to_abs(cam, panel, named)
        marks = {**plan.get('marks', {}), **sc.get('marks', {})}
        rows.append(dict(scene=si, line=li, image=sc['image'], text=ln['text'], start=s, end=e,
                         speech=sp, cam=cam_abs, wide=wide,
                         marks=resolve_marks(ln.get('mark'), panel, marks)))
    return rows, audio, total, notes


def resolve_marks(spec, panel, named):
    """Mark name(s) or inline shapes (panel-relative) -> absolute shapes on the image."""
    if not spec:
        return []
    out = []
    for m in (spec if isinstance(spec, list) else [spec]):
        if isinstance(m, str):
            if m not in named:
                sys.exit(f'unknown mark: {m}')
            m = named[m]
        l, t, w, h = panel
        X = lambda v: l + v * w
        Y = lambda v: t + v * h
        if 'box' in m:
            x0, y0, x1, y1 = m['box']; out.append(('box', X(x0), Y(y0), X(x1), Y(y1)))
        elif 'underline' in m:
            x0, y, x1 = m['underline']; out.append(('underline', X(x0), Y(y), X(x1)))
        elif 'ring' in m:
            x, y = m['ring'][:2]; out.append(('ring', X(x), Y(y), m.get('r', 0.035) * h))
        else:
            sys.exit(f'mark needs box, underline or ring: {m}')
    return out


def motion_report(rows):
    """Count camera moves and flag restless patterns."""
    moves, flips, quick = 0, 0, []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a['scene'] != b['scene'] or a['cam'] == b['cam']:
            continue
        moves += 1
        if i >= 2 and rows[i - 2]['scene'] == b['scene'] and rows[i - 2]['cam'] == b['cam']:
            flips += 1
        if b['end'] - b['start'] < 2.5:
            quick.append(f"S{b['scene']+1}.{b['line']+1}")
    mins = max(1e-9, (rows[-1]['end'] - rows[0]['start']) / 60)
    msg = f'camera: {moves} moves inside scenes ({moves / mins:.1f}/min), {flips} back-and-forth (A-B-A)'
    if quick: msg += f', moves on short lines (<2.5 s): {", ".join(quick[:12])}'
    return msg


def load_16x9(path):
    im = Image.open(path).convert('RGB')
    target = 16 / 9
    if abs(im.width / im.height - target) > 0.01:      # letterbox, never stretch (fit_panel matches)
        bg = im.getpixel((2, 2))
        W = max(im.width, round(im.height * target)); H = round(W * 9 / 16)
        canvas = Image.new('RGB', (W, H), bg)
        canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        im = canvas
    return im


def smooth(u):
    u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)


def glide(a, b, v):
    """Pan linearly, zoom in log space so zooming feels even."""
    return [a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v,
            math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * v)]


def camera_at(rows, i, t):
    """Move once at the start of a line, then hold still on the subject."""
    r = rows[i]
    p = rows[i - 1] if i else None
    old = p['cam'] if p and p['image'] == r['image'] else r['wide']
    new = r['cam']
    if old == new:
        return new
    zmax = max(old[2], new[2])
    dist = math.hypot(old[0] - new[0], old[1] - new[1]) * zmax       # in screen widths
    span = r['end'] - r['start']
    T = max(0.4, min(0.7 * span, 1.2 + 0.4 * min(dist, 2.5)))        # ~1.2-2.2 s
    if p and p['scene'] != r['scene']:                               # panel move ends before speech
        T = max(0.8, min(T, r['speech'] - r['start']))
    u = smooth((t - r['start']) / T)
    if p and p['scene'] != r['scene'] and dist > 1.2:                # panel to panel: lift, glide, settle
        mid = [(old[0] + new[0]) / 2, (old[1] + new[1]) / 2, max(1.0, min(old[2], new[2]) * 0.8)]
        return glide(old, mid, u * 2) if u < 0.5 else glide(mid, new, u * 2 - 1)
    return glide(old, new, u)


def view_rect(im, cam):
    """Pixel rectangle of the image that the camera shows: (x0, y0, width, height)."""
    cx, cy, z = cam
    cw, ch = im.width / z, im.height / z
    x0 = min(max(cx * im.width - cw / 2, 0), im.width - cw)
    y0 = min(max(cy * im.height - ch / 2, 0), im.height - ch)
    return x0, y0, cw, ch


def crop(im, cam, w, h, resample=Image.BILINEAR):
    x0, y0, cw, ch = view_rect(im, cam)
    return im.resize((w, h), resample, box=(x0, y0, x0 + cw, y0 + ch))


def mark_layer(shapes, im, cam, W, H, color):
    """Draw marks once (anti-aliased) -> (RGBA patch, (x, y)) to paste onto the frame."""
    x0, y0, cw, ch = view_rect(im, cam)
    sx = lambda X: (X * im.width - x0) / cw * W
    sy = lambda Y: (Y * im.height - y0) / ch * H
    lw = max(2.0, H / 300)
    items, xs, ys = [], [], []
    for s in shapes:
        if s[0] == 'box':
            a, b, c, d = sx(s[1]), sy(s[2]), sx(s[3]), sy(s[4]); items.append(('box', a, b, c, d))
            xs += [a, c]; ys += [b, d]
        elif s[0] == 'underline':
            a, b, c = sx(s[1]), sy(s[2]), sx(s[3]); items.append(('line', a, b, c))
            xs += [a, c]; ys += [b, b]
        else:
            x, y, r = sx(s[1]), sy(s[2]), s[3] * im.height / ch * H; items.append(('ring', x, y, r))
            xs += [x - r, x + r]; ys += [y - r, y + r]
    if not items:
        return None
    pad = int(lw * 4)
    bx0, by0 = int(max(0, min(xs) - pad)), int(max(0, min(ys) - pad))
    bx1, by1 = int(min(W, max(xs) + pad)), int(min(H, max(ys) + pad))
    if bx1 <= bx0 or by1 <= by0:
        return None
    SS = 3                                              # supersample for smooth edges
    layer = Image.new('RGBA', ((bx1 - bx0) * SS, (by1 - by0) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rgb = Image.new('RGB', (1, 1), color).getpixel((0, 0))
    P = lambda v, o: (v - o) * SS
    for it in items:
        if it[0] == 'box':
            box = [P(it[1], bx0), P(it[2], by0), P(it[3], bx0), P(it[4], by0)]
            rad = int(min(box[2] - box[0], box[3] - box[1]) * 0.18)
            d.rounded_rectangle(box, radius=rad, fill=rgb + (34,))
            d.rounded_rectangle(box, radius=rad, outline=rgb + (235,), width=int(lw * SS))
        elif it[0] == 'line':
            w = int(lw * 1.6 * SS); y = P(it[2], by0)
            d.line([P(it[1], bx0), y, P(it[3], bx0), y], fill=rgb + (240,), width=w)
            for xe in (P(it[1], bx0), P(it[3], bx0)):
                d.ellipse([xe - w / 2, y - w / 2, xe + w / 2, y + w / 2], fill=rgb + (240,))
        else:
            x, y, r = P(it[1], bx0), P(it[2], by0), it[3] * SS
            d.ellipse([x - r * 1.25, y - r * 1.25, x + r * 1.25, y + r * 1.25], outline=rgb + (70,), width=int(lw * 2 * SS))
            d.ellipse([x - r, y - r, x + r, y + r], fill=rgb + (30,), outline=rgb + (240,), width=int(lw * SS))
    return layer.resize((bx1 - bx0, by1 - by0), Image.LANCZOS), (bx0, by0)


MARK_IN, MARK_OUT = 0.25, 0.2                           # fade seconds


def mark_alpha(rows, i, t):
    """Fade in when the sentence starts speaking, out at its end; no flicker if the mark repeats."""
    r = rows[i]
    if not r['marks'] or t < r['speech']:
        return 0.0
    same_prev = i and rows[i - 1]['marks'] == r['marks'] and rows[i - 1]['scene'] == r['scene']
    same_next = i + 1 < len(rows) and rows[i + 1]['marks'] == r['marks'] and rows[i + 1]['scene'] == r['scene']
    a_in = 1.0 if same_prev else min(1.0, (t - r['speech']) / MARK_IN)
    a_out = 1.0 if same_next else min(1.0, max(0.0, (r['end'] - t) / MARK_OUT))
    return smooth(min(a_in, a_out))


def apply_marks(frame, rows, i, t, img, cam, color, cache):
    a = mark_alpha(rows, i, t)
    if a <= 0:
        return frame
    key = (i, tuple(round(v, 5) for v in cam))
    if key not in cache:
        if len(cache) > 64: cache.clear()
        cache[key] = mark_layer(rows[i]['marks'], img, cam, frame.width, frame.height, color)
    got = cache[key]
    if not got:
        return frame
    patch, pos = got
    if a < 0.999:
        patch = patch.copy(); patch.putalpha(patch.getchannel('A').point(lambda v: int(v * a)))
    frame.paste(patch, pos, patch)
    return frame


def caption(text, w, font):
    pad = int(font.size * 0.6)
    d = ImageDraw.Draw(Image.new('RGB', (2, 2)))
    lines, cur = [], ''
    for word in text.split():
        trial = (cur + ' ' + word).strip()
        if d.textlength(trial, font=font) <= w - 8 * pad: cur = trial
        else: lines.append(cur); cur = word
    lines.append(cur)
    lh = int(font.size * 1.3); bh = lh * len(lines) + 2 * pad
    band = Image.new('RGBA', (w, bh), (0, 0, 0, 0)); dd = ImageDraw.Draw(band)
    dd.rounded_rectangle([3 * pad, 0, w - 3 * pad, bh], radius=pad, fill=(8, 12, 16, 190))
    for j, ln in enumerate(lines):
        dd.text((w / 2, pad + j * lh), ln, font=font, fill=(250, 248, 238, 255), anchor='mt')
    return band


def srt(rows, path, t0=0.0, t1=1e9):
    def ts(s):
        ms = round(s * 1000); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    keep = [r for r in rows if r['end'] > t0 and r['start'] < t1]   # caption from its own speech
    path.write_text('\n'.join(f"{k}\n{ts(max(r['speech'], t0) - t0)} --> {ts(min(r['end'], t1) - t0)}\n{r['text']}\n"
                              for k, r in enumerate(keep, 1)), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--audio-dir', type=Path, help='folder with scene01.wav/.mp3/... (scene number order)')
    ap.add_argument('--preview', action='store_true', help='ignore audio, silent estimated timing')
    ap.add_argument('--clip', nargs=2, type=float, metavar=('START', 'END'), help='render only this time range')
    ap.add_argument('--contact-sheet', action='store_true', help="PNG of every line's camera target")
    ap.add_argument('--export-tts', type=Path, metavar='DIR', help='write sceneNN.txt files for TTS')
    ap.add_argument('--no-captions', action='store_true')
    ap.add_argument('--check', action='store_true', help='lint plan.json and exit (non-zero on problems)')
    a = ap.parse_args()
    base = a.plan.resolve().parent
    plan = json.loads(a.plan.read_text(encoding='utf-8'))
    problems = lint(plan, base)
    if a.check:
        for p in problems: print('PROBLEM:', p)
        n = sum(len(sc['lines']) for sc in plan['scenes'])
        print(f'plan check: {len(plan["scenes"])} scenes, {n} lines, {len(problems)} problems')
        sys.exit(1 if problems else 0)
    for p in problems: print('  warning:', p)

    if a.export_tts:
        a.export_tts.mkdir(parents=True, exist_ok=True)
        texts = ['\n'.join(ln['text'] for ln in sc['lines']) for sc in plan['scenes']]
        for k, txt in enumerate(texts, 1):
            (a.export_tts / f'scene{k:02d}.txt').write_text(txt + '\n', encoding='utf-8')
        (a.export_tts / 'narration_all.txt').write_text('\n\n'.join(texts) + '\n', encoding='utf-8')
        print(f'wrote {len(texts)} scene files to {a.export_tts}'); return

    W = int(plan.get('width', 1920)); W -= W % 2; H = W * 9 // 16; H -= H % 2
    fps = int(plan.get('fps', 24))
    out = a.out or base / ('preview.mp4' if a.preview else 'final.mp4')
    audio_dir = (a.audio_dir.resolve() if a.audio_dir else None)
    rows, audio, total, notes = timeline(plan, base, not a.preview, audio_dir)
    for n in notes: print('  note:', n)
    if any(r['cam'] != r['wide'] for r in rows): print(motion_report(rows))
    if not a.preview and not a.contact_sheet:          # a final render must have narration
        missing = [f'S{k + 1}' for k, (p, *_) in enumerate(audio) if p is None]
        if missing:
            sys.exit(f'no narration for {", ".join(missing) if len(missing) < len(audio) else "the video"}; '
                     'give "audio" + "timestamps", per-scene audio, or use --preview for a silent draft')
    cache = {}
    def img(name):
        if name not in cache:
            cache[name] = load_16x9(base / name)
        return cache[name]
    font = find_font(max(18, H // 26))
    mark_color = plan.get('mark_color', '#FFD36F')

    if a.contact_sheet:
        tw, th = 480, 270; cols = 4; n = len(rows)
        sheet = Image.new('RGB', (cols * tw, math.ceil(n / cols) * (th + 44)), (20, 20, 20))
        d = ImageDraw.Draw(sheet); f = find_font(15)
        for k, r in enumerate(rows):
            x, y = (k % cols) * tw, (k // cols) * (th + 44)
            thumb = crop(img(r['image']), r['cam'], tw, th)
            got = mark_layer(r['marks'], img(r['image']), r['cam'], tw, th, mark_color) if r['marks'] else None
            if got: thumb.paste(got[0], got[1], got[0])
            sheet.paste(thumb, (x, y))
            d.text((x + 6, y + th + 4), f"S{r['scene']+1}.{r['line']+1}  {r['text'][:52]}", font=f, fill='white')
        p = out.with_name(out.stem + '_contact.png'); sheet.save(p); print('wrote', p); return

    t0, t1 = (max(0.0, a.clip[0]), min(total, a.clip[1])) if a.clip else (0.0, total)
    has_audio = any(p for p, *_ in audio)
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(fps), '-i', 'pipe:0']
    parts, flt = [], []
    for k, (p, d, off) in enumerate(audio if has_audio else [(None, total, 0.0)]):
        if p: cmd += (['-ss', f'{off:.4f}'] if off else []) + ['-i', str(p)]
        else: cmd += ['-f', 'lavfi', '-t', f'{d:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
        flt.append(f'[{k+1}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,'
                   f'apad,atrim=0:{d:.4f},asetpts=PTS-STARTPTS[a{k}]')
        parts.append(f'[a{k}]')
    flt.append(''.join(parts) + f'concat=n={len(parts)}:v=0:a=1,'
               f'atrim={t0:.4f}:{t1:.4f},asetpts=PTS-STARTPTS[aout]')
    chapters = []
    titles = [sc.get('title') for sc in plan['scenes']]
    if any(titles) and not a.clip:                     # chapter markers from scene titles
        starts = {}
        for r in rows: starts.setdefault(r['scene'], r['start'])
        meta = [';FFMETADATA1', f"title={plan.get('title', '')}"]
        for si in range(len(titles)):
            s = starts[si]; e = starts.get(si + 1, total)
            meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={round(s * 1000)}', f'END={round(e * 1000)}',
                     f"title={si + 1:02d}. {titles[si] or 'Scene ' + str(si + 1)}"]
        mf = out.with_name(out.stem + '_chapters.txt'); mf.write_text('\n'.join(meta) + '\n', encoding='utf-8')
        cmd += ['-f', 'ffmetadata', '-i', str(mf)]     # inputs must come before output options
        chapters = ['-map_chapters', str(len(parts) + 1), '-map_metadata', str(len(parts) + 1)]
    srt(rows, out.with_suffix('.srt'), t0, t1)          # also muxed as a switchable subtitle track
    cmd += ['-i', str(out.with_suffix('.srt'))]
    subs = str(len(parts) + 1 + (1 if chapters else 0))
    cmd += ['-filter_complex', ';'.join(flt), '-map', '0:v', '-map', '[aout]', '-map', f'{subs}:s', *chapters]
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng',
            '-t', f'{t1 - t0:.3f}', '-movflags', '+faststart', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    show_caps = plan.get('captions', False) and not a.no_captions
    caps = {k: caption(r['text'], W, font) for k, r in enumerate(rows)} if show_caps else {}
    first = {}                                   # first row index of each scene
    for k, r in enumerate(rows):
        first.setdefault(r['scene'], k)
    i, held, mcache = 0, (None, None), {}
    for f in range(math.ceil((t1 - t0) * fps)):
        t = t0 + f / fps
        while i < len(rows) - 1 and t >= rows[i]['end']: i += 1
        r = rows[i]
        cam = camera_at(rows, i, t)
        key = (r['image'], tuple(cam))
        if held[0] != key:                         # camera holds most of the time: reuse the crop
            sharp = Image.LANCZOS if cam == r['cam'] else Image.BILINEAR   # settled view: best quality
            held = (key, crop(img(r['image']), cam, W, H, sharp))
        frame = held[1].copy()
        k0 = first[r['scene']]
        if k0 and rows[k0 - 1]['image'] != r['image'] and t - rows[k0]['start'] < FADE:
            prev = rows[k0 - 1]                    # new image: cross-fade from the last view
            old = crop(img(prev['image']), prev['cam'], W, H)
            frame = Image.blend(old, frame, smooth((t - rows[k0]['start']) / FADE))
        if r['marks']:
            frame = apply_marks(frame, rows, i, t, img(r['image']), cam, mark_color, mcache)
        if caps and t >= r['speech']:
            c = caps[i]; frame.paste(c, (0, H - c.height - H // 30), c)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait(): sys.exit('ffmpeg failed')
    (out.with_name(out.stem + '_timing.json')).write_text(json.dumps(rows, indent=1))
    mode = ('timestamps' if plan.get('timestamps') and has_audio and len(audio) == 1 and plan.get('audio')
            else 'per-scene audio' if has_audio else 'silent/estimated')
    print(f'wrote {out}  ({t1 - t0:.1f}s of {total:.1f}s, {len(plan["scenes"])} scenes, {len(rows)} lines, '
          f'{len(cache)} images, {mode})')


if __name__ == '__main__':
    main()
