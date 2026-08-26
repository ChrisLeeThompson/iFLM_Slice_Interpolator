"""
Worker Thread Module

ProcessingWorker runs the full processing pipeline for every channel of a
parsed TFS file on a background thread.

Processing order per channel:
    1. Load raw TIFFs from disk into memory
    1b. Hot pixel scan (optional) — folds the whole stack into a persistence
        vote to locate persistent camera defects, and records per-slice
        transient detections (cosmic rays, blinking pixels) along the way.
        Runs before the output directory is cleared, so an aborted scan
        leaves previous output intact.
    2. Filter (hot pixel repair + background subtraction + unsharp mask) —
       yields one slice at a time, each slice written to disk immediately
    3. Interpolate — needs all filtered slices in memory, then yields one
       interpolated slice at a time, each written to disk immediately
    4. Optional TIFF stack (single multi-page file) — streamed one page per
       interpolated slice alongside the per-slice files

The stop flag is a simple bool.  The main thread sets it; the worker checks
it while loading, at every yield point in both generators, and before the
TFS-generation step.
"""

import logging
import re
import shutil
import numpy as np
import cv2
import tifffile
from pathlib import Path
from typing import List
from PySide6.QtCore import QObject, Signal

from .image_filters import process_stack
from .hot_pixel_filter import scan_hot_pixels, HotPixelMask
from .slice_interpolator import interpolate_stack, calculate_interpolated_focus_values
from .processing_config import FilterMethod, InterpolationMethod
from .tfs_file_parser import TFSFileParser
from .tfs_file_generator import generate_interpolated_tfs_file, get_interpolated_tfs_path


logger = logging.getLogger(__name__)


# Characters that cannot appear in Windows file/directory names
_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_dir_name(name: str) -> str:
    """Make a channel-derived name safe to use as a directory name."""
    sanitized = _INVALID_FS_CHARS.sub("_", name).strip().rstrip(". ")
    return sanitized or "channel"


