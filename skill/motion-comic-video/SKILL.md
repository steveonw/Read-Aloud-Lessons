---
name: motion-comic-video
description: Turn a story or script with characters into a motion comic video from painted or AI panels: moving shots, word-timed cuts and effects, character voices, music. For stories, not lessons. Tools: github.com/steveonw/Read-Aloud-Lessons.
---

# Motion comic video

Use this skill when the piece is a **story with characters** (a sketch, a parody ad, a short
drama) and the art is painted or image-generated panels: comic pages, storyboard sheets, hero
images. For lessons and explainers use **narrated-explainer-video** (`skill/SKILL.md`) instead:
still boards with marks that point at what is said. Here every shot moves, cuts land on lines
and words, effects and sounds punctuate the gags, and a music bed runs under the dialogue.

## 0. Get the tools (once per session)

The tested tools live in the **Read-Aloud-Lessons** repo. Clone it; never retype or rewrite them.

```bash
git clone --depth 1 https://github.com/steveonw/Read-Aloud-Lessons.git read-aloud-lessons  # or: git -C read-aloud-lessons pull
pip install -r read-aloud-lessons/requirements.txt -r read-aloud-lessons/requirements-voice.txt
python read-aloud-lessons/examples/motion-comic-smoke/run.py   # a few seconds: proves the toolchain works here
T=read-aloud-lessons/tools      # motion_comic.py, voice_fx.py, word_times.py, upscale.py, narrate.py, check_audio.py
```

Needs ffmpeg with the rubberband filter for character pitch (most builds have it; the smoke test
says if it is missing). `upscale.py` alone needs `pip install torch` (CPU build) and the 5 MB
weights `realesr-general-x4v3.pth` from the GitHub xinntao/Real-ESRGAN release v0.2.5.0.
Models: Kokoro v1.0 from Hugging Face `onnx-community/Kokoro-82M-v1.0-ONNX` (`onnx/model.onnx`,
`tokenizer.json`, `voices/<name>.bin`) and the sherpa-onnx GitHub release "asr-models" file
`sherpa-onnx-zipformer-small-en-2023-06-26.tar.bz2`. If GitHub cannot be reached, ask the user to
attach the repo as a zip. `examples/motion-comic-smoke/run.py` is also the smallest complete plan
to copy from; `examples/zorblooks/plan.json` is a full 3-minute, 7-voice, 61-shot example.

Pipeline: **art -> (upscale) -> plan.json with shots -> check -> narrate.py -> voice_fx.py ->
word_times.py -> check_audio.py -> contact sheet -> MP4.**

**Done means:** `motion_comic.py plan.json --check` passes; `check_audio.py` reports no PROBLEM
except a one-word line you have tested alone (below); the contact sheet is opened and every
framing is clean; a frame from the middle of every line and one just after every word-anchored
gag have been looked at; `final.mp4` reports about -14 LUFS and its audio and video durations match.

**The one rule: anchor everything to lines and words, never to seconds.** A shot belongs to a
line; a cut, effect or sound inside a line names a word of it (`"at": "burst"`). Then a new
voice, a retake or a rewritten line re-times every cut, effect and music cue by itself. A
timeline pinned to seconds breaks the moment the narration changes.

### Art
- Image generators are fine here (the painted look is the point), but ask for **one scene per
  image, 16:9, 1280x720 or larger, with no speech bubbles or lettering**. Painted-in dialogue
  repeats the subtitles and is often misspelt. Big ad-style headlines can stay as on-screen graphics.
- A sheet of many small panels also works: upscale it 4x with `upscale.py`, then crop each panel
  with a `box`. Panels under about 250 px tall in the original stay soft even after upscaling;
  use them for short reaction shots.
- **Find boxes from a grid, not by eye.** Draw a labelled grid every 50 px over the *original*
  sheet, read the panel edges off it, convert to fractions (x / width, y / height), and inset 3-4 px
  so gutters, panel numbers and section labels never show. Check every framing with `--contact-sheet`.
- **Character consistency:** if a character's outfit differs between sheets, take that
  character's wide shots from one sheet and use the off-model panels only for tight face close-ups.

### Script and voices
- One plan line per spoken sentence or reply, each with a `"speaker"` in the `"cast"`.
  `"text"` is what the voice says: normal case, words not digits (Kokoro reads ALL-CAPS words
  such as "US" as letters). `"display"` is what the subtitles show, e.g. the shouted ALL-CAPS version.
- Cast clearly different voices. Best Kokoro voices: af_heart, af_bella, bf_emma; usable:
  am_puck (energetic host), am_michael, am_fenrir, bm_fable, bm_george. Avoid am_adam (weakest).
