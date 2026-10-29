#!/usr/bin/env python3
"""Smoke test: prove the toolchain works on this machine in about 15 seconds, no voice model needed.

  python examples/smoke-test/run.py

Draws one single board and one 2x2 panel page with the Board helper, writes plan.json, then runs
render_video.py --check, --contact-sheet and a silent --preview. Fails loudly on any problem.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from board import Board, ACCENT          # noqa: E402

out = HERE / "out"; out.mkdir(exist_ok=True)

b = Board(str(out / "board01.png"))
b.title("Smoke test: single board")
b.text(.06, .66, r"$f(x)=x^2$", 40, ACCENT, name="F")
ax = b.axes([.55, .2, .38, .55])
xs = [i / 10 for i in range(-20, 21)]; ax.plot(xs, [x * x for x in xs], color=ACCENT)
b.ring("min", ax, 0, 0)
m1 = b.save()

p = Board(str(out / "page01.png"), grid=(2, 2))
for c, r in [(0, 0), (1, 0), (0, 1), (1, 1)]:
    p.title(f"Panel {c},{r}", panel=(c, r))
    p.text(.06, .5, f"Item in panel {c},{r}", 32, ACCENT, name="item", panel=(c, r))
m2 = p.save()

panel = lambda c, r: [c * .5, r * .5, .5, .5]
plan = {"title": "Smoke test", "scenes": [
    {"title": "Single board", "image": "board01.png", "marks": m1, "lines": [
        {"text": "This is a parabola.", "mark": "F"},
        {"text": "Its lowest point is the origin.", "mark": "min"}]},
    {"title": "Panel one", "image": "page01.png", "panel": panel(0, 0), "marks": m2[(0, 0)],
     "lines": [{"text": "Panels work too.", "mark": "item"}]},
    {"title": "Panel four", "image": "page01.png", "panel": panel(1, 1), "marks": m2[(1, 1)],
     "lines": [{"text": "And the glide lands on the right panel.", "mark": "item"}]}]}
(out / "plan.json").write_text(json.dumps(plan, indent=1))

render = [sys.executable, str(TOOLS / "render_video.py"), str(out / "plan.json")]
for extra in (["--check"], ["--contact-sheet", "--preview"], ["--preview", "--out", str(out / "preview.mp4")]):
    r = subprocess.run(render + extra, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode:
        sys.exit(f"FAILED: render_video.py {' '.join(extra)}\n{r.stderr}")
for f in ("board01.png", "page01.png", "preview_contact.png", "preview.mp4"):
    if not (out / f).exists(): sys.exit(f"FAILED: {f} was not made")
print(f"SMOKE TEST PASSED. Open {out / 'preview_contact.png'} to see every mark.")
