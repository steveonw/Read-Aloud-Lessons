#!/usr/bin/env python3
"""Check every number shown on the boards and said in the narration. Fails loudly."""
import json
from pathlib import Path
import calmath as C

D = Path(__file__).resolve().parent
plan = json.loads((D / 'plan.json').read_text())
said = ' '.join(l['text'].lower() for s in plan['scenes'] for l in s['lines'])
src = (D / 'build.py').read_text()
ck = {}

ck['solar year 365.2422 shown; "three hundred sixty five point two four two two" said'] = \
    f'{C.TROPICAL:.4f}' == '365.2422' and 'three hundred sixty five point two four two two days' in said
ck['extra part of the year = 5 h 49 min; "five hours and forty nine minutes" said'] = \
    C.extra_hm() == (5, 49) and 'five hours and forty nine minutes' in said
ck['about a quarter day short each year'] = abs((C.TROPICAL - 365) - 0.25) < 0.01 and 'quarter of a day' in said
ck['Julian average 365.25 from the every-4-years rule'] = C.mean_year(C.is_leap_julian) == C.JULIAN == 365.25 \
    and 'three hundred sixty five and a quarter days' in said
ck['Julian too long by about 11 minutes; "eleven minutes" said'] = round(C.error_minutes(C.JULIAN)) == 11 \
    and 'eleven minutes' in said
ck['Julian drifts 1 day per 128 years; said'] = round(C.years_per_day(C.JULIAN)) == 128 \
    and 'hundred and twenty eight years' in said
ck['drift 325 -> 1582 is about 10 days; "about ten days" said'] = round(C.drift_days(C.REFORM)) == 10 \
    and 'about ten days out of step' in said
ck['equinox March 21 - ~10 days = about March 11'] = 21 - round(C.drift_days(C.REFORM)) == 11 \
    and 'march eleventh' in said
ck['Gregorian average 365.2425 from the 3 rules; said'] = abs(C.GREGORIAN - 365.2425) < 1e-12 \
    and 'three hundred sixty five point two four two five days' in said
ck['Gregorian drifts 1 day in more than 3,000 years (3,226)'] = 3000 < C.years_per_day(C.GREGORIAN) < 3300 \
    and 'more than three thousand years' in said and '~3,200' in src
ck['3 leap days dropped per 400 years'] = sum(C.is_leap_julian(y) and not C.is_leap_gregorian(y)
                                              for y in range(2000, 2400)) == 3 and 'three leap days' in said
ck['1582: Oct 4 then Oct 15 skips 10 days'] = C.skipped(4, 15) == 10 and 'ten days were simply skipped' in said
ck['1752: Sep 2 then Sep 14 skips 11 days'] = C.skipped(2, 14) == 11 and 'skip eleven days' in said
ck['1900 not leap, 2000 leap, 2100 not leap'] = (not C.is_leap_gregorian(1900) and C.is_leap_gregorian(2000)
                                                 and not C.is_leap_gregorian(2100))
ck['answer board arithmetic: 2100/4=525, /100=21, /400=5.25, 2000/400=5'] = \
    (2100 / 4, 2100 / 100, 2100 / 400, 2000 / 400) == (525, 21, 5.25, 5)
quiz = [l for s in plan['scenes'] for l in s['lines'] if 'twenty one hundred a leap year' in l['text']]
ck['quiz question has 5 s to think and the answer is on a different image'] = \
    quiz and quiz[0].get('pause_after') == 5 and plan['scenes'][-1]['image'] != plan['scenes'][-2]['image']

bad = [k for k, v in ck.items() if not v]
lines = ['# Validation: Why Leap Years Exist', '',
         f'Solar (tropical) year {C.TROPICAL} days; Julian {C.JULIAN}; Gregorian {C.GREGORIAN} '
         '(computed from the rules over a 400-year cycle).',
         'History: Julian calendar from 45 BC; Council of Nicaea 325; Gregorian reform October 1582 '
         '(Thu 4 -> Fri 15); Britain and colonies September 1752 (2 -> 14).', '']
lines += [('- [x] ' if v else '- [ ] ') + k for k, v in ck.items()]
(D / 'validation.md').write_text('\n'.join(lines) + '\n')
assert not bad, f'FAILED: {bad}'
print(len(ck), 'checks passed')
