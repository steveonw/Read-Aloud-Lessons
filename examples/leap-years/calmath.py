"""Calendar numbers used by the boards, the script and validate.py (single source of numbers)."""

TROPICAL = 365.24219      # mean tropical year in days (solar year, equinox to equinox)
JULIAN = 365.25           # leap day every 4th year
NICAEA, REFORM, BRITAIN = 325, 1582, 1752


def is_leap_julian(y):
    return y % 4 == 0


def is_leap_gregorian(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def mean_year(is_leap, span=400):
    """Average calendar year over one full rule cycle."""
    return 365 + sum(is_leap(y) for y in range(2000, 2000 + span)) / span


GREGORIAN = mean_year(is_leap_gregorian)          # 365.2425


def extra_hm(days=TROPICAL):
    """Part of a day beyond 365, as (hours, minutes)."""
    m = round((days - 365) * 24 * 60)
    return divmod(m, 60)


def error_minutes(cal):
    return (cal - TROPICAL) * 24 * 60


def years_per_day(cal):
    return 1 / (cal - TROPICAL)


def drift_days(year, start=NICAEA, cal=JULIAN):
    return (year - start) * (cal - TROPICAL)


def skipped(last_old_day, first_new_day):
    """Calendar days left out when the day after `last_old_day` is numbered `first_new_day`."""
    return first_new_day - last_old_day - 1
