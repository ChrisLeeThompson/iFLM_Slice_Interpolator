"""
Hot Pixel Filter

Detects and repairs hot pixels in two tiers:

  * Persistent defects: sensor elements that sit at a fixed (y, x) and read
    high in essentially every plane of a z-stack.  Found by a stack-wide
    persistence vote and repaired in every slice - including planes where a
    bright neighbour or saturation happens to mask the defect.
  * Transient events: cosmic rays and RTS ("blinking") pixels that read high
    in only some planes.  Any per-slice detection that is not in the
    persistent map is repaired only in the slice where it occurred.

This module is separate from image_filters.py because it imports only numpy
and cv2 (no PySide6, no scipy), so every function here can be driven directly
against a real image stack with no QApplication and no TFS file.

Discriminating statistic
------------------------
Detection in every slice uses the same spatial test:

  1. Spatial   excess(p, z) = I(p, z) - max(8 neighbours of p in slice z)
               A strict local maximum.  Anything at least 2 px wide in any
               direction - including a 1-px-wide line, whose neighbours are
               also on the line - has an equally bright neighbour and scores
               excess ~ 0.  A 3x3 median reference would erase the whole line.

The persistent tier additionally requires a temporal vote:

  2. Temporal  vote(p) = #{ z : excess(p, z) > offset(p, z) + k * scale(p, z) }
               hot(p)  = vote(p) >= 0.90 * N
               Real fluorescence cannot do this: defocus spreads a point
               emitter sideways through z, so a genuine feature either fades
               below threshold or widens until a neighbour matches it.

The conjunction is what makes the persistent tier safe to apply everywhere.
Test 2 alone would also flag a stationary object (a stuck bead, a dust
speck); test 1 rejects it on size.

Persistence carries ~N independent bits of evidence, so k can be modest and
still produce essentially no noise-driven false positives.  Worst case, at an
absurd per-slice false rate of 0.5 on a 71-slice stack (needing 64 votes):
P(Binom(71, 0.5) >= 64) = 6.3e-13, times 16 Mpixel = 1e-5 false px per frame.
That binomial argument is what licenses a low k, so _VOTE_FRACTION is a fixed
module constant and is deliberately not exposed in the UI.  The margin is
thinner on short stacks - at N = 17 the same tail is 1.4e-4, ~2,200 px on a
16 Mpixel frame - which is why _MIN_SLICES exists and why the dispersion
guard below is worth its cost.

The transient tier rests on the spatial test alone, so its safety is bounded
differently: at 6 sigma on real iFLM data it flags ~0.13 % of the frame per
slice, scattered like sensor noise (dispersion ~1.0), not like structure.  A
false positive costs one strict local maximum flattened to its neighbourhood
median - darken-only, in one slice - whereas a missed spike is amplified
~3.7x by the default unsharp settings downstream and copied into every
interpolated plane by the z-spline.  That asymmetry is why transient repair
is on whenever the filter is on.

Nothing here has units of microns.  The spatial test is pure pixel adjacency
and the threshold is measured in locally estimated noise sigma, so the filter
adapts itself to any objective, magnification, or pixel size and needs no
NA, magnification, or pixel-size parameter.

Known blind spots
-----------------
  * A transient masked by a bright neighbour in its own slice is missed in
    that slice.  Persistent defects are immune: the stack-wide map repairs
    them in every plane regardless.
  * Solid clusters and hot columns are missed - the strict-local-max rule
    makes it impossible for two 8-adjacent pixels to both be flagged.  That
    same property is what guarantees a repair is never contaminated.
  * Cold / dead pixels are out of scope; this filter is one-sided.
"""

import logging
import math
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple


logger = logging.getLogger(__name__)


# Hollow 3x3 structuring element: the zero centre makes cv2.dilate return the
# maximum of the 8 neighbours, excluding the pixel itself.
_NEIGHBOUR_KERNEL = np.array([[1, 1, 1],
                              [1, 0, 1],
                              [1, 1, 1]], dtype=np.uint8)

# Fraction of slices in which a pixel must be a thresholded local maximum.
# Not a UI parameter - see the binomial argument in the module docstring.
_VOTE_FRACTION = 0.90

