"""Physics used by the boards and checked by validate.py (single source of numbers)."""
import math
import numpy as np


def rayleigh_relative(nm, ref=700.0):
    """Rayleigh scattering strength relative to the reference wavelength: (ref/nm)^4."""
    return (ref / np.asarray(nm, dtype=float)) ** 4


def optical_depth(nm):
    """Rayleigh optical depth of the whole atmosphere at sea level (Hansen & Travis 1974), nm in nanometres."""
    l = np.asarray(nm, dtype=float) / 1000.0
    return 0.008569 * l ** -4 * (1 + 0.0113 * l ** -2 + 0.00013 * l ** -4)


def air_mass(zenith_deg):
    """Relative air mass (Kasten & Young 1989); 1 overhead, about 38 at the horizon."""
    z = zenith_deg
    return 1.0 / (math.cos(math.radians(z)) + 0.50572 * (96.07995 - z) ** -1.6364)


def transmission(nm, am):
    """Fraction of direct sunlight that gets through clean air (Beer-Lambert, Rayleigh only)."""
    return np.exp(-optical_depth(nm) * am)
