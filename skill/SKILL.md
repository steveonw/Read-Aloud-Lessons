---
name: narrated-explainer-video
description: Make a narrated slideshow video (explainer, lesson, training, story) from a topic or notes: TTS-ready script, code-drawn boards or 4-panel comic pages, markers that point at what is being said, local Kokoro narration with exact timestamps, synced MP4. Tools: github.com/steveonw/Read-Aloud-Lessons.
---

# Narrated explainer video

A video built like a teacher at a board: a **few high-resolution still boards**, a **TTS-ready
script**, and **markers** (a box, underline or ring) that appear on whatever each sentence talks
about. The view holds still; it only moves to the next board or panel between topics. TTS audio
and its sentence timestamps set all timing: narrate it yourself with a local voice (`narrate.py`),
or use the user's own TTS export.

Pipeline: **source -> scenes -> boards -> checks -> plan.json (text + marks) -> narration + timestamps -> contact sheet -> MP4.**

**Done means all of these exist and pass:** boards (opened and looked at), `plan.json` passing
`$T/render_video.py --check`, `validation.md` from `validate.py`, the contact sheet (opened, every mark
on its item), narration with `check_audio.py` reporting no PROBLEM, then `final.mp4`.

## 0. Get the tools (once per session)

The tested tools live in the **Read-Aloud-Lessons** repo. Clone it; never retype or rewrite them.

```bash
git clone --depth 1 https://github.com/steveonw/Read-Aloud-Lessons.git read-aloud-lessons  # or: git -C read-aloud-lessons pull
pip install -r read-aloud-lessons/requirements.txt          # Pillow, matplotlib, numpy (+ ffmpeg from the system)
python read-aloud-lessons/examples/smoke-test/run.py        # ~10 s: proves the toolchain works here
T=read-aloud-lessons/tools                                  # render_video.py, narrate.py, check_audio.py, board.py
```

For narration and the audio check also `pip install -r read-aloud-lessons/requirements-voice.txt`.
If GitHub cannot be reached, ask the user to attach the repo as a zip (GitHub: Code -> Download ZIP).
Worked examples to copy from: `examples/sky-blue` (single boards, 5 min) and `examples/leap-years`
(2x2 panel pages, three voices, quiz). Each has `build.py` (boards + plan), a numbers module and
`validate.py`.

## 1. Pick a layout and plan the scenes

| Layout | Board | Scene | Good for |
|---|---|---|---|
| **Single board** | one 16:9 board per idea, 3840x2160 | the whole board, 4-8 sentences | short pieces, 1-5 minutes |
| **Panel pages** (manga/comic) | one 16:9 page with a 2x2 grid of 16:9 panels, 5120x2880 | one panel, 4-8 sentences | longer reviews, stories; 4 scenes per image |

- Panel pages are usually best past ~5 minutes: few images, consistent style. The view glides to
  the next panel at each scene change; a new page cross-fades in.
- Use a **fixed layout inside every board/panel** (e.g. title top-left, graph left, equations right,
  bullet notes under them, takeaway line at the bottom), so marks are easy to place.
- Read the source material. Ask about length, audience and look only if they are unclear.
  Give each scene a title (it becomes a chapter marker) and a one-line purpose.
- **Size it from the word count.** Narration runs about 150 spoken words per minute with pauses
  (Kokoro Heart): 5 minutes is about 700-750 words, 50-60 sentences, 7-8 boards of 6-9 sentences.
- A strong shape for teaching: hook question, building blocks one per board, the payoff with real
  numbers, recap, a test-yourself question, then the answer (plus an optional bonus fact).
- Time budget for a 5-minute video: writing and boards take most of the work; narration about
  2 minutes and the 1080p render under 2 minutes on a 2-core machine.

## 2. Write the narration in `plan.json`

`plan.json` is the single source of truth for narration. TTS text files are exported from it,
so the script and the plan cannot drift apart.

- One sentence per line. Each sentence should point at one thing on the board.
- Write it exactly as spoken: "x cubed minus three halves x squared", "one comma negative one half",
  "f double prime of x". No symbols, markdown, bullets, abbreviations or digits that could be misread.
- Short sentences (about 6-25 words); budget about 150 spoken words per minute (step 1).
- Fix errors in the source rather than repeating them, and tell the user what you corrected.
- **Use one spelling variant everywhere** (e.g. "color" on the boards if the narration says color),
  matching the viewer's locale.