- Give small or monstrous characters a colour with `voice_fx` instead of hunting for a new voice:
  `{"gnome": {"pitch": 5}, "wizard": {"pitch": 3}, "dragon": {"pitch": -5, "echo": true}}`.
- **Comic pace:** narrate at `--speed 1.08`, then `voice_fx.py --gap 0.3 --scene-gap 0.6`.
  Kokoro pads every sentence with about 0.8 s of silence, so even a small `--gap` in narrate.py
  plays as a 1.1 s pause. voice_fx.py trims that padding and lays the lines out again with exact
  pauses, writing new labels. Measured: 58 lines, 399 words came to 3.5 minutes untrimmed and
  2:58 trimmed. Put a beat before a payoff with `"pause_after": 0.7` on the setup line.
- Kokoro cannot act: delivery comes only from punctuation and speed. Say so to the user; if they
  have an expressive TTS (instruction or emotion control), its WAV plus labels drop straight in
  as `"audio"` + `"timestamps"` and everything re-times.

### Shots, effects and sound
- **A new shot on almost every line**; a long narrated line can take a second shot at a word
  (`"shots": [{"at": "coven", ...}]`). Every shot moves: push in (zoom 1.0 to 1.2-1.4), tilt down
  a tall panel (cy 0 to 1), pan a wide one (cx 0 to 1). Avoid holding still for more than about 4 s.
- Transitions: `"cut"` for punchlines and one-word reactions ("Oh?", "Why?"), `"static"` for
  interruptions and broadcast breaks, `"flash"` for explosions, `"cont"` to continue a move on the
  same panel, cross-fade otherwise.
- **Show the gag the narration describes.** If a line says a tower bursts through the ceiling,
  cut to the tower and put flash + shake + debris + crash on "burst". If the line names a small
  action (a gnome drops a biscuit), a `drop` effect on "dropped" plus a `tink` on "biscuit" sells it.
- Rhythms use `repeat` and `every`: hammering = shake and thud, `repeat` 21, `every` 0.17.
  Keep effects rare enough to land, roughly one per scene; a `"sting"` on ad-break scenes.
- `"lower_third"` on each main character's first line; `"bug"` gives a TV-channel corner logo.
  A drawn `"card"` (test-card style) suits "broadcast terminated" or "please stand by" moments.
- `--clip` renders a short stretch with real audio for checking a gag before the full render
  (about 75 s for 3 minutes at 1280x720 on 2 cores).

### Commands
```bash
python $T/upscale.py realesr-general-x4v3.pth sheet.png art/sheet_x4.png      # optional, small panels
python $T/motion_comic.py plan.json --check
python $T/narrate.py plan.json --model-dir <kokoro folder> --speed 1.08        # cast from plan.json
python $T/voice_fx.py plan.json --gap 0.3 --scene-gap 0.6                      # -> narration_fx.wav, labels_fx.txt
python $T/word_times.py plan.json --asr-dir <sherpa zipformer folder>          # -> words.json
python $T/check_audio.py plan.json --asr-dir <sherpa zipformer folder>
python $T/motion_comic.py plan.json --contact-sheet                            # final_contact.png
python $T/motion_comic.py plan.json --clip 60 75
python $T/motion_comic.py plan.json                                            # final.mp4 + .srt, chapters
```
With `"audio": "narration_fx.wav", "timestamps": "labels_fx.txt", "words": "words.json"` in the plan.

### Checks
- `check_audio.py` reads the plan's audio and timestamps, so it checks the trimmed, coloured
  narration. A one-word line ("Oh?") can fail in context although it is clear alone: voice it by
  itself and transcribe it before respelling anything.
- The renderer prints a note for any anchor word the recognizer did not hear; that cue is then
  placed from the word's position in the sentence, which is close but not exact. Look at those frames.
- Pull frames with `ffmpeg -nostdin -ss T -i final.mp4 -frames:v 1 f.png` (in a shell loop,
  ffmpeg without `-nostdin` swallows the loop's input). Check the middle of every line (right
  panel, nothing clipped) and just after each gag (effect visible).

## Plan format

The full `plan.json` format (shots, boxes, cameras, transitions, effect and sound types, anchors
like `"burst#2"` or `"burst+0.4"`, cards, music, lower thirds) is documented at the top of
`$T/motion_comic.py`; read it before writing the plan. The narration fields (`"cast"`,
`"speaker"`, `"pause_after"`, `"audio"`, `"timestamps"`) are the same as in `skill/SKILL.md`.
