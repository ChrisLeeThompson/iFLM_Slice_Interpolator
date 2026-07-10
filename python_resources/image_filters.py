"""
Image Filtering Module

This module provides image filtering operations for iFLM data.
All processing is exposed through generators that yield one slice at a time,
making cancellation, progress tracking, and memory usage straightforward
for the worker thread.

Processing pipeline per slice:
    1. Background subtraction (Minimum Value or Gaussian)
    2. Unsharp masking (if amount > 0)

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
from typing import Generator, List


logger = logging.getLogger(__name__)


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
    result = float_img - min_val

    result = np.clip(result, 0, None).astype(orig_dtype)
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
    result = float_img - background

    # Integer dtypes clip to their full range; float images clip only at 0
    # (a fixed 1.0 ceiling would destroy float data with values above 1).
    max_val = np.iinfo(orig_dtype).max if np.issubdtype(orig_dtype, np.integer) else None
    result = np.clip(result, 0, max_val).astype(orig_dtype)

    logger.debug(f"Gaussian background subtraction: sigma={sigma}")
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


# ---------------------------------------------------------------------------
# Per-slice subtraction with global normalization
# ---------------------------------------------------------------------------

def _subtract_global_min(image: np.ndarray, global_min: float) -> np.ndarray:
    """Subtract a precomputed global minimum from a single slice."""
    orig_dtype = image.dtype
    result = image.astype(np.float32) - global_min
    result = np.clip(result, 0, None).astype(orig_dtype)
    return result


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

    max_val = np.iinfo(orig_dtype).max if np.issubdtype(orig_dtype, np.integer) else None
    result = np.clip(result, 0, max_val).astype(orig_dtype)
    return result


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

    max_val = np.iinfo(orig_dtype).max if np.issubdtype(orig_dtype, np.integer) else None
    sharpened = np.clip(sharpened, 0, max_val).astype(orig_dtype)

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
    global_background_normalization: bool = False
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
    :yields: (slice_index, processed_image) for each plane in order
    """
    num_slices = len(slices)
    logger.info(
        f"Starting filter pass: method={method.name}, "
        f"global_norm={global_background_normalization}, "
        f"slices={num_slices}"
    )

    # ------------------------------------------------------------------
    # First pass: compute global statistic if needed (no yields here)
    # ------------------------------------------------------------------
    global_stat = None
    if global_background_normalization:
        global_stat = method.compute_global(slices, gaussian_sigma)
        logger.info(f"Global statistic for {method.name}: {global_stat}")

    # ------------------------------------------------------------------
    # Second pass: process and yield one slice at a time
    # ------------------------------------------------------------------
    for i, raw in enumerate(slices):

        # --- background subtraction ---
        if global_background_normalization:
            subtracted = method.apply_global(raw, gaussian_sigma, global_stat)
        else:
            subtracted = method.subtract(raw, gaussian_sigma)

        # --- unsharp masking ---
        processed = _apply_unsharp_mask(subtracted, unsharp_ksize, unsharp_sigma, unsharp_amount)

        logger.debug(f"Filtered slice {i + 1}/{num_slices}")
        yield i, processed