# Notes for AI sessions working on this repo

- `skill/SKILL.md` is the workflow; `tools/` are the tested scripts it calls. Change a tool and the
  text that describes it together.
- Before committing a change to `tools/`, run `python examples/smoke-test/run.py`, then rebuild and
  check both full examples:
  `cd examples/leap-years && python build.py && python validate.py && python ../../tools/render_video.py plan.json --check`
  (same for `examples/sky-blue`). Look at a contact sheet after any change to marks or timing.
- Generated files (PNG, WAV, MP4, labels, caches) are ignored by `.gitignore`; examples are rebuilt
  from `build.py`. Only `docs/` images are committed.
- `narrate.py` caches sentences by a `CACHE_VERSION`; bump it when phoneme rules or synthesis change.
- Keep the narration rules from SKILL.md in the examples: no digits or symbols in spoken text, one
  spelling variant (US), quiz answers on a different image with `"pause_after"` of 4 or more.