- **Quiz: question on one board, answer on the next**, so the answer isn't visible while the viewer
  thinks. Give the question line `"pause_after": 5`. On panel pages put the answer on a new page,
  not the neighbouring panel: the glide between panels can show it early.
- **One narrator by default.** Use several voices only when the piece has dialogue or characters
  (a student asking, a teacher answering, a story): add a `"cast"` and put `"speaker"` on those
  lines or scenes (step 6). Keep speaker names out of the spoken text.

## 3. Draw the boards with code

- **Everything the narration names must be on the board.** If a sentence states a formula, a rule
  or a domain, draw it; otherwise the viewer hears something they can't see and there is nothing to mark.
- **All text, equations, numbers, labels and charts are drawn with code** (matplotlib with mathtext,
  Pillow, or HTML/SVG screenshotted with Playwright). Image generators garble text and math, so use
  them only for decorative art with no lettering, and add any words on top with code.
- Compute every plotted value from the real data or formula (e.g. sympy -> lambdify), never by eye.
  Put the formulas and numbers in **one module** (e.g. `physics.py`, `data.py`) that the boards, the
  script numbers and `validate.py` all import, so they can never disagree.
- **Label simplified models on the board** ("Model: clean air, Rayleigh scattering only") when a
  number comes from an idealised calculation.
- **Keep diagrams simple**: one idea per drawing, few arrows, lots of empty space. A busy diagram
  hides what the marker points at.
- Consistent style: dark "chalkboard" background, one accent color per concept, generous margins,
  space between rows so a box fits around each line without touching its neighbours.
- The whole panel is on screen and viewers can go fullscreen, so normal readable sizes are fine;
  avoid tiny tick numbers.
- Captions are usually off (`"captions": false`) since the board carries the content; the `.srt` is given separately.
- Name files `board01.png`, `board02.png`, ... Save the drawing script so boards can be rebuilt.
- Open every board image and look at it: nothing overlapping, clipped, or too small.

