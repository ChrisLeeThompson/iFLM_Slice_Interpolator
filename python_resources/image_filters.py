"""
Image Filtering Module

This module provides image filtering operations for iFLM data.
All processing is exposed through generators that yield one slice at a time,
making cancellation, progress tracking, and memory usage straightforward
for the worker thread.

Processing pipeline per slice:
    0. Hot pixel correction (optional, if a mask was supplied)
    1. Background subtraction (Minimum Value or Gaussian)
    2. Unsharp masking (if amount > 0)

Hot pixel correction runs first because unsharp masking amplifies an isolated
single-pixel spike ~3.7x at the default settings, and the z-interpolation
spline then copies it into every interpolated plane.  Detection lives in
hot_pixel_filter.py; this module only applies a mask that was already scanned.

Background methods:
    - Minimum Value: subtracts the per-slice minimum pixel value
    - Gaussian: estimates background with a heavy Gaussian blur, then subtracts

Global background normalization (optional):
    When enabled, Gaussian and Minimum Value methods compute a global
    statistic across the stack first, then apply a consistent subtraction
    per slice. This requires a two-pass approach: the first pass computes
    the global value (yielding nothing), and the second pass yields
    processed slices.
"""

import logging
import numpy as np
import cv2
from typing import Generator, List, Optional

from .hot_pixel_filter import HotPixelMask, correct_hot_pixels


logger = logging.getLogger(__name__)


def _to_original_dtype(result: np.ndarray, orig_dtype: np.dtype) -> np.ndarray:
    """
    Clip a float working image and cast it back to the original dtype.

    Integer dtypes clip to their full range and round to the nearest value
    (truncating would darken every pixel by ~0.5 ADU per stage); float images
    clip only at 0, since a fixed 1.0 ceiling would destroy float data with
    values above 1.
    """
    if np.issubdtype(orig_dtype, np.integer):
        result = np.rint(np.clip(result, 0, np.iinfo(orig_dtype).max))
    else:
        result = np.clip(result, 0, None)
    return result.astype(orig_dtype)


# ---------------------------------------------------------------------------
# Per-slice background subtraction
# ---------------------------------------------------------------------------

def _subtract_background_min_value(image: np.ndarray) -> np.ndarray:
    """
    Subtract the minimum pixel value from the image.

    :param image: 2D numpy array (grayscale)
    :return: Background-subtracted image in original dtype
    """
    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    min_val = float_img.min()
    result = _to_original_dtype(float_img - min_val, orig_dtype)
    logger.debug(f"Min value subtraction: min={min_val}")
    return result


def _subtract_background_gaussian(image: np.ndarray, sigma: float) -> np.ndarray:
    """
    Estimate background with a heavy Gaussian blur and subtract it.

    :param image: 2D numpy array (grayscale)
    :param sigma: Gaussian sigma controlling blur strength
    :return: Background-subtracted image in original dtype
    """
    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    background = cv2.GaussianBlur(float_img, (0, 0), sigmaX=sigma)
    result = _to_original_dtype(float_img - background, orig_dtype)

    logger.debug(f"Gaussian background subtraction: sigma={sigma}")
    return result


# Rolling background: the low percentile taken across a neighbourhood of
# blocks.  10 % of a 5x5 block window means bright features can cover up to
# ~90 % of the neighbourhood without inflating the background estimate.
_ROLLING_WINDOW = 5
_ROLLING_PERCENTILE = 10


