#!/usr/bin/env python3
"""Smoke test for the motion-comic tools: about 30 s, no voice model, no art, no GPU.

  python examples/motion-comic-smoke/run.py

Draws two code-made "painted" panels and a tall panel with Pillow, makes a stand-in narration
(tone bursts with exact Audacity labels, one per line, like narrate.py writes), then runs
voice_fx.py (pitch colour + tight pauses), motion_comic.py --check, --contact-sheet and a full
render with shots, a word-anchored cut, effects, sounds, a lower third, a test card, music and
chapters. With no words.json, word anchors fall back to position-in-sentence estimates (the
renderer prints a note for each), which this test expects. Fails loudly on any problem.
"""
import json, math, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / "tools"
out = HERE / "out"; (out / "art").mkdir(parents=True, exist_ok=True)


def panel(path, size, sky, ground, label):
    im = Image.new("RGB", size, sky); d = ImageDraw.Draw(im); W, H = size
    d.rectangle((0, int(H * .62), W, H), fill=ground)
    for k in range(7):                                   # some detail so camera moves are visible
        x = int(W * (.08 + .13 * k)); h = int(H * (.18 + .05 * (k % 3)))
        d.rectangle((x, int(H * .62) - h, x + int(W * .07), int(H * .62)), fill=(60 + 20 * k, 50, 90))
    d.ellipse((int(W * .7), int(H * .08), int(W * .82), int(H * .08) + int(W * .12)), fill=(250, 220, 90))
    d.text((int(W * .05), int(H * .05)), label, fill=(255, 255, 255), font_size=int(H * .08))
    im.save(path)


panel(out / "art" / "wide.png", (1600, 900), (70, 120, 200), (60, 140, 80), "PANEL A")
panel(out / "art" / "tall.png", (900, 1400), (190, 90, 80), (90, 70, 60), "PANEL B")

lines = [("narrator", "A town sat quietly under a yellow sun."),
         ("hero", "Then a tower burst out of the ground!"),
         ("gnome", "Union business!"),
         ("narrator", "Broadcast terminated.")]
SR = 24000; t = 0.3; pcm = []; labels = []
for k, (_, text) in enumerate(lines):                    # stand-in speech: a buzzy tone per line
    d = 0.32 * len(text.split()); x = np.arange(int(d * SR)) / SR
    tone = 0.25 * np.sin(2 * np.pi * (140 + 40 * k) * x) * np.sin(np.pi * x / d) ** 0.3
    pcm += [np.zeros(int(.25 * SR)), tone, np.zeros(int(.6 * SR))]   # padding, like a TTS adds
    labels.append((t + .25, t + .25 + d, text)); t += .25 + d + .6
audio = np.concatenate([np.zeros(int(.3 * SR))] + pcm).astype(np.float32)
with wave.open(str(out / "narration.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((audio * 32767).astype(np.int16).tobytes())
(out / "labels.txt").write_text("".join(f"{s:.6f}\t{e:.6f}\t{x}\n" for s, e, x in labels))

has_rubberband = "rubberband" in subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
plan = {"title": "Motion comic smoke test", "width": 640, "fps": 24,
        "audio": "narration_fx.wav", "timestamps": "labels_fx.txt",
        "cast": {"narrator": "af_heart", "hero": "am_puck", "gnome": "am_fenrir"},
        "voice_fx": {"gnome": {"pitch": 5} if has_rubberband else {}, "hero": {"echo": True}},
        "images": {"A": "art/wide.png", "B": "art/tall.png"},
        "music": {"bpm": 112, "volume": 0.84}, "bug": "SMOKE TV",
        "scenes": [
            {"title": "The town", "sting": True, "lines": [
                {"text": lines[0][1], "speaker": "narrator", "lower_third": ["THE TOWN", "Population: quiet"],
                 "shot": {"image": "A", "box": [0, 0, 1, 1], "from": [.5, .5, 1.0], "to": [.3, .4, 1.3], "tr": "static"}},
                {"text": lines[1][1], "speaker": "hero",
                 "shot": {"image": "B", "box": [0, 0, 1, 1], "from": [.5, 1.0, 1.0], "to": [.5, 0.0, 1.0], "tr": "cut"},
                 "shots": [{"at": "burst", "image": "A", "box": [.4, .2, 1, .8], "from": [.5, .5, 1.0], "to": [.5, .5, 1.2], "tr": "flash"}],
                 "fx": [{"type": "shake", "at": "burst", "dur": 1.0, "amp": 14}, {"type": "debris", "at": "burst", "dur": 2.0}],
                 "sfx": [{"type": "crash", "at": "burst"}, {"type": "rumble", "at": "burst+0.2"}]}]},
            {"title": "The union", "lines": [
                {"text": lines[2][1], "speaker": "gnome",
                 "shot": {"image": "A", "box": [0, .3, .5, .9], "from": [.5, .5, 1.1], "to": [.5, .5, 1.0], "tr": "x"},
                 "fx": [{"type": "drop", "at": "business", "size": 60}], "sfx": [{"type": "tink", "at": "business"}]},
                {"text": lines[3][1], "speaker": "narrator",
                 "shot": {"card": {"title": "BROADCAST TERMINATED", "subtitle": "PLEASE STAND BY", "footer": "SMOKE TV"}, "tr": "static"}}]}]}
(out / "plan.json").write_text(json.dumps(plan, indent=1))


def run(script, *args):
    r = subprocess.run([sys.executable, str(TOOLS / script), str(out / "plan.json"), *args], capture_output=True, text=True, cwd=out)
    print(r.stdout.strip())
    if r.returncode: sys.exit(f"FAILED: {script} {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


fx_out = run("voice_fx.py", "--gap", "0.3", "--scene-gap", "0.6")
if "4 lines" not in fx_out: sys.exit("FAILED: voice_fx.py did not lay out 4 lines")
new = [l.split("\t") for l in (out / "labels_fx.txt").read_text().splitlines()]
gap = float(new[1][0]) - float(new[0][1])
if not 0.25 < gap < 0.55: sys.exit(f"FAILED: expected a tight pause after trimming, got {gap:.2f}s")
run("motion_comic.py", "--check")
run("motion_comic.py", "--contact-sheet")
rend = run("motion_comic.py")
if 'estimated time for "burst"' not in rend: sys.exit("FAILED: expected the word-position fallback note")
for f in ("final.mp4", "final.srt", "final_contact.png"):
    if not (out / f).exists(): sys.exit(f"FAILED: {f} was not made")
probe = lambda s: float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", s, "-show_entries", "stream=duration",
                                        "-of", "csv=p=0", str(out / "final.mp4")], capture_output=True, text=True).stdout.split()[0])
v, a = probe("v:0"), probe("a:0")
if abs(v - a) > 0.1: sys.exit(f"FAILED: video {v:.2f}s vs audio {a:.2f}s")
if not has_rubberband:
    print("note: ffmpeg has no rubberband filter here, so the pitch step was skipped")
print(f"MOTION COMIC SMOKE TEST PASSED ({v:.1f}s). Open {out / 'final_contact.png'} and {out / 'final.mp4'}.")
