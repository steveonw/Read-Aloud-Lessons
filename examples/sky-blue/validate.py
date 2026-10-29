#!/usr/bin/env python3
"""Check every number shown on the boards and said in the narration. Fails loudly."""
import json, re
from pathlib import Path
import physics as P

D = Path(__file__).resolve().parent
plan = json.loads((D / 'plan.json').read_text())
said = ' '.join(l['text'].lower() for s in plan['scenes'] for l in s['lines'])
checks = {}

ratio = float(P.rayleigh_relative(450)[()])                      # (700/450)^4
checks['blue/red scattering ratio 5.86 -> "5.9" on board, "almost six" said'] = abs(ratio - 5.855) < .01 and 'almost six' in said
am_h = P.air_mass(90); am_0 = P.air_mass(0)
checks['air mass overhead = 1'] = abs(am_0 - 1) < .001
checks['air mass at horizon about 38 (Kasten-Young), said "thirty eight"'] = 37.5 < am_h < 38.5 and 'thirty eight times' in said
T = lambda nm, am: float(P.transmission(nm, am)) * 100
checks['noon blue ~80% said "eighty percent"'] = round(T(450, am_0)) == 80 and 'eighty percent of the blue' in said
checks['noon red ~96% said "ninety six percent"'] = round(T(700, am_0)) == 96 and 'ninety six percent of the red' in said
checks['sunset blue 0.02% said "two hundredths of a percent"'] = round(T(450, am_h), 2) == 0.02 and 'two hundredths of a percent' in said
checks['sunset red 25% said "a quarter"'] = round(T(700, am_h)) == 25 and 'a quarter of the red' in said
checks['visible range 380-750 nm said'] = 'three hundred eighty to seven hundred fifty' in said
checks['molecule ~0.3 nm vs light 380+ nm: >1000x smaller'] = 380 / 0.3 > 1000
checks['cloud droplet (10-20 um) thousands of times wider than a molecule'] = 10_000 / 0.3 > 1000
checks['optical depth at 450 nm about 0.22'] = abs(float(P.optical_depth(450)) - 0.221) < .005
# board text agrees with the physics (read from the plan's mark list + build script strings)
src = (D / 'build.py').read_text()
checks['board shows "5.9"'] = r'\approx\ 5.9' in src
checks['board shows "about 38 air masses"'] = 'about 38 air masses' in src
# plan sanity
for s in plan['scenes']:
    for l in s['lines']:
        for m in ([l['mark']] if isinstance(l.get('mark'), str) else l.get('mark') or []):
            assert m in s['marks'], (s['title'], m)
checks['quiz question has >= 4 s to think'] = any(l.get('pause_after', 0) >= 4 for s in plan['scenes'] for l in s['lines'] if '?' in l['text'] and 'clouds' in l['text'])
checks['no digits or symbols in narration'] = not re.search(r'[0-9%/=^]', said)

bad = [k for k, v in checks.items() if not v]
lines = ['# Validation: Why the sky is blue but sunsets are red', '',
         'Model: Rayleigh optical depth (Hansen & Travis 1974), air mass (Kasten & Young 1989),',
         'Beer-Lambert transmission through clean air. Real aerosols are not modelled (stated on board 6).', '']
lines += [('- [x] ' if v else '- [ ] ') + k for k, v in checks.items()]
lines += ['', f'Computed: (700/450)^4 = {ratio:.3f}; air mass horizon = {am_h:.2f}; '
          f'noon 450/700 nm = {T(450, am_0):.1f}% / {T(700, am_0):.1f}%; sunset = {T(450, am_h):.4f}% / {T(700, am_h):.1f}%']
(D / 'validation.md').write_text('\n'.join(lines) + '\n')
assert not bad, f'FAILED: {bad}'
print(len(checks), 'checks passed')