# Below this many slices the persistence evidence is too thin to trust, so
# the vote (and with it the persistent tier) is disabled - transient repair
# still runs, being purely spatial.  _validate_channels permits stacks as
# short as k + 1 = 2, so this is load-bearing rather than defensive.
_MIN_SLICES = 8

# Local offset/scale are estimated on a block grid: area-average into 16x16
# blocks, take a median across a 5x5 neighbourhood of blocks, then upsample.
# The block median is what makes the estimate robust - a saturated pixel
# contaminates exactly one block and is outvoted by the other 24.  A plain box
# mean over the same support is not robust: one stuck-at-max pixel inflates
# the threshold ~5.7x across its whole neighbourhood and self-masks every weak
# defect nearby.
_SCALE_BLOCK = 16
_SCALE_MEDIAN_KSIZE = 5          # cv2.medianBlur on float32 supports ksize 3 and 5 only

# E|x| = sigma * sqrt(2/pi) for zero-mean Gaussian x  ->  sigma = 1.2533 * E|x|
_MAD_TO_SIGMA = 1.2533

# Floor on the local scale.  Quantization alone contributes 1/sqrt(12) = 0.289
# ADU on integer data.  Without a floor a perfectly flat frame gives scale = 0
# exactly and every strict local maximum (~1 pixel in 9) is flagged.  Float
# images get a floor derived from their own dynamic range - a hardcoded 1.0
# would silently disable the filter on data normalized to [0, 1].
_MIN_SCALE_INTEGER = 0.5
_MIN_SCALE_FLOAT_FRACTION = 1e-6

# A real camera defect map is 0.001 - 0.5 % of the frame.  Measured on real
# filter-off iFLM data: 0.109 % at 5 sigma.  These sit ~4.5x and ~18x above
# that, so neither fires on good data at any sensitivity setting.
_WARN_FRACTION = 0.005           # 0.5 %  -> warn, continue
_ABORT_FRACTION = 0.02           # 2.0 %  -> refuse, write nothing

# Sensor defects are spatially random; biological structure clusters.  The
# index of dispersion (variance/mean of flagged counts per block) separates
# them without knowing anything about the optics.  Measured: ~1.0 when nothing
# real is being flagged, rising well above 1.5 as real features start being
# caught, 1.08 on real filter-off iFLM data.
#
# The grid must adapt to the flagged count, not be fixed: a fixed 16x16 grid
# puts 21.7 px/block on a frame with 5,556 defects but only 0.34 px/block on
# one with 87, where the statistic is pure noise.  Sizing the grid to hold
# ~_DISPERSION_TARGET_PER_BLOCK keeps it meaningful across three orders of
# magnitude of defect count.
_DISPERSION_WARN = 1.5
_DISPERSION_TARGET_PER_BLOCK = 12
_DISPERSION_MIN_GRID = 4
_DISPERSION_MAX_GRID = 32
_DISPERSION_MIN_COUNT = 50       # below this, no grid is thick enough to trust


