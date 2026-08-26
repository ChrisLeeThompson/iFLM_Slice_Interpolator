"""
Slice Interpolator Module

This module provides z-stack slice interpolation for microscopy images.
The main entry point is a generator that yields one interpolated slice at
a time, keeping the workflow consistent with image_filters.py and letting
the worker thread cancel or track progress at any point.

Both current interpolation methods use scipy.interpolate.make_interp_spline.
The spline is built once from the full input stack (unavoidable — it needs
all input slices), but output slices are evaluated and yielded one at a time.

The method object (an InterpolationMethod from processing_config) carries
the spline order k.  No index look-up or if/elif chain lives here.

Focus-value interpolation is a separate, one-shot utility used when
generating the new TFS file.  It stays as a plain function because it
operates on a tiny list of floats and has no reason to be a generator.
"""

import logging
import numpy as np
from scipy.interpolate import make_interp_spline
from typing import Generator, List


logger = logging.getLogger(__name__)


def _new_z_positions(num_slices: int, interpolation_factor: int) -> np.ndarray:
    """Return the new z-position array after interpolation."""
    new_num_slices = (num_slices - 1) * interpolation_factor + 1
    return np.linspace(0, num_slices - 1, new_num_slices)


def interpolate_stack(
    slices: List[np.ndarray],
    method,                                 # InterpolationMethod from processing_config
    interpolation_factor: int = 2
) -> Generator[tuple[int, np.ndarray], None, None]:
    """
    Generator that yields (slice_index, interpolated_image) one slice at a time.

    The spline is fitted once from all input slices, then evaluated at each
    new z-position individually.  This means only one output slice exists in
    memory at a time — the caller can write it to disk before advancing.

    :param slices: List of 2D numpy arrays (one per z-plane)
    :param method: An InterpolationMethod instance from
        processing_config.INTERPOLATION_METHODS.  Carries .name and .k
        (spline order) — no index look-up needed here.
    :param interpolation_factor: Number of output slices per input interval
    :yields: (slice_index, interpolated_image) for each new z-plane in order
    """
    num_input   = len(slices)
    if num_input < method.k + 1:
        raise ValueError(
            f"{method.name} interpolation requires at least {method.k + 1} slices, "
            f"but only {num_input} were provided."
        )
    height, width = slices[0].shape
    orig_dtype  = slices[0].dtype

    # --- build the spline (needs the full input stack) ---
    z_orig      = np.arange(num_input)
    stack_flat  = np.stack(slices, axis=0).reshape(num_input, -1).astype(np.float32)
    spline      = make_interp_spline(z_orig, stack_flat, k=method.k, axis=0)
    # The spline keeps its own (float64) coefficient copy; free the flat
    # stack before the evaluation loop instead of holding both.
    del stack_flat

    # --- compute new z positions ---
    z_new       = _new_z_positions(num_input, interpolation_factor)
    num_output  = len(z_new)

    logger.info(
        f"{method.name} interpolation (k={method.k}): "
        f"{num_input} -> {num_output} slices (factor={interpolation_factor})"
    )

    # --- clipping bounds (only matters for cubic overshoot) ---
    # Integer dtypes clip to their full range and round to the nearest value;
    # float images clip only at 0 (a fixed 1.0 ceiling would destroy float
    # data with values above 1).
    is_integer = np.issubdtype(orig_dtype, np.integer)
    clip_max = float(np.iinfo(orig_dtype).max) if is_integer else None

    # --- yield one slice at a time ---
    for i, z in enumerate(z_new):
        interpolated_flat  = spline(z)
        interpolated_flat  = np.clip(interpolated_flat, 0, clip_max)
        if is_integer:
            interpolated_flat = np.rint(interpolated_flat)
        interpolated_slice = interpolated_flat.reshape(height, width).astype(orig_dtype)

        logger.debug(f"Interpolated slice {i + 1}/{num_output}")
        yield i, interpolated_slice


def calculate_interpolated_focus_values(
    original_focus_values: List[float],
    interpolation_factor: int
) -> List[float]:
    """
    Linearly interpolate focus values to match the new slice count.

    Example:
        Original: [0.0, 1.4, 2.8, 4.2]  (step = 1.4)
        Factor:   2
        Result:   [0.0, 0.7, 1.4, 2.1, 2.8, 3.5, 4.2]  (step = 0.7)

    :param original_focus_values: Focus values from the parsed TFS file
    :param interpolation_factor: Same factor passed to interpolate_stack
    :return: Interpolated focus values as a plain list of floats
    """
    if len(original_focus_values) < 2:
        raise ValueError(
            f"Focus value interpolation requires at least 2 values, "
            f"but only {len(original_focus_values)} were provided."
        )

    orig  = np.array(original_focus_values)
    z_orig = np.arange(len(orig))
    z_new  = _new_z_positions(len(orig), interpolation_factor)

    new_focus = np.interp(z_new, z_orig, orig)

    logger.info(f"Interpolated focus values: {len(orig)} -> {len(new_focus)}")
    logger.debug(f"Original focus step: {orig[1] - orig[0]:.4f}")
    logger.debug(f"New focus step:      {new_focus[1] - new_focus[0]:.4f}")

    return new_focus.tolist()