"""Leap-year video: draw two 2x2 panel pages + one answer board, write plan.json."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))   # tools/board.py
from matplotlib.patches import Rectangle, FancyArrowPatch
from board import Board, INK, ACCENT
import calmath as C

BLUE, RED, MUTED = "#7CC8FF", "#FF8A7A", "#A7B7C1"
PANEL = {(0, 0): [0, 0, .5, .5], (1, 0): [.5, 0, .5, .5], (0, 1): [0, .5, .5, .5], (1, 1): [.5, .5, .5, .5]}
T = f"{C.TROPICAL:.4f}"                      # 365.2422
H, M = C.extra_hm()                          # 5 h 49 min


def take(b, p, s, name):                     # takeaway bar at the bottom of a panel
    b.text(.06, .1, s, 26, ACCENT, name=name, panel=p, weight="bold")


# ---------------- page 1 ----------------
b = Board("page01.png", grid=(2, 2))
p = (0, 0); b.title("Why does February get an extra day?", p)
b.text(.06, .66, "February 29", 64, ACCENT, name="F29", panel=p, weight="bold")
b.text(.06, .47, "Leap day: one extra day that keeps the calendar", 26, name="def", panel=p)
b.text(.06, .40, "in step with the Sun and the seasons", 26, name="def2", panel=p)
b.text(.06, .26, "Every four years ... almost", 30, BLUE, name="almost", panel=p)

p = (1, 0); b.title("A year is not a whole number of days", p)
b.text(.06, .73, "One trip around the Sun:", 26, MUTED, panel=p)
b.text(.06, .62, f"{T} days", 44, ACCENT, name="Y", panel=p, weight="bold")
b.text(.06, .49, f"= 365 days + {H} h {M} min", 28, name="extra", panel=p)
b.text(.06, .37, "A calendar year holds 365 whole days", 26, name="cal", panel=p)
b.text(.06, .25, r"$4 \times$ about $\frac{1}{4}$ day  $\approx$  1 whole day", 26, BLUE, name="four", panel=p)
ax = b.axes([.58, .30, .37, .22], p); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.add_patch(Rectangle((0, .3), .78, .4, color="#2C4A63"))
left = ax.add_patch(Rectangle((.8, .3), .2, .4, color=RED))
ax.text(.39, .5, "365 days", ha="center", va="center", fontsize=20, color=INK)
ax.text(.9, .5, r"$\approx\frac{1}{4}$", ha="center", va="center", fontsize=20, color="#0B1015")
ax.text(.5, .05, "(not to scale)", ha="center", fontsize=14, color=MUTED)
b.box("left", left, p)

p = (0, 1); b.title("Caesar's fix: a leap day every 4 years", p)
b.text(.06, .73, "Julian calendar (Julius Caesar, 45 BC)", 26, MUTED, name="jul", panel=p)
b.text(.06, .60, "Every 4th year gets February 29", 30, name="rule4", panel=p)
b.text(.06, .47, f"Average year: {C.JULIAN:.2f} days", 30, ACCENT, name="avg", panel=p)
b.text(.06, .34, f"Too long by {C.JULIAN - C.TROPICAL:.4f} day", 28, RED, name="err", panel=p)
b.text(.06, .27, f"= about {round(C.error_minutes(C.JULIAN))} minutes every year", 28, RED, name="err2", panel=p)
take(b, p, "Small errors pile up.", "take1")

p = (1, 1); b.title("Eleven minutes a year adds up", p)
ax = b.axes([.09, .2, .44, .52], p); ax.set_facecolor("#0B1015")
yrs = np.arange(C.NICAEA, C.REFORM + 1)
ax.plot(yrs, C.drift_days(yrs), color=ACCENT, lw=3)
ax.set_xlim(300, 1620); ax.set_ylim(0, 11)
ax.set_xlabel("year", fontsize=16, color=MUTED); ax.set_ylabel("days of drift", fontsize=16, color=MUTED)
ax.tick_params(colors=MUTED, labelsize=14)
for s in ax.spines.values(): s.set_color("#3A4A55")
b.box("chart", ax, p)
b.ring("G1582", ax, C.REFORM, C.drift_days(C.REFORM), r=.04, panel=p)
b.text(.58, .66, "325: Council of Nicaea fixes", 22, name="nicaea", panel=p)
b.text(.58, .60, "the spring equinox on March 21", 22, name="nicaea2", panel=p)
b.text(.58, .45, f"1582: about {round(C.drift_days(C.REFORM))} days off", 24, ACCENT, name="ten", panel=p)
b.text(.58, .33, "Equinox now falls on", 22, BLUE, name="mar11", panel=p)
b.text(.58, .27, "about March 11", 22, BLUE, name="mar11b", panel=p)
m1 = b.save()

# ---------------- page 2 ----------------
b = Board("page02.png", grid=(2, 2))
p = (0, 0); b.title("Gregory's sharper rule (1582)", p)
b.text(.06, .73, "Gregorian calendar (Pope Gregory XIII)", 26, MUTED, name="greg", panel=p)
b.text(.06, .60, "1.  Divisible by 4  →  leap year", 28, name="r1", panel=p)
b.text(.06, .50, "2.  Divisible by 100  →  not a leap year", 28, name="r2", panel=p)
b.text(.06, .40, "3.  Divisible by 400  →  leap year after all", 28, name="r3", panel=p)
b.text(.06, .25, f"Average year: {C.GREGORIAN:.4f} days", 30, ACCENT, name="avg2", panel=p)

p = (1, 0); b.title("Ten days that never happened", p)
b.text(.06, .70, "Thursday, October 4, 1582", 34, name="d4", panel=p)
b.text(.10, .60, "next day", 22, MUTED, panel=p)
b.text(.06, .50, "Friday, October 15, 1582", 34, ACCENT, name="d15", panel=p)
b.text(.06, .32, f"Britain and its colonies, 1752: September 2 → September 14", 22, name="uk", panel=p)
b.text(.06, .26, f"({C.skipped(2, 14)} days skipped)", 22, MUTED, name="uk2", panel=p)
b.fig.add_artist(FancyArrowPatch(b._fig(.08, .66, p), b._fig(.08, .55, p), transform=b.fig.transFigure,
                                 arrowstyle="-|>", mutation_scale=30, color=MUTED, lw=2))

p = (0, 1); b.title("Three numbers side by side", p)
b.text(.06, .70, f"Real solar year:  {T} days", 28, name="real", panel=p)
b.text(.06, .56, f"Julian:  {C.JULIAN:.2f}  →  1 day off every {round(C.years_per_day(C.JULIAN))} years", 28,
       RED, name="jrow", panel=p)
b.text(.06, .42, f"Gregorian:  {C.GREGORIAN:.4f}  →  1 day off every ~3,200 years", 28,
       BLUE, name="grow", panel=p)
take(b, p, "Leap rules keep the calendar in step with the seasons.", "take2")

p = (1, 1); b.title("Test yourself", p)
b.text(.06, .60, "Is 2100 a leap year?", 52, ACCENT, name="q", panel=p, weight="bold")
b.text(.06, .40, "Check the three rules:  divisible by 4?  by 100?  by 400?", 24, MUTED, name="hint", panel=p)
b.text(.06, .22, "Pause the video and decide.", 24, BLUE, panel=p)
m2 = b.save()

# ---------------- answer board ----------------
b = Board("board03.png")
b.title("Answer: 2100 is not a leap year")
b.text(.06, .72, "2100 / 4 = 525  →  divisible by 4", 30, name="a1")
b.text(.06, .60, "2100 / 100 = 21  →  a century year", 30, name="a2")
b.text(.06, .48, "2100 / 400 = 5.25  →  not divisible by 400", 30, name="a3")
b.text(.06, .33, "So 2100 gets no February 29", 38, ACCENT, name="ans", weight="bold")
b.text(.06, .18, "But 2000 did: 2000 / 400 = 5", 30, BLUE, name="bonus")
m3 = b.save()


def merge(m, a, b2):                          # one box around a phrase drawn on two lines
    x0, y0, x1, y1 = m[a]["box"]; u0, v0, u1, v1 = m[b2]["box"]
    m[a] = {"box": [min(x0, u0), min(y0, v0), max(x1, u1), max(y1, v1)]}; del m[b2]


merge(m1[(0, 0)], "def", "def2"); merge(m1[(0, 1)], "err", "err2")
merge(m1[(1, 1)], "nicaea", "nicaea2"); merge(m1[(1, 1)], "mar11", "mar11b"); merge(m2[(1, 0)], "uk", "uk2")

N, S, Tc = None, "student", "teacher"
L = lambda text, mark=None, who=N, **kw: {"text": text, **({"mark": mark} if mark else {}),
                                          **({"speaker": who} if who else {}), **kw}
scenes = [
 ("page01.png", (0, 0), m1, "Why February gets an extra day", [
   L("Every few years, February gets an extra day, the twenty ninth.", "F29"),
   L("Why does February get a bonus day at all?", None, S),
   L("Because our calendar has to keep pace with the Sun, and the Sun does not count in whole days.", "def", Tc),
   L("A leap day is a small correction that keeps the seasons where we expect them.", "def", Tc),
   L("And it really comes every four years?", "almost", S),
   L("Almost every four years, and that word almost is the whole story.", "almost", Tc)]),
 ("page01.png", (1, 0), m1, "A year is not whole days", [
   L("Earth takes about three hundred sixty five point two four two two days to go once around the Sun.", "Y"),
   L("That is three hundred sixty five days, plus about five hours and forty nine minutes.", "extra", Tc),
   L("But a calendar year can only hold whole days, so it stops at three hundred sixty five.", "cal", Tc),
   L("So every year the calendar falls a little short?", "left", S),
   L("Yes, almost a quarter of a day short, every single year.", "left", Tc),
   L("After four years, those quarters add up to nearly one whole day.", "four", Tc)]),
 ("page01.png", (0, 1), m1, "Caesar's fix", [
   L("More than two thousand years ago, Julius Caesar fixed this with a simple rule.", "jul"),
   L("Add one extra day to every fourth year.", "rule4", Tc),
   L("Three short years and one long year average out to three hundred sixty five and a quarter days.", "avg", Tc),
   L("That sounds perfect.", None, S),
   L("Close, but it is too long by about eleven minutes every year.", "err", Tc),
   L("Eleven minutes sounds tiny, but small errors pile up.", "take1", Tc)]),
 ("page01.png", (1, 1), m1, "Eleven minutes a year adds up", [
   L("This graph shows how far the Julian calendar drifted from the Sun.", "chart"),
   L("In the year three twenty five, church leaders tied the spring equinox to March twenty first.", "nicaea", Tc),
   L("From then on, the gap grew by eleven minutes every year.", "chart", Tc),
   L("By fifteen eighty two, the calendar was about ten days out of step.", ["G1582", "ten"], Tc),
   L("So the first day of spring had slid back to March eleventh?", "mar11", S),
   L("Exactly, and Easter, which is set from that date, was drifting too.", "mar11", Tc)]),
 ("page02.png", (0, 0), m2, "Gregory's sharper rule", [
   L("In fifteen eighty two, Pope Gregory the thirteenth introduced a sharper rule.", "greg"),
   L("Years divisible by four are still leap years.", "r1", Tc),
   L("But century years, like nineteen hundred, are not.", "r2", Tc),
   L("Unless the century year divides by four hundred, like the year two thousand.", "r3", Tc),
   L("So three leap days get dropped every four hundred years?", ["r2", "r3"], S),
   L("Right, and that brings the average year to three hundred sixty five point two four two five days.", "avg2", Tc)]),
 ("page02.png", (1, 0), m2, "Ten days that never happened", [
   L("To put the seasons back in place, ten days were simply skipped."),
   L("In much of Catholic Europe, Thursday October fourth was followed by Friday October fifteenth.", ["d4", "d15"], Tc),
   L("People went to bed and woke up ten days later?", "d15", S),
   L("On paper, yes, though nobody actually lost any sleep.", None, Tc),
   L("Britain and its American colonies waited until seventeen fifty two, and by then they had to skip eleven days.", "uk", Tc)]),
 ("page02.png", (0, 1), m2, "Three numbers side by side", [
   L("Let's put the three numbers side by side."),
   L("The real solar year is about three hundred sixty five point two four two two days.", "real", Tc),
   L("The Julian rule drifts one whole day every hundred and twenty eight years.", "jrow", Tc),
   L("The Gregorian rule drifts one day in more than three thousand years.", "grow", Tc),
   L("Leap rules exist to keep the calendar in step with the seasons.", "take2")]),
 ("page02.png", (1, 1), m2, "Test yourself", [
   L("Now it's your turn to test yourself."),
   L("Using the three rules, is the year twenty one hundred a leap year?", "q", pause_after=5)]),
 ("board03.png", None, {None: m3}, "Answer", [
   L("Twenty one hundred divides by four, so it starts out looking like a leap year.", "a1", Tc),
   L("But it is a century year, because it divides by one hundred.", "a2", Tc),
   L("And it does not divide by four hundred.", "a3", Tc),
   L("So twenty one hundred gets no February twenty ninth!", "ans", S),
   L("That's right, while the year two thousand did get one, because it divides by four hundred.", "bonus", Tc),
   L("So the next time February has twenty nine days, thank Julius Caesar and Pope Gregory.")]),
]
plan = {"title": "Why Leap Years Exist", "width": 1920, "fps": 24, "captions": False,
        "audio": "narration.wav", "timestamps": "labels.txt",
        "cast": {"narrator": "af_heart", "student": {"kokoro": "am_adam", "kitten": 3},
                 "teacher": {"kokoro": "bf_emma", "kitten": 2}},
        "scenes": []}
for img, p, marks, title, lines in scenes:
    sc = {"title": title, "image": img, "marks": marks[p], "lines": lines}
    if p is not None: sc["panel"] = PANEL[p]
    plan["scenes"].append(sc)
json.dump(plan, open("plan.json", "w"), indent=1)
w = sum(len(l["text"].split()) for s in plan["scenes"] for l in s["lines"])
print(f'{len(plan["scenes"])} scenes, {sum(len(s["lines"]) for s in plan["scenes"])} lines, {w} words')