@dataclass
class HotPixelMask:
    """A finished scan: where the defects are, how to repair them, what to report.

    The persistent-tier fields (ys/xs, neighbour tables, excess_floor,
    dispersion, count, fraction, to_mask_image) describe only the stack-wide
    defect map; the transient tier lives in transient_ys/xs and votes.
    """

    ys: np.ndarray                  # (K,) row indices of persistent defects
    xs: np.ndarray                  # (K,) column indices
    neighbour_ys: np.ndarray        # (8, K) clamped rows, built once per channel
    neighbour_xs: np.ndarray        # (8, K) clamped columns
    shape: Tuple[int, int]
    threshold_sigma: float
    num_slices: int
    excess_floor: np.ndarray        # (K,) guaranteed excess over the whole stack
    dispersion: float               # index of dispersion of the persistent set
    transient_ys: List[np.ndarray]  # len N; (T_z,) rows of transient-only hits in slice z
    transient_xs: List[np.ndarray]  # parallel columns, same ragged shape
    votes: np.ndarray               # (H, W) per-pixel detection count, for the audit TIFF
    max_slice_fraction: float       # max over slices of the per-slice detection fraction

    @property
    def count(self) -> int:
        return int(self.ys.size)

    @property
    def fraction(self) -> float:
        return self.count / float(self.shape[0] * self.shape[1])

    @property
    def transient_counts(self) -> np.ndarray:
        """(num_slices,) transient repair count per slice."""
        return np.array([ys.size for ys in self.transient_ys], dtype=np.intp)

    @property
    def transient_total(self) -> int:
        return int(sum(ys.size for ys in self.transient_ys))

    @property
    def has_corrections(self) -> bool:
        return self.count > 0 or self.transient_total > 0

    @property
    def follows_structure(self) -> bool:
        """True when the persistent set clusters like image structure rather
        than scattering like sensor defects.  See _DISPERSION_WARN."""
        return self.dispersion > _DISPERSION_WARN

    @property
    def high_count(self) -> bool:
        """True when any slice's detection fraction exceeds the warn threshold.
        The worker's status-line (high) prefix reads this so the UI flag and
        the log warning can never disagree on the threshold."""
        return self.max_slice_fraction > _WARN_FRACTION

    def to_mask_image(self) -> np.ndarray:
        """0/255 uint8 image of the persistent defect map for the audit TIFF."""
        img = np.zeros(self.shape, dtype=np.uint8)
        img[self.ys, self.xs] = 255
        return img

    def summary(self) -> str:
        if not self.has_corrections:
            return (f"none found at {self.threshold_sigma:.0f} sigma "
                    f"over {self.num_slices} slices")
        if self.count:
            persistent = (f"{self.count:,} persistent px "
                          f"({self.fraction * 100:.4f} % of frame, "
                          f"{self.fraction * 1e6:.0f} ppm; excess over brightest "
                          f"neighbour: median={np.median(self.excess_floor):.1f}, "
                          f"max={self.excess_floor.max():.1f}; "
                          f"dispersion={self.dispersion:.2f})")
        else:
            persistent = "0 persistent px"
        if self.transient_total:
            counts = self.transient_counts
            transient = (f"{self.transient_total:,} transient px "
                         f"(per-slice mean={counts.mean():.0f}, "
                         f"max={int(counts.max()):,})")
        else:
            transient = "0 transient px"
        return (f"{persistent} + {transient} at {self.threshold_sigma:.0f} sigma "
                f"over {self.num_slices} slices")


# ---------------------------------------------------------------------------
# Local statistics
# ---------------------------------------------------------------------------

def _block_map(field: np.ndarray, small_size: Tuple[int, int]) -> np.ndarray:
    """
    Locally-averaged, outlier-robust map of `field`, at full resolution.

    INTER_AREA averages each block; the 5x5 median across blocks discards any
    block a defect contaminated; INTER_LINEAR restores full size.  Effective
    support ~80x80 px at roughly a third the cost of a 65x65 box blur and -
    unlike a box blur - a single extreme pixel cannot move it.
    """
    small = cv2.resize(field, small_size, interpolation=cv2.INTER_AREA)
    if min(small.shape[0], small.shape[1]) >= _SCALE_MEDIAN_KSIZE:
        # float32 + ksize 5 is a supported cv2.medianBlur combination
        small = cv2.medianBlur(small, _SCALE_MEDIAN_KSIZE)
    return cv2.resize(small, (field.shape[1], field.shape[0]),
                      interpolation=cv2.INTER_LINEAR)


