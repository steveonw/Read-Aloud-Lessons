#!/usr/bin/env python3
"""Per-character voice colour and tight comedy pauses for a narrate.py narration.

  python voice_fx.py plan.json                       # narration.wav + labels.txt -> narration_fx.wav + labels_fx.txt
  python voice_fx.py plan.json --gap 0.3 --scene-gap 0.6

plan.json:  "voice_fx": {"gnome": {"pitch": 5}, "dragon": {"pitch": -5, "echo": true}}
            "audio": "narration_fx.wav", "timestamps": "labels_fx.txt"

Each sentence is cut out of the narration using its label, trimmed of the silence the TTS
pads around it (Kokoro adds about 0.8 s per sentence), coloured if its speaker has an entry
(pitch in semitones with ffmpeg rubberband, duration kept; optional short echo), and laid out
again with exact pauses: --gap between lines, --scene-gap at scene changes, a line's own
"pause_after" wins. The new labels are exact by construction (sample counts). Run word_times.py
afterwards (it reads the plan's audio + timestamps). Needs ffmpeg with rubberband for pitch.
"""
import argparse, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np


def read_labels(p):
    out = []
    for l in Path(p).read_text(encoding='utf-8-sig').splitlines():
        q = l.split('\t')
        if len(q) >= 2 and not l.startswith('\\'):
            out.append((float(q[0]), float(q[1]), q[2] if len(q) > 2 else ''))
    return out


def rd(p):
    with wave.open(str(p)) as w:
        sr = w.getframerate(); n = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return (x.reshape(-1, n).mean(1) if n > 1 else x), sr


def wr(p, x, sr):
    with wave.open(str(p), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def trim(x, sr, thr=0.002):
    idx = np.nonzero(np.abs(x) > thr)[0]
    if not len(idx): return x
    return x[max(0, idx[0] - int(.09 * sr)):min(len(x), idx[-1] + int(.08 * sr))]


def colour(x, sr, f):
    """-> (audio, tail samples after the speech, e.g. echo)."""
    flt = []
    if f.get('pitch'): flt.append(f"rubberband=pitch={2 ** (f['pitch'] / 12):.5f}:pitchq=quality")
    if f.get('echo'): flt.append('aecho=0.8:0.6:45|90:0.25|0.15')
    if not flt: return x, 0
    tail = int(.6 * sr) if f.get('echo') else 0
    with tempfile.TemporaryDirectory() as td:
        wr(Path(td) / 'i.wav', np.concatenate([x, np.zeros(tail, np.float32)]), sr)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(Path(td) / 'i.wav'), '-af', ','.join(flt),
                        '-ar', str(sr), '-ac', '1', str(Path(td) / 'o.wav')], check=True)
        y, _ = rd(Path(td) / 'o.wav')
    y = y[:len(x) + tail]
    y *= np.sqrt(np.mean(x ** 2)) / max(1e-9, np.sqrt(np.mean(y[:len(x)] ** 2)))   # keep the level
    return y, tail


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('plan', type=Path)
    ap.add_argument('--in', dest='src', default='narration.wav'); ap.add_argument('--labels-in', default='labels.txt')
    ap.add_argument('--out', default='narration_fx.wav'); ap.add_argument('--labels-out', default='labels_fx.txt')
    ap.add_argument('--gap', type=float, default=0.32); ap.add_argument('--scene-gap', type=float, default=0.6)
    ap.add_argument('--lead', type=float, default=0.25, help='silence before the first line')
    a = ap.parse_args()
    base = a.plan.resolve().parent; plan = json.loads(a.plan.read_text(encoding='utf-8'))
    fx = plan.get('voice_fx', {})
    x, sr = rd(base / a.src); labels = read_labels(base / a.labels_in)
    lines = [(ln, sc, li == len(sc['lines']) - 1) for sc in plan['scenes'] for li, ln in enumerate(sc['lines'])]
    if len(lines) != len(labels):
        raise SystemExit(f'{len(labels)} labels but {len(lines)} plan lines; re-narrate first')
    parts, out_labels, t, done = [], [], a.lead, 0
    for (s0, s1, text), (ln, sc, last) in zip(labels, lines):
        seg = trim(x[int(s0 * sr):int(s1 * sr)], sr)
        f = fx.get(ln.get('speaker', sc.get('speaker', 'narrator')), {})
        seg, tail = colour(seg, sr, f); done += bool(f)
        speech = len(seg) - tail
        parts.append((t, seg)); out_labels.append((t, t + speech / sr, text))
        t += speech / sr + float(ln.get('pause_after', a.scene_gap if last else a.gap))
    pcm = np.zeros(int((t + .5) * sr), np.float32)
    for t0, seg in parts:
        i = int(round(t0 * sr)); pcm[i:i + len(seg)] += seg[:len(pcm) - i]
    pcm *= min(1.0, 0.89 / max(1e-9, np.abs(pcm).max()))
    wr(base / a.out, pcm, sr)
    (base / a.labels_out).write_text(''.join(f'{s:.6f}\t{e:.6f}\t{x_}\n' for s, e, x_ in out_labels), encoding='utf-8')
    print(f'wrote {a.out} + {a.labels_out}: {len(out_labels)} lines, {len(pcm) / sr:.1f}s '
          f'(was {len(x) / sr:.1f}s), {done} coloured ({", ".join(sorted(fx)) or "none"})')


if __name__ == '__main__':
    main()