**Draw with the board helper `tools/board.py`; it records where everything is.** Name each element a
sentence may point at while you draw it; after layout its exact box (or a graph point's position) is
read back from matplotlib, so marks come from the drawing itself, with no guessing or pixel searching.
It handles single boards and 2x2 panel pages the same way: coordinates are always relative to one
panel (0..1, y up), and `save()` returns marks ready to paste into each scene.

```python
import sys; sys.path.insert(0, "read-aloud-lessons/tools")
from board import Board, INK, ACCENT        # dark chalkboard style: BG #0B1015, INK, ACCENT gold

b = Board("board01.png")                     # single board, 3840x2160
b.title("Turning points")
b.text(.56, .70, r"$f(x)=x^3-\frac{3}{2}x^2$", 30, ACCENT, name="E1")
ax = b.axes([.06, .22, .42, .52])            # [left, bottom, width, height] inside the panel
# ... plot computed data on ax ...
b.ring("G:max", ax, 0, 0)                    # a point in the axes' data coordinates
b.box("graph", ax)                           # any drawn thing: axes, image, patch, legend
marks = b.save()                             # {"E1": {"box": [...]}, "G:max": {"ring": [...], "r": .035}}

page = Board("page01.png", grid=(2, 2))      # panel page, 5120x2880; scene "panel" for (col, row)
page.title("Second derivative", panel=(1, 0))            # is [col * 0.5, row * 0.5, 0.5, 0.5]
page.text(.56, .70, r"$f''(x)=6x-3$", 30, ACCENT, name="E2", panel=(1, 0))
marks = page.save()                          # {(1, 0): {"E2": {...}}, ...}
```

- A phrase drawn as two text lines is one item: merge the two boxes into one mark.
- `axes(rect)` takes [left, bottom, width, height] inside the panel; use it instead of
  `fig.add_axes` so graphs land in the right panel.

## 4. Check the content

- Write a small `validate.py` that re-checks every fact shown on the boards and said in the script
  (for math: sympy derivatives, roots, coordinates, signs, domains; for data: totals against the source).
  It should fail loudly. Make sure the board and the narration say the same values.
- Check the **spoken** form too: compute the number, then assert the narration contains the matching
  words (25.0% -> "a quarter", 37.9 -> "thirty eight").
- Structure is checked by the tool: `python $T/render_video.py plan.json --check` fails on missing
  images, unknown marks or speakers, marks outside 0..1, digits or symbols in spoken text, and quiz
  questions without `"pause_after"` of 4 or more. Run it before narrating; fix every PROBLEM.
- Save a short `validation.md` listing what was checked and any source errors corrected.

## 5. `plan.json` and marks

```json
{
  "title": "Derivative tests",
  "width": 1920, "fps": 24, "captions": false,
  "audio": "narration.wav", "timestamps": "labels.txt",
  "scenes": [
    {"title": "Turning points", "image": "board01.png",
     "marks": {"E1": {"box": [0.54, 0.25, 0.79, 0.33]},
               "E2": {"box": [0.54, 0.37, 0.76, 0.45]},
               "F":  {"box": [0.04, 0.90, 0.42, 0.96]},
               "G:max": {"ring": [0.18, 0.40], "r": 0.032},
               "G:min": {"ring": [0.38, 0.62], "r": 0.032}},
     "lines": [
       {"text": "Consider f of x equals x cubed minus three halves x squared.", "mark": "E1"},
       {"text": "Its first derivative factors as three x times the quantity x minus one.", "mark": "E2"},
       {"text": "The critical numbers are zero and one.", "mark": "E2"},
       {"text": "So zero comma zero is a local maximum, and one comma negative one half is a local minimum.", "mark": ["G:max", "G:min"]},
       {"text": "Neither point is an absolute extremum.", "mark": "F"},
       {"text": "Keep that in mind for the next example."}
     ]},
    {"title": "Concavity", "image": "page01.png", "panel": [0.5, 0, 0.5, 0.5],
     "marks": {"E2": {"box": [0.55, 0.25, 0.74, 0.34]}},
     "lines": [
       {"text": "The second derivative is six x minus three.", "mark": "E2"}
     ]}
  ]
}
```

- `panel` = [left, top, width, height] of the scene's region on the image (0-1). Omit it for single boards.
  2x2 panels: [0,0,.5,.5], [.5,0,.5,.5], [0,.5,.5,.5], [.5,.5,.5,.5] in reading order.
  Keep panels 16:9 shaped; a board image that is not 16:9 is letterboxed and its panels and marks
  are moved to match automatically.
- All mark coordinates are **panel-relative** (0-1 from the panel's top-left). Shapes:
  `{"box": [x0, y0, x1, y1]}`, `{"underline": [x0, y, x1]}`, `{"ring": [x, y], "r": 0.032}` (r = fraction of panel height).
- A line's `"mark"` is a name, a list of names (several things at once), or an inline shape. No mark = nothing highlighted.
- Scene `"title"` becomes a chapter marker in the MP4. Defaults: width 1920, fps 24, captions off.

### Marking rules

- **Mark what the sentence names**, chosen by meaning: a sentence stating a formula marks that
  formula; one about a point on the curve rings that point; one restating a bullet boxes that note;
  the moral boxes the takeaway line. Several items named = several marks.
- **General sentences get no mark** (introductions, transitions, anything not on the board). Never
  add a mark just to have one.
- Repeating the same mark on consecutive sentences keeps it solid (no flicker).
- Marks appear when that sentence's own speech starts (not during a spoken scene title) and fade
  when the next sentence starts, so a mark stays up through a pause (a quiz question stays marked
  while viewers think). At a scene change the old board leaves in the pause, before the next speech.
- **Take mark positions from the drawing** (the `Board` helper in step 3). Only for boards you did
  not draw yourself (someone else's images), fit boxes to the ink: search a region of the board image
  for non-background pixels and pad the bounding box by ~0.01:

```python
import numpy as np
def ink_box(panel_img, x0, y0, x1, y1, pad=0.01):
    """Panel-relative search region -> tight panel-relative box around the ink drawn there."""
    W, H = panel_img.size
    rgb = panel_img.convert('RGB'); bg = np.array(rgb.getpixel((2, 2)))   # board background colour
    a = np.asarray(rgb.crop((int(x0*W), int(y0*H), int(x1*W), int(y1*H)))).astype(int)
    ys, xs = np.nonzero(np.abs(a - bg).max(axis=2) > 45)
    if not len(xs): raise ValueError(f'no ink in region {x0, y0, x1, y1}; widen it')
    return [x0 + xs.min()/W - pad, y0 + ys.min()/H - pad, x0 + (xs.max()+1)/W + pad, y0 + (ys.max()+1)/H + pad]
```

- **Place rings from the math**: `Board.ring` with the point's data coordinates does this for you.
  By hand: with the axes rectangle (left, top, width, height in panel coordinates) and axis limits,
  `x_panel = left + width*(x - xmin)/(xmax - xmin)`, `y_panel = top + height*(ymax - y)/(ymax - ymin)`.
- Camera: leave `camera` out entirely. Each scene shows its whole panel, still. Only add a
  `camera` close-up ([center_x, center_y, zoom] inside the panel, or a preset name) if the user asks
  for zooming; then move only when the subject changes and never back-and-forth.

## 6. Timing: how the audio drives the video

Best to worst:

1. **One audio file + timestamps** (`"audio"` + `"timestamps"` at plan level). Every sentence starts
   exactly on its own timestamp. Accepts Audacity labels (start, end, text separated by tabs), SRT,
   VTT, or JSON `[{"start", "end", "text"}]`. Entries are matched to plan lines by text in order,
   so the timestamp file may contain extra entries (e.g. spoken scene titles); they are folded into
   the start of the next line, and listed in the console. A plan line with no match stops the render
   and names the line, so fix the plan text or the timestamps.
2. **One audio file per scene** (`"audio"` per scene or `--audio-dir` with `scene01.wav`, ...).
   Scene changes are exact; lines inside a scene are split by word count unless `"seconds"` is given.
3. **No audio**: `--preview` estimates at 150 words per minute.

Prefer **WAV**. MP3 encoders add ~25-50 ms of silence at the start; if only MP3 exists, set
`"audio_offset"` to that delay (measure it against a WAV if one exists, or use 0.046 for LAME).

### Narrate it yourself (draft or final)

`$T/narrate.py` voices `plan.json` locally, the way the Read Aloud app does: one sentence at a
time, joined with pauses, plus an Audacity label file with exact times. Then set
`"audio": "narration.wav", "timestamps": "labels.txt"` and render. Use it for every preview so
timing and pauses are real, and as the final narration when the user wants it.

```bash
python $T/narrate.py plan.json --model-dir <voice folder> --voice af_heart   # -> narration.wav + labels.txt
python $T/narrate.py --list-voices --model-dir <voice folder>
```

Voices, best first:
1. **The user's own Read Aloud voice folder** if they provide it: `voices/kokoro-gpu-v1-0`
   (Kokoro v1.0, 54 voices; speaker numbers match the app, 0 = Heart). Measured at about
   1.5-2.5x real time on a 2-core CPU. `pip install onnxruntime espeakng-loader phonemizer-fork numpy`
2. **The same Kokoro v1.0 downloaded** (326 MB) from Hugging Face `onnx-community/Kokoro-82M-v1.0-ONNX`:
   `onnx/model.onnx`, `tokenizer.json`, `voices/<name>.bin` into one folder (layout as above).
3. **Kitten TTS micro 0.8** for a fast, small (63 MB) draft: sherpa package `tecmage/kitten-micro-en-v0_8`
   on Hugging Face; needs `pip install sherpa-onnx==1.13.4` (2.x asks for a lexicon file). About 2x real time.
4. **Piper Amy** (Read Aloud's default voice): `vits-piper-en_US-amy-medium.tar.bz2` from the
   sherpa-onnx GitHub `tts-models` release.

- **Several voices**: put a cast in `plan.json` and `"speaker"` on a line (that line only) or a scene
  (its default); untagged lines use `"narrator"`. A cast entry is one voice or one per engine, so the
  plan works with Kokoro or Kitten:
  `"cast": {"narrator": "af_heart", "student": {"kokoro": "am_adam", "kitten": 3}, "teacher": {"kokoro": "bf_emma", "kitten": 2}}`.
  Unknown speakers or voices stop before any audio is made. Pick voices that differ clearly
  (e.g. a male and a female voice, or US and UK); British Kokoro voices (`bf_`, `bm_`) get British
  pronunciation. Speakers are level-matched automatically (one gain per speaker). `check_audio.py`
  prints each speaker's pitch and loudness so you can confirm the change is audible.
- With no `--voice` and no cast, Kokoro uses Heart (`af_heart`). Speaker numbers (0 = Heart) only
  work with the Read Aloud voice folder, which has the numbering in `voice.json`.
- **Sentence cache**: every voiced sentence is kept in `tts_cache/`, keyed by code version, engine,
  model, voice, speed and text. After editing the script, rerun `narrate.py` and only the changed lines are voiced again;
  the labels are rebuilt for the whole narration, so timing stays exact.
- Never hand over a video whose narration is missing sentences or failed a check; fix and re-narrate.
  `narrate.py` warns when Kokoro drops sounds it cannot say or cuts off an over-long sentence: respell
  or split that line.
- Scene changes get a longer pause (sentence gap + 0.4 s, like Read Aloud's paragraph pause).
- **Give viewers time to think:** any "pause and answer" moment (quiz question, "try it yourself")
  needs `"pause_after": 4` or more on that line. A normal sentence gap (~1 s) is too short to recall anything.
- Listen-free check: run `check_audio.py` (step 9) on every narration.

## 7. Render

`$T/render_video.py` needs ffmpeg/ffprobe and Pillow. Paths inside `plan.json` are relative to it.

```bash
python $T/render_video.py plan.json --check               # lint the plan (run before narrating)
python $T/render_video.py plan.json --export-tts tts      # tts/scene01.txt ... + narration_all.txt
python $T/render_video.py plan.json --contact-sheet       # final_contact.png: every line's view with its marks
python $T/render_video.py plan.json --preview             # preview.mp4, silent, estimated timing
python $T/render_video.py plan.json --clip 300 330        # quick 30 s check with real audio
python $T/render_video.py plan.json                       # final.mp4 (+ .srt, _timing.json, chapters)
python $T/render_video.py plan.json --audio-dir audio     # final, from per-scene files
```

- **Always open the contact sheet** and check every mark sits on the item its sentence names.
  Render a `--clip` across a scene change before the full render.
- Speed: roughly 3-5 minutes for a 16-minute video at 1920x1080, 24 fps. Run long renders in the background.
- A final render refuses to run without narration for every scene; `--preview` is the silent draft
  (it includes each `pause_after`).
- The MP4 carries chapters and a subtitle track viewers can switch on; captions burned into the
  picture are off unless `"captions": true`. Options: `--out name.mp4`, `--no-captions`.

## 8. Hand off for TTS

If you narrated it yourself, the video is already complete; offer the hand-off below only if the
user wants their own voice or app for the final.

Deliver the boards, `tts/` folder, preview, contact sheet, `plan.json`, the drawing and validation
scripts (and a link to the Read-Aloud-Lessons repo for the tools), and a short `README` / audio checklist telling the user:
- Best: read `tts/narration_all.txt` as **one WAV plus a timestamp file** (labels/SRT/VTT/JSON), if the TTS can export one.
  For the Read Aloud app: paste `narration_all.txt`, set the sentence pause, Render, turn on the label
  track and export WAV; it writes `read-aloud-narration.wav` and `read-aloud-narration-labels.txt`
  with exact sentence times.
- Otherwise: one file per scene, `tts/scene01.txt` -> `scene01.wav`, and so on. Same voice and speed throughout.
- Scene titles may be spoken or not; both work.
Also give a human-readable `script_with_scene_headings.md` (titles + narration) for review.
If audio is already supplied, skip straight to the final render.

## 9. Check the final

- Confirm the video and audio durations match (`ffprobe`) and read `final_timing.json`.
- Run `python $T/check_audio.py plan.json --asr-dir <speech recognizer folder>`. It finds every plan
  line in the timestamps (any format), transcribes that stretch of audio and compares it with the
  **plan** text, so narration made from an older script fails. It also reports silence, overlaps,
  clipping, pauses, quiz think time (4 s or more) and, with several speakers, each one's pitch and
  loudness. PROBLEM lines are failures (exit code 1): fix every one before the final render.
  "check" lines are for review only.
- The recognizer is a proxy, not a listener. It cannot judge how natural the voice sounds, and it
  mishears some clear speech (single-letter math names like "x" heard as "ex", "sky blue" as
  "skyblue"). Respell a word only when a real word is consistently misheard; never bend the script
  to please the recognizer. When the user can listen, their ear wins.
- Pull frames a second or two into a few sentences (`ffmpeg -ss T -i final.mp4 -frames:v 1 f.png`)
  and check the marked item is the one being said.
- If a mark is wrong, fix it in `plan.json` and re-render; with timestamps no new audio is needed.