class ProcessingWorker(QObject):
    """
    Worker that runs the filter → interpolate → write pipeline on a background thread.

    Signals
    -------
    status_update(str)
        Human-readable status string for the status label.
    progress_update(int)
        Progress as a percentage 0-100.
    finished()
        Emitted when all channels have been processed successfully.
    stopped()
        Emitted when the user requests a stop and processing exits early.
    error(str)
        Emitted if an unrecoverable exception occurs.  Processing stops.
    """

    status_update   = Signal(str)
    progress_update = Signal(int)
    finished        = Signal()
    stopped         = Signal()
    error           = Signal(str)

    def __init__(
        self,
        tfs_parser:           TFSFileParser,
        filter_method:        FilterMethod,
        interp_method:        InterpolationMethod,
        gaussian_sigma:       float,
        unsharp_ksize:        tuple,
        unsharp_sigma:        float,
        unsharp_amount:       float,
        interpolation_factor: int,
        global_background_normalization: bool,
        hot_pixel_filter:     bool,
        hot_pixel_sigma:      float,
        save_as_stack:        bool,
        output_base_dir:      Path,
        parent=None
    ):
        super().__init__(parent)

        # Everything the worker needs — set once, never mutated after this.
        self._tfs_parser              = tfs_parser
        self._filter_method           = filter_method
        self._interp_method           = interp_method
        self._gaussian_sigma          = gaussian_sigma
        self._unsharp_ksize           = unsharp_ksize
        self._unsharp_sigma           = unsharp_sigma
        self._unsharp_amount          = unsharp_amount
        self._interpolation_factor    = interpolation_factor
        self._global_background_norm  = global_background_normalization
        self._hot_pixel_filter        = hot_pixel_filter
        self._hot_pixel_sigma         = hot_pixel_sigma
        self._save_as_stack           = save_as_stack
        self._output_base_dir         = output_base_dir

        # Stop flag
        self._stop_flag: bool = False

    # ------------------------------------------------------------------
    # Channel naming helpers
    # ------------------------------------------------------------------

    def _get_channel_info(self, channel) -> tuple[str, str, bool]:
        """
        Extract directory name, wavelength tag, and reflection flag for a channel.

        :return: (dir_name, wavelength_tag, is_reflection), e.g.
            ("Blue_L385", "L385", False) or ("Refl_L470", "L470_refl", True)
        """
        # Check if this is a reflection channel (Grey/Gray/Reflection with no
        # wavelength attribute)
        if channel.name.lower() in ("grey", "gray", "reflection") and channel.wavelength is None:
            # Extract wavelength from reflection image filenames
            refl_wavelength = self._tfs_parser.get_reflection_wavelength(channel.index)
            if refl_wavelength:
                dir_name = f"Refl_L{refl_wavelength}"
                wavelength_tag = f"L{refl_wavelength}_refl"
            else:
                # Fallback if we can't detect the wavelength
                dir_name = "Refl"
                wavelength_tag = "refl"
            return dir_name, wavelength_tag, True

        # Normal fluorescence channel — wavelength is already populated
        elif channel.wavelength:
            dir_name = f"{_sanitize_dir_name(channel.name)}_L{channel.wavelength}"
            wavelength_tag = f"L{channel.wavelength}"
            return dir_name, wavelength_tag, False

        # Fallback for channel names with no wavelength mapping (seen in TFS
        # files from non-iFLM software): name outputs after the channel so
        # the filename tag is never empty.
        else:
            name = _sanitize_dir_name(channel.name)
            logger.info(f"Channel '{channel.name}' has no wavelength mapping - using '{name}' for output naming")
            return name, name, False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def request_stop(self):
        """Called by the main thread when the user clicks Stop."""
        self._stop_flag = True

    def run(self):
        """
        Entry point — called by QThread.start().  Do not call directly.

        Routes any exception out of the pipeline to the error signal so
        the thread can never die silently.
        """
        try:
            self._run_pipeline()
        except Exception as exc:
            logger.error("ProcessingWorker hit an exception", exc_info=True)
            self.error.emit(str(exc))

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(self):
        """
        Run the full pipeline for every channel, then generate the TFS file.

        Emits progress and status signals throughout, and exactly one of
        finished(), stopped(), or error() at the end.
        """

        channels = self._tfs_parser.get_channels()
        num_channels = len(channels)

        # --- pre-compute total work units for progress reporting ---
        # Each channel contributes: N (filter yields) + M (interpolate yields).
        # M = (N - 1) * factor + 1.  We need N per channel to sum this up.
        # Channels with no images are skipped by the loop below, so they must
        # contribute nothing here (the formula would go negative for N = 0).
        slice_counts = []                       # original slice count per channel
        for ch in channels:
            n = len(self._tfs_parser.get_images_for_channel(ch.index))
            slice_counts.append(n)

        total_work = sum(
            n + ((n - 1) * self._interpolation_factor + 1)
            for n in slice_counts
            if n > 0
        )

        # --- fail fast on missing files: all channels, before any output ---
        # Done here on the background thread: stat'ing hundreds of TIFFs on a
        # network share would freeze the GUI if done in the Start handler.
        # Silently skipping missing files instead would shift z-indices and
        # desynchronize the written TIFFs from the XML metadata used for
        # focus interpolation and TFS generation.
        missing = []
        for ch in channels:
            missing.extend(self._tfs_parser.get_missing_image_paths_for_channel(ch.index))
        if missing:
            names = ", ".join(p.name for p in missing[:5])
            if len(missing) > 5:
                names += f", ... (+{len(missing) - 5} more)"
            noun, verb = ("image", "is") if len(missing) == 1 else ("images", "are")
            raise RuntimeError(
                f"{len(missing)} source {noun} referenced by the TFS file "
                f"{verb} missing from disk: {names}"
            )

        work_done = 0
        last_progress_percent = -1  # only emit the progress signal on change

        # Channel naming for TFS file generation
        channel_dir_names: dict[int, str] = {}
        channel_wavelength_tags: dict[int, str] = {}

        # --- channel loop ---
        for ch_idx, channel in enumerate(channels):
            if self._stop_flag:
                self.status_update.emit("Processing stopped")
                logger.info("Processing stopped by user (between channels).")
                self.stopped.emit()
                return

            dir_name, wavelength_tag, is_reflection = self._get_channel_info(channel)
            channel_dir_names[channel.index] = dir_name
            channel_wavelength_tags[channel.index] = wavelength_tag

            self.status_update.emit(f"Loading images: {dir_name}")
            logger.info(f"Starting channel {ch_idx + 1}/{num_channels}: {dir_name}")

            # --- 1. Load raw TIFFs ---
            image_paths = self._tfs_parser.get_image_paths_for_channel(channel.index)
            if not image_paths:
                logger.warning(f"No images found for channel '{dir_name}', skipping.")
                self.status_update.emit(f"No images: {dir_name}")
                continue

            raw_slices = self._load_slices(image_paths)
            if self._stop_flag:
                self.status_update.emit("Processing stopped")
                self.stopped.emit()
                return

            num_input_slices = len(raw_slices)

            # --- 1b. Hot pixel scan ---
            # Deliberately before the rmtree below: if the scan refuses the
            # data (implausible defect fraction) it raises, and the previous
            # run's output for this channel is still on disk untouched.
            # Emits status only, no progress units — the scan is a small
            # fraction of a channel's work, below the bar's 1 % resolution.
            hot_pixel_mask: HotPixelMask | None = None
            if self._hot_pixel_filter:
                self.status_update.emit(f"Hot pixel scan: {dir_name}")
                for scan_idx, mask in scan_hot_pixels(raw_slices, self._hot_pixel_sigma):
                    if self._stop_flag:
                        self.status_update.emit("Processing stopped")
                        logger.info(f"Processing stopped during hot pixel scan of '{dir_name}'.")
                        self.stopped.emit()
                        return
                    if mask is not None:
                        hot_pixel_mask = mask
                    elif scan_idx < num_input_slices:
                        # A skipped scan's final (num_slices, None) yield would
                        # otherwise print a tick for a slice never scanned
                        self.status_update.emit(f"Hot pixel scan: {dir_name} z{scan_idx:04d}")

                if hot_pixel_mask is None:
                    # Skipped only when the first frame is constant (short
                    # stacks run transient-only) — details in the log
                    self.status_update.emit(f"Hot pixels: {dir_name} scan skipped (see log)")
                elif not hot_pixel_mask.has_corrections:
                    self.status_update.emit(f"Hot pixels: {dir_name} none found")
                else:
                    prefix = "Hot pixels (high)" if hot_pixel_mask.high_count else "Hot pixels"
                    note = " - follows structure, check the mask file" if hot_pixel_mask.follows_structure else ""
                    self.status_update.emit(
                        f"{prefix}: {dir_name} {hot_pixel_mask.count:,} persistent "
                        f"({hot_pixel_mask.fraction * 100:.4f} %) + "
                        f"{hot_pixel_mask.transient_total:,} transient px{note}"
                    )

            # --- 2. Create a clean output subdirectory for this channel ---
            # From here until the new TFS is generated at the very end, the
            # on-disk output is a partial mix of old and new planes.  A
            # previous run's interpolated TFS must not survive into that
            # window: if this run aborts after rewriting a channel (e.g. at a
            # different interpolation factor), the stale XML would reference
            # z-planes that no longer exist and a TFS Maps import would load
            # a broken or channel-inconsistent stack.  First iteration
            # deletes it; later ones are a no-op.
            stale_tfs = get_interpolated_tfs_path(self._tfs_parser.tfs_file_path)
            if stale_tfs.exists():
                stale_tfs.unlink()
                logger.info(f"Removed previous interpolated TFS file: {stale_tfs.name}")

            # Clear any previous run's output first: a re-run with a smaller
            # interpolation factor would otherwise leave stale higher-z TIFFs
            # mixed into the directory.
            channel_dir = self._output_base_dir / dir_name
            if channel_dir.exists():
                logger.info(f"Clearing previous output directory: {channel_dir}")
                shutil.rmtree(channel_dir)
            channel_dir.mkdir(parents=True, exist_ok=True)

            # Audit trail: a 0/255 map of every pixel this run will edit.
            # Written into the channel directory so it travels with the data.
            # Nothing in tfs_file_generator enumerates a directory (paths are
            # built by pattern), so an extra file here cannot affect the
            # generated XML or a TFS Maps import.
            if hot_pixel_mask is not None and hot_pixel_mask.count:
                mask_path = channel_dir / f"hotpixel_mask_{wavelength_tag}.tif"
                tifffile.imwrite(str(mask_path), hot_pixel_mask.to_mask_image())
                logger.info(f"Wrote hot pixel mask: {mask_path}")

            # Companion audit: per-pixel detection counts.  In Fiji, persistent
            # defects read ~num_slices, blinking pixels read intermediate
            # values, and cosmic rays read 1.
            if hot_pixel_mask is not None and hot_pixel_mask.has_corrections:
                votes_path = channel_dir / f"hotpixel_votes_{wavelength_tag}.tif"
                tifffile.imwrite(str(votes_path), hot_pixel_mask.votes)
                logger.info(f"Wrote hot pixel vote map: {votes_path}")

            # --- 3. Filter pass ---
            self.status_update.emit(f"Filtering: {dir_name}")

            filtered_slices: List[np.ndarray] = []

            for slice_idx, filtered_image in process_stack(
                raw_slices,
                self._filter_method,
                unsharp_ksize=self._unsharp_ksize,
                gaussian_sigma=self._gaussian_sigma,
                unsharp_sigma=self._unsharp_sigma,
                unsharp_amount=self._unsharp_amount,
                global_background_normalization=self._global_background_norm,
                hot_pixel_mask=hot_pixel_mask
            ):
                if self._stop_flag:
                    self.status_update.emit("Processing stopped")
                    logger.info(f"Processing stopped during filtering of '{dir_name}'.")
                    self.stopped.emit()
                    return

                # Example: filtered_stack_z0042_L385.tif
                filtered_filename = f"filtered_stack_z{slice_idx:04d}_{wavelength_tag}.tif"
                filtered_path = channel_dir / filtered_filename
                tifffile.imwrite(str(filtered_path), filtered_image)

                self.status_update.emit(f"Filtering: {dir_name} z{slice_idx:04d}")

                # Keep in memory — interpolator needs the full filtered stack
                filtered_slices.append(filtered_image)

                work_done += 1
                if total_work > 0:
                    current_percent = int(work_done / total_work * 100)
                    if current_percent != last_progress_percent:
                        last_progress_percent = current_percent
                        self.progress_update.emit(current_percent)

            del raw_slices

            # --- 4. Interpolation pass ---
            self.status_update.emit(f"Interpolating: {dir_name}")

            # The optional multi-page stack file is streamed one page per
            # interpolated slice rather than accumulated in memory first —
            # accumulating would double the peak footprint on large stacks.
            stack_writer = None
            if self._save_as_stack:
                stack_path = channel_dir / f"interpolated_stack_{wavelength_tag}.tif"
                stack_writer = tifffile.TiffWriter(str(stack_path))

            try:
                for slice_idx, interpolated_image in interpolate_stack(
                    filtered_slices,
                    self._interp_method,
                    interpolation_factor=self._interpolation_factor
                ):
                    if self._stop_flag:
                        self.status_update.emit("Processing stopped")
                        logger.info(f"Processing stopped during interpolation of '{dir_name}'.")
                        self.stopped.emit()
                        return

                    # Example: interpolated_stack_z0000_L385.tif
                    interp_filename = f"interpolated_stack_z{slice_idx:04d}_{wavelength_tag}.tif"
                    interp_path = channel_dir / interp_filename
                    tifffile.imwrite(str(interp_path), interpolated_image)

                    if stack_writer is not None:
                        stack_writer.write(interpolated_image, contiguous=True)

                    self.status_update.emit(f"Interpolating: {dir_name} z{slice_idx:04d}")

                    work_done += 1
                    if total_work > 0:
                        current_percent = int(work_done / total_work * 100)
                        if current_percent != last_progress_percent:
                            last_progress_percent = current_percent
                            self.progress_update.emit(current_percent)
            finally:
                if stack_writer is not None:
                    stack_writer.close()

            if stack_writer is not None:
                logger.info(f"Wrote stack file: {stack_path.name}")

            del filtered_slices

        # --- all channels done, now generate the interpolated TFS file ---
        if self._stop_flag:
            self.status_update.emit("Processing stopped")
            logger.info("Processing stopped before TFS file generation.")
            self.stopped.emit()
            return

        self.status_update.emit("Generating TFS file...")
        
        try:
            output_tfs_path = generate_interpolated_tfs_file(
                original_tfs_path=self._tfs_parser.tfs_file_path,
                original_parser=self._tfs_parser,
                interpolation_factor=self._interpolation_factor,
                channel_dir_names=channel_dir_names,
                channel_wavelength_tags=channel_wavelength_tags
            )
            logger.info(f"Generated interpolated TFS file: {output_tfs_path.name}")
        except Exception as exc:
            logger.error("Failed to generate interpolated TFS file", exc_info=True)
            self.error.emit(f"TFS generation failed: {exc}")
            return

        # --- complete ---
        self.progress_update.emit(100)
        self.status_update.emit("Processing complete")
        logger.info("Processing complete — all channels finished.")
        self.finished.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_slices(self, image_paths: List[Path]) -> List[np.ndarray]:
        """
        Load a list of TIFF paths into memory as grayscale numpy arrays.

        An unreadable file raises rather than being skipped - a silently
        dropped slice would desynchronize the written TIFFs from the XML
        metadata used for TFS generation.  Returns early (partial list) if
        a stop was requested; the caller checks the stop flag right after.

        :param image_paths: Ordered list of paths (plane 0, 1, 2, …)
        :return: List of 2D numpy arrays in the same order
        """
        slices = []
        for path in image_paths:
            if self._stop_flag:
                return slices
            img = self._read_image(path)
            slices.append(img)
            logger.debug(f"Loaded {path.name}: shape={img.shape}, dtype={img.dtype}")
        return slices

    @staticmethod
    def _read_image(path: Path) -> np.ndarray:
        """
        Read a single image with IMREAD_UNCHANGED semantics (16-bit stays 16-bit).

        Decodes via np.fromfile + cv2.imdecode instead of cv2.imread: on
        Windows, imread opens files through the narrow ANSI API and fails on
        paths containing characters outside the system codepage.

        :param path: Path to the image file
        :raises RuntimeError: If the file cannot be read or decoded
        """
        try:
            data = np.fromfile(str(path), dtype=np.uint8)
        except OSError as exc:
            raise RuntimeError(f"Could not read image file: {path.name} ({exc})") from exc

        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED) if data.size > 0 else None
        if img is None:
            raise RuntimeError(f"Could not decode image file: {path.name} (corrupt or unsupported format)")
        return img