"""
Processing Configuration Registry

Single source of truth for all image processing methods.  Every other
module in the pipeline — the UI, image_filters, slice_interpolator —
pulls its method information from here.  Adding, removing, or reordering
a method means editing one list in one place.

How it works
------------
Each method is a dataclass instance that bundles together everything
needed to use that method: its display name (for the UI ComboBox) and
the actual callable(s) that do the work.  The *position* in the list
IS the index that gets stored in ProcessingParams and passed around.
No module ever needs to know what that index means — it just looks up
the object at that position and calls what it finds.

Adding a new filter method, for example, is three steps:
    1. Write the functions in image_filters.py
    2. Add a FilterMethod(...) entry to IMAGE_FILTER_METHODS here
    3. Done — the UI picks up the name, the worker picks up the functions.

FilterMethod
------------
Each background-subtraction method needs three operations:

    subtract(image, gaussian_sigma)
        Per-slice subtraction.  gaussian_sigma is ignored by methods
        that don't use it (e.g. Minimum Value) — kept in the signature
        so every method has the same call shape and the generator loop
        doesn't need to branch.

    compute_global(slices, gaussian_sigma)
        First-pass statistic when global_background_normalization is on.
        Returns a single float (the global stat) that is then passed to
        apply_global for every slice.  Same sigma convention as above.

    apply_global(image, gaussian_sigma, global_stat)
        Per-slice subtraction using the precomputed global stat.

InterpolationMethod
-------------------
Both current interpolation methods use the exact same spline machinery —
the only thing that differs is the spline order k.  So the dataclass
just carries the name and k; slice_interpolator reads k and passes it
to make_interp_spline.  If a future method needs fundamentally different
logic, a callable field can be added the same way FilterMethod does it.
"""

import numpy as np
from dataclasses import dataclass
from typing import Callable, List


# ---------------------------------------------------------------------------
# Dataclass definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FilterMethod:
    """A single background-subtraction method, fully self-contained."""

    name: str                                                       # UI display name

    subtract: Callable[[np.ndarray, float], np.ndarray]             # per-slice
    compute_global: Callable[[List[np.ndarray], float], float]      # first-pass stat
    apply_global: Callable[[np.ndarray, float, float], np.ndarray]  # per-slice with stat


@dataclass(frozen=True)
class InterpolationMethod:
    """A single spline-based interpolation method."""

    name: str           # UI display name
    description: str    # UI description label
    k: int              # spline order passed to make_interp_spline


# ---------------------------------------------------------------------------
# Import the actual functions (after dataclass defs, to avoid circular issues)
# ---------------------------------------------------------------------------
# These are imported here rather than at module top so that processing_config
# can be imported by anything without pulling in numpy/cv2/scipy until the
# lists below are actually accessed.  In practice the imports happen at
# module load time anyway, but this keeps the intent clear.

from .image_filters import (
    _subtract_background_min_value,
    _subtract_background_gaussian,
    _subtract_background_rolling,
    _compute_global_min,
    _compute_global_gaussian_median,
    _compute_global_rolling_median,
    _subtract_global_min,
    _subtract_global_gaussian,
    _subtract_global_rolling,
)


# ---------------------------------------------------------------------------
# The registries — edit these lists to change what the app offers
# ---------------------------------------------------------------------------

IMAGE_FILTER_METHODS: List[FilterMethod] = [
    FilterMethod(
        name            = "Minimum Value",
        subtract        = lambda image, sigma: _subtract_background_min_value(image),
        compute_global  = lambda slices, sigma: _compute_global_min(slices),
        apply_global    = lambda image, sigma, stat: _subtract_global_min(image, stat),
    ),
    FilterMethod(
        name            = "Gaussian Background",
        subtract        = _subtract_background_gaussian,
        compute_global  = _compute_global_gaussian_median,
        apply_global    = _subtract_global_gaussian,
    ),
    # Appended so the stored indices of the two methods above never change.
    FilterMethod(
        name            = "Rolling Background",
        subtract        = _subtract_background_rolling,
        compute_global  = _compute_global_rolling_median,
        apply_global    = _subtract_global_rolling,
    ),
]

INTERPOLATION_METHODS: List[InterpolationMethod] = [
    InterpolationMethod(name="Linear Spline", description="Linear interpolation with SciPy", k=1),
    InterpolationMethod(name="Cubic Spline",  description="Cubic interpolation with SciPy",  k=3),
]


# ---------------------------------------------------------------------------
# Convenience helpers used by iflm_slice_interpolator.py to feed the UI
# ---------------------------------------------------------------------------

def get_filter_method_names() -> List[str]:
    """Return display names in registry order — ready for a ComboBox."""
    return [m.name for m in IMAGE_FILTER_METHODS]


def get_interpolation_method_names() -> List[str]:
    """Return display names in registry order — ready for a ComboBox."""
    return [m.name for m in INTERPOLATION_METHODS]


def get_interpolation_method_descriptions() -> List[str]:
    """Return descriptions in registry order — indexed by ComboBox currentIndex."""
    return [m.description for m in INTERPOLATION_METHODS]