def _rolling_background_estimate(float_img: np.ndarray, radius: float) -> np.ndarray:
    """
    Smoothed local lower-envelope background (rolling-ball-like).

    INTER_AREA-average into blocks of ~radius/2 px, take a low percentile
    across a 5x5 neighbourhood of blocks, upsample, and smooth.  Same
    block-map idiom as hot_pixel_filter._block_map, but with a low percentile
    instead of a median: the estimate tracks the dim FLOOR of each region, so
    a bright specimen feature cannot drag the background up underneath itself
    the way it drags up a Gaussian mean.
    """
    height, width = float_img.shape
    block = max(int(radius) // 2, 4)
    small_w = max(width // block, 8)
    small_h = max(height // block, 8)
    small = cv2.resize(float_img, (small_w, small_h), interpolation=cv2.INTER_AREA)

    half = _ROLLING_WINDOW // 2
    padded = cv2.copyMakeBorder(small, half, half, half, half, cv2.BORDER_REFLECT)
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (_ROLLING_WINDOW, _ROLLING_WINDOW))
    envelope = np.percentile(
        windows.reshape(small_h, small_w, -1), _ROLLING_PERCENTILE, axis=-1
    ).astype(np.float32)

    background = cv2.resize(envelope, (width, height), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(background, (0, 0), sigmaX=max(radius / 2.0, 1.0))


def _subtract_background_rolling(image: np.ndarray, radius: float) -> np.ndarray:
    """
    Estimate the background as a smoothed local lower envelope and subtract it.

    The Gaussian method subtracts the local MEAN, which by construction sits
    in the middle of the intensity distribution — roughly half of every
    neighbourhood goes negative and is clipped to zero, leaving an edge-image
    look.  The lower envelope sits UNDER the signal, so real features keep
    their intensity and only the illumination gradient is removed.

    :param image: 2D numpy array (grayscale)
    :param radius: Background scale in pixels (features smaller than this
        survive; background variation broader than this is removed)
    :return: Background-subtracted image in original dtype
    """
    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    background = _rolling_background_estimate(float_img, radius)
    result = _to_original_dtype(float_img - background, orig_dtype)

    logger.debug(f"Rolling background subtraction: radius={radius}")
    return result


# ---------------------------------------------------------------------------
# Global background statistics (first pass for stack-consistent mode)
# ---------------------------------------------------------------------------

def _compute_global_min(slices: List[np.ndarray]) -> float:
    """Compute the global minimum across a list of slices."""
    return float(min(s.min() for s in slices))


def _compute_global_gaussian_median(slices: List[np.ndarray], sigma: float) -> float:
    """Compute the median of per-slice Gaussian background medians."""
    medians = []
    for s in slices:
        bg = cv2.GaussianBlur(s.astype(np.float32), (0, 0), sigmaX=sigma)
        medians.append(float(np.median(bg)))
    logger.debug(f"Global Gaussian median: sigma={sigma}, median={np.median(medians)}")
    return float(np.median(medians))


def _compute_global_rolling_median(slices: List[np.ndarray], radius: float) -> float:
    """Compute the median of per-slice rolling background medians."""
    medians = []
    for s in slices:
        bg = _rolling_background_estimate(s.astype(np.float32), radius)
        medians.append(float(np.median(bg)))
    logger.debug(f"Global rolling median: radius={radius}, median={np.median(medians)}")
    return float(np.median(medians))


# ---------------------------------------------------------------------------
# Per-slice subtraction with global normalization
# ---------------------------------------------------------------------------

def _subtract_global_min(image: np.ndarray, global_min: float) -> np.ndarray:
    """Subtract a precomputed global minimum from a single slice."""
    orig_dtype = image.dtype
    result = image.astype(np.float32) - global_min
    return _to_original_dtype(result, orig_dtype)


def _subtract_global_gaussian(image: np.ndarray, sigma: float, global_bg_median: float) -> np.ndarray:
    """
    Subtract a Gaussian background normalized to a global median.

    The local background is shifted so its median matches the global median
    before subtraction, keeping intensity levels consistent across the stack.
    """
    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    local_bg = cv2.GaussianBlur(float_img, (0, 0), sigmaX=sigma)
    normalized_bg = local_bg - np.median(local_bg) + global_bg_median
    result = float_img - normalized_bg
    return _to_original_dtype(result, orig_dtype)


def _subtract_global_rolling(image: np.ndarray, radius: float, global_bg_median: float) -> np.ndarray:
    """
    Subtract a rolling background normalized to a global median.

    Same normalization idea as _subtract_global_gaussian: the local envelope
    is shifted so its median matches the global median, keeping intensity
    levels consistent across the stack.
    """
    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    local_bg = _rolling_background_estimate(float_img, radius)
    normalized_bg = local_bg - np.median(local_bg) + global_bg_median
    result = float_img - normalized_bg
    return _to_original_dtype(result, orig_dtype)


# ---------------------------------------------------------------------------
# Unsharp masking
# ---------------------------------------------------------------------------

def _apply_unsharp_mask(image: np.ndarray, ksize: tuple, sigma: float, amount: float) -> np.ndarray:
    """
    Enhance edges via unsharp masking.

    Algorithm:
        mask   = original - GaussianBlur(original, sigma)
        result = original + amount * mask

    :param image: 2D numpy array
    :param ksize: kernel size
    :param sigma: Gaussian sigma for the blur used to build the mask
    :param amount: Sharpening strength (0 = no-op)
    :return: Sharpened image in original dtype
    """
    if amount == 0:
        return image

    orig_dtype = image.dtype
    float_img = image.astype(np.float32)

    blurred = cv2.GaussianBlur(float_img, ksize=ksize, sigmaX=sigma)
    mask = float_img - blurred
    sharpened = float_img + (amount * mask)
    sharpened = _to_original_dtype(sharpened, orig_dtype)

    kernel_mode = "auto" if ksize == (0, 0) else f"{ksize[0]}×{ksize[1]}"
    logger.debug(f"Unsharp mask: kernel={kernel_mode}, sigma={sigma}, amount={amount}")
    return sharpened


# ---------------------------------------------------------------------------
# Public generator — the single entry point the worker thread calls
# ---------------------------------------------------------------------------

def process_stack(
    slices: List[np.ndarray],
    method,                                 # FilterMethod from processing_config
    gaussian_sigma: float = 50.0,
    unsharp_ksize: tuple = (3, 3),
    unsharp_sigma: float = 0.5,
    unsharp_amount: float = 7.0,
    global_background_normalization: bool = False,
    hot_pixel_mask: Optional[HotPixelMask] = None
) -> Generator[tuple[int, np.ndarray], None, None]:
    """
    Generator that yields (slice_index, processed_image) one slice at a time.

    The worker thread drives this with a simple for-loop.  Cancellation is
    free: just stop iterating.  Memory stays low because only one processed
    slice exists at a time — the caller writes it to disk (or hands it to
    the interpolator) before advancing.

    :param slices: List of 2D numpy arrays (one per z-plane, already loaded)
    :param method: A FilterMethod instance from processing_config.IMAGE_FILTER_METHODS.
        Carries subtract(), compute_global(), and apply_global() — no index
        look-up needed here.
    :param gaussian_sigma: Sigma for Gaussian background (ignored by methods
        that don't use it — the FilterMethod lambdas absorb it silently)
    :param unsharp_sigma: Sigma for unsharp mask Gaussian blur
    :param unsharp_amount: Sharpening strength (0 disables unsharp masking)
    :param global_background_normalization: If True, run a first pass to
        compute a global statistic, then use it for consistent subtraction
    :param hot_pixel_mask: Optional HotPixelMask from hot_pixel_filter.
        scan_hot_pixels.  When supplied, persistent defects are repaired in
        every slice and transient detections in the slice where they occurred,
        before background subtraction.  `slices` must be the same list (same
        order and length) the scan consumed, since slice indices map 1:1 - the
        worker guarantees this.  None disables the step.
    :yields: (slice_index, processed_image) for each plane in order
    """
    num_slices = len(slices)
    logger.info(
        f"Starting filter pass: method={method.name}, "
        f"global_norm={global_background_normalization}, "
        f"slices={num_slices}, "
        f"hot_pixels="
        + (f"{hot_pixel_mask.count} persistent + "
           f"{hot_pixel_mask.transient_total} transient"
           if hot_pixel_mask is not None else "off")
    )

    # ------------------------------------------------------------------
    # First pass: compute global statistic if needed (no yields here)
    # ------------------------------------------------------------------
    # Note: the global statistic is computed on the UNCORRECTED slices.  That
    # is safe for a hot-pixel (bright-only) mask - _compute_global_min takes a
    # minimum, which a bright pixel can never set, and
    # _compute_global_gaussian_median takes the median of a heavy blur, which
    # ~0.1% of pixels in the upper tail cannot move.  Both tiers are bright-
    # only (transients included), so the reasoning covers them equally.  It
    # INVERTS if a cold/dead-pixel branch is ever added: a pixel stuck at 0
    # does set the minimum, and the correction would have to run before this
    # pass.
    global_stat = None
    if global_background_normalization:
        global_stat = method.compute_global(slices, gaussian_sigma)
        logger.info(f"Global statistic for {method.name}: {global_stat}")

    # ------------------------------------------------------------------
    # Second pass: process and yield one slice at a time
    # ------------------------------------------------------------------
    for i, raw in enumerate(slices):

        # --- hot pixel correction (before anything can amplify a defect) ---
        if hot_pixel_mask is not None:
            raw = correct_hot_pixels(raw, hot_pixel_mask, slice_index=i)

        # --- background subtraction ---
        if global_background_normalization:
            subtracted = method.apply_global(raw, gaussian_sigma, global_stat)
        else:
            subtracted = method.subtract(raw, gaussian_sigma)

        # --- unsharp masking ---
        processed = _apply_unsharp_mask(subtracted, unsharp_ksize, unsharp_sigma, unsharp_amount)

        logger.debug(f"Filtered slice {i + 1}/{num_slices}")
        yield i, processed