def _local_offset_and_scale(excess: np.ndarray,
                            small_size: Tuple[int, int],
                            scale_floor: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Spatially varying centre and spread of the local-maximum excess field.

    Both are needed because both track local intensity: shot noise scales as
    sqrt(I), and E[max of 8 neighbours] sits ~1.4 sigma above the pixel, so
    `excess` is systematically negative and more so where the frame is bright.
    A single global threshold is set by the darkest part of the frame and then
    misapplied to the brightest - which is where the specimen is.
    """
    offset = _block_map(excess, small_size)
    dev = np.abs(excess - offset)
    scale = _block_map(dev, small_size)
    scale *= _MAD_TO_SIGMA
    np.maximum(scale, scale_floor, out=scale)
    return offset, scale


def _scale_floor_for(reference: np.ndarray) -> Optional[float]:
    """Dtype-relative floor on the local scale.  None means 'nothing to detect'."""
    if np.issubdtype(reference.dtype, np.integer):
        return _MIN_SCALE_INTEGER
    span = float(np.ptp(reference))
    if span == 0.0:
        return None
    return span * _MIN_SCALE_FLOAT_FRACTION


def _dispersion_of(mask: np.ndarray, count: int) -> float:
    """
    Index of dispersion (variance/mean) of flagged counts over a coarse grid.

    ~1.0 means spatially random, which is what a sensor defect map looks like.
    Values well above 1 mean the flagged set is clustering, i.e. tracking image
    structure - the signature of real features being caught.

    The grid is sized from the count so each block holds ~12 flagged pixels;
    a fixed grid would make the statistic meaningless (and silently return
    "safe") whenever the defect count is small.  Returns 0.0 - read as "not
    measured" - when even the coarsest grid would be too thin.
    """
    if count < _DISPERSION_MIN_COUNT:
        return 0.0
    g = int(round(math.sqrt(count / float(_DISPERSION_TARGET_PER_BLOCK))))
    g = max(_DISPERSION_MIN_GRID, min(_DISPERSION_MAX_GRID, g))
    bh, bw = mask.shape[0] // g, mask.shape[1] // g
    if bh < 1 or bw < 1:
        return 0.0
    counts = mask[:bh * g, :bw * g].reshape(g, bh, g, bw).sum(axis=(1, 3)).astype(np.float64)
    mean = counts.mean()
    if mean <= 0.0:
        return 0.0
    return float(counts.var() / mean)


def _neighbour_indices(ys: np.ndarray, xs: np.ndarray,
                       shape: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray]:
    """
    (8, K) coordinates of each flagged pixel's 8 neighbours.

    Built once per channel for the persistent map because they are identical
    for every slice - this is what makes correction O(K) rather than O(H*W).
    The transient tier builds its own small set per slice.

    Out-of-frame neighbours mirror back inside (REFLECT_101, matching the
    detection padding), so a border pixel's donors are real nearby pixels -
    never the pixel itself.  Two mirrored offsets can land on the same donor
    at the frame edge; a repeated value cannot move the median much and the
    strict-local-max rule still guarantees no donor is itself flagged.
    """
    height, width = shape
    offsets = [(-1, -1), (-1, 0), (-1, 1),
               (0, -1),           (0, 1),
               (1, -1),  (1, 0),  (1, 1)]
    nys = np.empty((8, ys.size), dtype=np.intp)
    nxs = np.empty((8, xs.size), dtype=np.intp)
    for i, (dy, dx) in enumerate(offsets):
        # reflect101(v) = min(|v|, 2*(n-1) - |v|) for v in [-1, n]; the final
        # clip only matters for degenerate 1-px-wide frames.
        ny = np.abs(ys + dy)
        nx = np.abs(xs + dx)
        np.minimum(ny, 2 * (height - 1) - ny, out=ny)
        np.minimum(nx, 2 * (width - 1) - nx, out=nx)
        np.clip(ny, 0, height - 1, out=nys[i])
        np.clip(nx, 0, width - 1, out=nxs[i])
    return nys, nxs


# ---------------------------------------------------------------------------
# Public: detection
# ---------------------------------------------------------------------------

def scan_hot_pixels(
    slices: List[np.ndarray],
    threshold_sigma: float = 6.0
) -> Generator[Tuple[int, Optional[HotPixelMask]], None, None]:
    """
    Generator that folds one slice at a time into a persistence vote while
    recording per-slice detections, then yields the finished mask.

    Yields (slice_index, None) once per slice while accumulating, then one
    final (num_slices, mask), so a caller iterating with a stop check can
    cancel at every fold; only the short finalize tail is uninterruptible.

    A mask of None as the final yield means "skip hot pixel filtering" - a
    degenerate constant first frame.  Stacks shorter than _MIN_SLICES still
    produce a mask: the persistence vote is disabled (no persistent tier) but
    per-slice transient detections are kept.  The stack is never modified.

    :param slices: Full raw stack for one channel.  Never modified.
    :param threshold_sigma: Per-slice threshold in units of the local scale.
    :yields: (index, None) per slice, then (num_slices, HotPixelMask or None)
    :raises ValueError: on an empty stack or non-2D slices
    :raises RuntimeError: if any slice's detection fraction (or the persistent
        map's fraction) exceeds _ABORT_FRACTION
    """
    num_slices = len(slices)
    if num_slices == 0:
        raise ValueError("Hot pixel filtering needs at least one slice")

    reference = slices[0]
    if reference.ndim != 2:
        raise ValueError(
            f"Hot pixel filtering needs 2D grayscale slices, got shape {reference.shape}"
        )

    persistence_enabled = num_slices >= _MIN_SLICES
    if not persistence_enabled:
        logger.info(
            f"Hot pixel filter: {num_slices} slices is below the {_MIN_SLICES} "
            f"needed for the persistence vote to mean anything. Persistent-"
            f"defect detection is disabled; per-slice transients are still "
            f"repaired."
        )

    scale_floor = _scale_floor_for(reference)
    if scale_floor is None:
        logger.warning(
            "Hot pixel filter: first slice is constant (zero dynamic range); "
            "nothing to detect. Skipping - images pass through unchanged."
        )
        yield num_slices, None
        return

    height, width = reference.shape
    # needed = N + 1 is unreachable, so with the vote disabled `hot` in the
    # finalize step comes out all-False with no extra branching.
    needed = (int(math.ceil(_VOTE_FRACTION * num_slices))
              if persistence_enabled else num_slices + 1)

    # Block grid for the local offset/scale maps.  Clamped so tiny frames still
    # produce a usable (if coarse) map rather than a zero-size resize.
    small_size = (max(width // _SCALE_BLOCK, _SCALE_MEDIAN_KSIZE),
                  max(height // _SCALE_BLOCK, _SCALE_MEDIAN_KSIZE))

    # Size the accumulator to N.  A uint8 accumulator silently wraps at 300
    # planes - reachable from this UI - and reports "0 hot" with no exception.
    vote_dtype = np.uint16 if num_slices <= np.iinfo(np.uint16).max else np.uint32
    votes = np.zeros((height, width), dtype=vote_dtype)
    excess_floor = np.full((height, width), np.inf, dtype=np.float32)

    # Per-slice detection coordinates, split into transients at finalize.
    # ~110 KB per 2256x2256 slice at real defect rates - negligible.
    slice_det_ys: List[np.ndarray] = []
    slice_det_xs: List[np.ndarray] = []
    max_slice_fraction = 0.0

    vote_text = (f"vote {needed}/{num_slices}" if persistence_enabled
                 else "vote disabled (transient-only)")
    logger.info(
        f"Hot pixel scan: {num_slices} slices, {height}x{width}, "
        f"dtype={reference.dtype}, threshold={threshold_sigma:.0f} sigma, "
        f"{vote_text}"
    )

    for i, raw in enumerate(slices):
        if raw.shape != (height, width):
            raise ValueError(
                f"Hot pixel filter: slice {i} has shape {raw.shape}, "
                f"expected {(height, width)}"
            )

        # cv2.dilate on float32 only - it rejects int32/uint32/int64/float16.
        # Mirror-pad by one pixel first (REFLECT_101 never mirrors a pixel
        # into its own neighbourhood) so border pixels compare against their
        # available real neighbours instead of dilate's -inf padding, which
        # would make every edge pixel look like a peak.  Zeroing the ring
        # instead - the previous approach - made the outer ring undetectable
        # by both tiers, and a border defect sailed straight into the unsharp
        # amplifier.
        float_img = raw.astype(np.float32)
        padded = cv2.copyMakeBorder(float_img, 1, 1, 1, 1, cv2.BORDER_REFLECT_101)
        neighbour_max = cv2.dilate(padded, _NEIGHBOUR_KERNEL)[1:-1, 1:-1]
        excess = float_img - neighbour_max

        offset, scale = _local_offset_and_scale(excess, small_size, scale_floor)

        # Floor the threshold field at zero.  offset is systematically
        # negative (E[max of 8] sits above the pixel), so on a steep
        # persistent intensity gradient offset + k*scale can dip below 0 -
        # and an interior pixel on such a flank would then win the vote in
        # every slice.  A hot pixel must at minimum beat its brightest
        # neighbour, so a threshold below zero is never meaningful.
        threshold = offset + threshold_sigma * scale
        np.maximum(threshold, 0.0, out=threshold)
        detected = excess > threshold
        votes += detected
        np.minimum(excess_floor, excess, out=excess_floor)

        det_ys, det_xs = np.nonzero(detected)
        det_fraction = det_ys.size / float(height * width)
        if det_fraction > _ABORT_FRACTION:
            raise RuntimeError(
                f"Hot pixel filter flagged {det_ys.size:,} pixels "
                f"({det_fraction * 100:.2f} % of slice {i}) at "
                f"{threshold_sigma:.0f} sigma. That is far more than any real "
                "defect map, so the threshold is wrong for this data. Set "
                "Hot Pixel Sensitivity to a higher value (fewer detections) "
                "or disable the filter. The run stopped and no interpolated "
                "TFS file was written."
            )
        max_slice_fraction = max(max_slice_fraction, det_fraction)
        slice_det_ys.append(det_ys)
        slice_det_xs.append(det_xs)

        yield i, None

    # --- finalize ---
    hot = votes >= needed
    ys, xs = np.nonzero(hot)
    count = int(ys.size)
    fraction = count / float(height * width)

    # Defensive double-check: the per-slice guard above nearly subsumes this
    # (a persistent map is built from per-slice detections), but it costs
    # nothing.
    if fraction > _ABORT_FRACTION:
        raise RuntimeError(
            f"Hot pixel filter flagged {count:,} persistent pixels "
            f"({fraction * 100:.2f} % of the frame) at {threshold_sigma:.0f} "
            "sigma. That is far more than any real defect map, so the "
            "threshold is wrong for this data. Set Hot Pixel Sensitivity to "
            "a higher value (fewer detections) or disable the filter. The "
            "run stopped and no interpolated TFS file was written."
        )

    # Transients: per-slice detections minus the persistent set.  Disjoint by
    # construction, so the two repair passes can never write the same pixel.
    transient_ys: List[np.ndarray] = []
    transient_xs: List[np.ndarray] = []
    for dy, dx in zip(slice_det_ys, slice_det_xs):
        if count:
            keep = ~hot[dy, dx]
            dy, dx = dy[keep], dx[keep]
        transient_ys.append(dy)
        transient_xs.append(dx)

    # Dispersion stays a persistent-set statistic: cosmic-ray transients are
    # random by nature, and a garbage slice is caught by the per-slice
    # fraction rails, so a per-slice dispersion would add noise, not signal.
    dispersion = _dispersion_of(hot, count)
    nys, nxs = _neighbour_indices(ys, xs, (height, width))

    mask = HotPixelMask(
        ys=ys,
        xs=xs,
        neighbour_ys=nys,
        neighbour_xs=nxs,
        shape=(height, width),
        threshold_sigma=threshold_sigma,
        num_slices=num_slices,
        excess_floor=excess_floor[ys, xs] if count else np.empty(0, np.float32),
        dispersion=dispersion,
        transient_ys=transient_ys,
        transient_xs=transient_xs,
        votes=votes,
        max_slice_fraction=max_slice_fraction,
    )

    if max_slice_fraction > _WARN_FRACTION:
        logger.warning(
            f"Hot pixel filter flagged an unusually large fraction of at least one "
            f"slice (max {max_slice_fraction * 100:.2f} %): {mask.summary()}. "
            f"Inspect the hotpixel_votes TIFF (and the hotpixel_mask TIFF, present "
            f"when persistent defects were found) before trusting the output."
        )
    if mask.follows_structure:
        logger.warning(
            f"Hot pixel filter: flagged pixels cluster like image structure "
            f"(dispersion {dispersion:.2f} > {_DISPERSION_WARN}), not like sensor "
            f"defects. Some may be real single-pixel features. Inspect the "
            f"hotpixel_mask TIFF, and consider raising the sensitivity."
        )
    logger.info(f"Hot pixel scan complete: {mask.summary()}")

    yield num_slices, mask


# ---------------------------------------------------------------------------
# Public: correction
# ---------------------------------------------------------------------------

def _repair_pixels(result: np.ndarray, image: np.ndarray,
                   ys: np.ndarray, xs: np.ndarray,
                   nys: np.ndarray, nxs: np.ndarray) -> None:
    """Median-of-8 repair of (ys, xs) in result, reading donors from image."""
    # float64 gather so int32 inputs above 2**24 do not lose precision
    neighbours = image[nys, nxs].astype(np.float64)
    replacement = np.median(neighbours, axis=0)
    original = image[ys, xs].astype(np.float64)
    np.minimum(replacement, original, out=replacement)

    if np.issubdtype(image.dtype, np.integer):
        replacement = np.rint(replacement)
    result[ys, xs] = replacement.astype(image.dtype)


def correct_hot_pixels(image: np.ndarray, mask: HotPixelMask,
                       slice_index: Optional[int] = None) -> np.ndarray:
    """
    Replace the flagged pixels with the median of their 8 neighbours.

    Two tiers: the persistent map is repaired in every slice; the transient
    detections for slice_index are repaired only here.  slice_index=None
    applies the persistent map alone (useful for diagnostics driving the
    module directly).  Both tiers read donors from the original image: a
    transient 8-adjacent to a persistent pixel contributes one contaminated
    donor to the other's median-of-8, which the median absorbs.  The two
    coordinate sets are disjoint by construction, so the repairs never write
    the same pixel.

    Two deliberate properties:

    * The replacement is clamped with np.minimum so a repair can only ever
      darken a pixel.  The persistent map is stack-derived and applied to
      every slice, so where a masked pixel happens to be dark in one plane
      while its neighbours are bright, an unclamped median would raise it -
      writing a value brighter than the sensor measured.  (For a transient in
      its own detection slice the clamp is a mathematical no-op - detection
      required beating the brightest neighbour - but it is kept for
      uniformity.)

    * No np.clip.  Every output value is either the original pixel or the
      median of eight real pixel values from the same frame, so it is in
      range by construction; clipping at 0 would instead corrupt int16
      images with legitimately negative values.

    :param image: 2D numpy array
    :param mask: HotPixelMask from scan_hot_pixels
    :param slice_index: Index of this image in the scanned stack, or None to
        apply only the persistent map
    :return: Corrected copy in the original dtype (input is never modified)
    :raises ValueError: on a shape mismatch or an out-of-range slice_index
    """
    if image.shape != mask.shape:
        raise ValueError(
            f"Hot pixel mask shape {mask.shape} does not match image {image.shape}"
        )

    tys = txs = None
    if slice_index is not None:
        if not 0 <= slice_index < len(mask.transient_ys):
            raise ValueError(
                f"Slice index {slice_index} is out of range for a "
                f"{len(mask.transient_ys)}-slice scan"
            )
        tys = mask.transient_ys[slice_index]
        txs = mask.transient_xs[slice_index]
        if tys.size == 0:
            tys = txs = None

    if mask.count == 0 and tys is None:
        # Copy even here: the contract is that the input is never aliased by
        # the return value, and a caller mutating the result in place must
        # never corrupt the raw slice list.
        return image.copy()

    result = image.copy()

    if mask.count:
        _repair_pixels(result, image, mask.ys, mask.xs,
                       mask.neighbour_ys, mask.neighbour_xs)
    if tys is not None:
        # Neighbour tables on the fly: transient sets are small (~10^3 px) and
        # differ per slice, so precomputing per-slice tables buys nothing.
        nys, nxs = _neighbour_indices(tys, txs, mask.shape)
        _repair_pixels(result, image, tys, txs, nys, nxs)
    return result
