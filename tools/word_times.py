#!/usr/bin/env python3
"""Word start/end times for every narrated line -> words.json (for word-anchored shots and effects).

  python word_times.py plan.json --asr-dir models/sherpa-onnx-zipformer-small-en-2023-06-26

Uses the plan's "audio" + "timestamps" (from narrate.py). Each line's stretch of audio is
transcribed by the same small recognizer check_audio.py uses; its token timestamps give the
time each recognised word starts. The renderer matches an anchor word ("burst") against these
words, and falls back to an estimate from the word's position in the sentence if the
recognizer misheard it. Output: {"lines": [{"text", "start", "end", "words": [[w, t0, t1], ...]}]}
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np

SR, PAD = 16000, 0.25


def read_labels(p):
    out = []
    for l in Path(p).read_text(encoding='utf-8-sig').splitlines():
        q = l.split('\t')
        if len(q) >= 2 and not l.startswith('\\'):
            out.append((float(q[0]), float(q[1]), q[2] if len(q) > 2 else ''))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan', type=Path); ap.add_argument('--asr-dir', required=True)
    ap.add_argument('--out', default='words.json'); ap.add_argument('--threads', type=int, default=2)
    a = ap.parse_args()
    import sherpa_onnx
    base = a.plan.resolve().parent; plan = json.loads(a.plan.read_text(encoding='utf-8'))
    d = Path(a.asr_dir)
    pick = lambda pat, alt: str((sorted(d.glob(pat)) or sorted(d.glob(alt)))[0])
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=pick('encoder*.int8.onnx', 'encoder*.onnx'), decoder=pick('decoder*.onnx', 'decoder*.onnx'),
        joiner=pick('joiner*.int8.onnx', 'joiner*.onnx'), tokens=str(d / 'tokens.txt'), num_threads=a.threads)
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(base / plan['audio']), '-ac', '1', '-ar', str(SR),
                          '-f', 's16le', '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    out = []
    for s0, s1, text in read_labels(base / plan['timestamps']):
        seg = x[int(s0 * SR):int(s1 * SR)]
        pad = np.zeros(int(PAD * SR), np.float32)
        st = rec.create_stream(); st.accept_waveform(SR, np.concatenate([pad, seg, pad])); rec.decode_stream(st)
        r = st.result; words = []
        for tok, t in zip(r.tokens, r.timestamps):
            t = round(max(s0, min(s1, s0 + t - PAD)), 3)
            if tok.startswith(' ') or not words: words.append([tok.strip().lower(), t, t])
            else: words[-1][0] += tok.lower()
        for k, w in enumerate(words):
            w[2] = words[k + 1][1] if k + 1 < len(words) else round(s1, 3)
        out.append(dict(text=text, start=s0, end=s1, words=words))
    (base / a.out).write_text(json.dumps({'lines': out}, indent=1), encoding='utf-8')
    print(f'wrote {a.out}: {len(out)} lines, {sum(len(l["words"]) for l in out)} words')


if __name__ == '__main__':
    main()
