# Zorblook's Magical Exterminators (motion comic example)

A 2:58 parody TV ad: 21 scenes, 58 lines, 7 Kokoro voices, 61 shots, 33 effects, 43 sounds.
`plan.json` is the complete, tested plan. Use it as a template for shot lists, word-anchored
effects (`"at": "burst"`, `"repeat"` hammering, the biscuit `drop`), voice colour and a TV test card.

The art is not in this repo (the repo keeps no images). The plan expects three image-generator
storyboard sheets, 4x upscaled, as `art/sheetA_x4.png`, `art/sheetB_x4.png`, `art/sheetC_x4.png`
(originals 1774x887, 1672x941 and 1672x941; boxes are fractions, so any upscale factor works).
To rebuild with your own art, replace the images and adjust each shot's `box`, then:

```bash
T=../../tools
python $T/motion_comic.py plan.json --check
python $T/narrate.py plan.json --model-dir <kokoro folder> --speed 1.08
python $T/voice_fx.py plan.json --gap 0.3 --scene-gap 0.6
python $T/word_times.py plan.json --asr-dir <sherpa zipformer folder>
python $T/check_audio.py plan.json --asr-dir <sherpa zipformer folder>
python $T/motion_comic.py plan.json --contact-sheet
python $T/motion_comic.py plan.json
```

Measured: narration about 90 s and render about 75 s on 2 CPU cores. `check_audio.py` flags the
one-word line "Oh?" in context although it is heard correctly when voiced alone (a recognizer quirk).
